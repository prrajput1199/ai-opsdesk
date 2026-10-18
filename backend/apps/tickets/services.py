"""
Ticket business logic (write side). Views stay thin and call these functions.

Rules enforced here, regardless of which client calls the API:
- allowed status transitions per role
- who may assign tickets and to whom
- customers can never post internal notes
- related writes (ticket + activity + audit) happen in one transaction
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import log_action

from .models import (
    ReplyDraft,
    SLAPolicy,
    Ticket,
    TicketActivity,
    TicketAIInsight,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)

logger = logging.getLogger(__name__)

S = TicketStatus

STAFF_TRANSITIONS = {
    S.OPEN: {S.IN_PROGRESS, S.WAITING_FOR_CUSTOMER, S.RESOLVED, S.CLOSED},
    S.IN_PROGRESS: {S.OPEN, S.WAITING_FOR_CUSTOMER, S.RESOLVED, S.CLOSED},
    S.WAITING_FOR_CUSTOMER: {S.IN_PROGRESS, S.RESOLVED, S.CLOSED},
    S.RESOLVED: {S.IN_PROGRESS, S.CLOSED},
    S.CLOSED: set(),
}

# Customers may withdraw (close) their ticket at any time, and confirm or reopen a resolution.
CUSTOMER_TRANSITIONS = {
    S.OPEN: {S.CLOSED},
    S.IN_PROGRESS: {S.CLOSED},
    S.WAITING_FOR_CUSTOMER: {S.CLOSED},
    S.RESOLVED: {S.CLOSED, S.OPEN},
    S.CLOSED: set(),
}


# ---------------------------------------------------------------------------
# SLA
# ---------------------------------------------------------------------------
def sla_hours_for(priority):
    hours = SLAPolicy.objects.filter(priority=priority).values_list("resolution_hours", flat=True).first()
    return hours or settings.DEFAULT_SLA_HOURS.get(priority, 72)


def compute_sla_due(created_at, priority):
    return created_at + timedelta(hours=sla_hours_for(priority))


# ---------------------------------------------------------------------------
# Permissions helpers
# ---------------------------------------------------------------------------
def allowed_transitions(ticket, user):
    table = CUSTOMER_TRANSITIONS if user.role == "CUSTOMER" else STAFF_TRANSITIONS
    return sorted(table.get(ticket.status, set()))


def can_assign(ticket, user):
    if user.role == "ADMIN":
        return ticket.status != S.CLOSED
    if user.role == "AGENT":
        return ticket.status != S.CLOSED and ticket.assigned_agent_id is None
    return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def create_ticket(*, customer, title, description, category=None, request=None):
    with transaction.atomic():
        now = timezone.now()
        ticket = Ticket.objects.create(
            title=title.strip(),
            description=description.strip(),
            customer=customer,
            category=category,
            priority=TicketPriority.MEDIUM,
            created_at=now,
            sla_due_at=compute_sla_due(now, TicketPriority.MEDIUM),
        )
        ticket.number = f"OPS-{ticket.pk:06d}"
        ticket.save(update_fields=["number"])
        TicketActivity.objects.create(
            ticket=ticket, actor=customer, action=TicketActivity.Action.CREATED, to_value=ticket.status, is_public=True
        )
        log_action(AuditAction.TICKET_CREATED, actor=customer, target=ticket,
                   description=f"Created {ticket.number}", request=request)
        mode = settings.AI_CLASSIFICATION_MODE
        if mode != "off":
            TicketAIInsight.objects.create(ticket=ticket, classification_status=TicketAIInsight.Status.PENDING)
        if mode == "thread":
            # Runs after COMMIT so the background thread can see the ticket. Ticket creation
            # never waits for (or fails because of) Gemini.
            transaction.on_commit(lambda: _start_background_classification(ticket.pk))

    if mode == "sync":
        from apps.ai.services import run_classification_safely

        run_classification_safely(ticket.pk)
    return ticket


def _start_background_classification(ticket_id):
    import threading

    from apps.ai.services import run_classification_safely

    threading.Thread(target=run_classification_safely, args=(ticket_id,), kwargs={"close_connection": True}, daemon=True,
                     name=f"classify-{ticket_id}").start()


def transition_ticket(*, ticket, user, to_status, request=None):
    if to_status not in S.values:
        raise ValidationError({"status": "Unknown status."})
    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        from_status = ticket.status
        if to_status == from_status:
            raise ValidationError({"status": f"Ticket is already {ticket.get_status_display()}."})
        if to_status not in allowed_transitions(ticket, user):
            raise ValidationError(
                {"status": f"Cannot move a ticket from {S(from_status).label} to {S(to_status).label}."}
            )
        now = timezone.now()
        update_fields = ["status", "updated_at"]
        ticket.status = to_status

        if to_status == S.RESOLVED:
            ticket.resolved_at = now
            update_fields.append("resolved_at")
        elif from_status == S.RESOLVED and to_status != S.CLOSED:
            ticket.resolved_at = None  # reopened
            update_fields.append("resolved_at")
        if to_status == S.CLOSED:
            ticket.closed_at = now
            update_fields.append("closed_at")

        # An agent starting work on an unassigned ticket takes ownership of it.
        if user.role == "AGENT" and to_status == S.IN_PROGRESS and ticket.assigned_agent_id is None:
            ticket.assigned_agent = user
            update_fields.append("assigned_agent")
            TicketActivity.objects.create(ticket=ticket, actor=user, action=TicketActivity.Action.ASSIGNED,
                                          to_value=user.full_name)
        ticket.save(update_fields=update_fields)
        TicketActivity.objects.create(
            ticket=ticket, actor=user, action=TicketActivity.Action.STATUS_CHANGED,
            from_value=from_status, to_value=to_status, is_public=True,
        )
        log_action(AuditAction.TICKET_STATUS_CHANGED, actor=user, target=ticket,
                   description=f"{ticket.number}: {from_status} -> {to_status}",
                   metadata={"from": from_status, "to": to_status}, request=request)
    return ticket


def assign_ticket(*, ticket, user, agent, request=None):
    from apps.accounts.models import User

    if not can_assign(ticket, user):
        raise PermissionDenied("You are not allowed to assign this ticket.")
    if agent is not None:
        if not agent.is_active or agent.role not in (User.Role.AGENT, User.Role.ADMIN):
            raise ValidationError({"agent_id": "Tickets can only be assigned to active agents or admins."})
        if user.role == "AGENT" and agent.pk != user.pk:
            raise PermissionDenied("Agents can only assign unassigned tickets to themselves.")
    elif user.role != "ADMIN":
        raise PermissionDenied("Only admins can unassign tickets.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        # Re-check under the row lock: another agent may have taken the ticket meanwhile.
        if not can_assign(ticket, user):
            raise PermissionDenied("This ticket was just assigned to someone else.")
        previous = ticket.assigned_agent
        if (previous and previous.pk) == (agent and agent.pk):
            return ticket
        ticket.assigned_agent = agent
        ticket.save(update_fields=["assigned_agent", "updated_at"])
        TicketActivity.objects.create(
            ticket=ticket, actor=user, action=TicketActivity.Action.ASSIGNED,
            from_value=previous.full_name if previous else "", to_value=agent.full_name if agent else "Unassigned",
        )
        log_action(AuditAction.TICKET_ASSIGNED, actor=user, target=ticket,
                   description=f"{ticket.number} assigned to {agent.email if agent else 'nobody'}",
                   metadata={"from": previous.pk if previous else None, "to": agent.pk if agent else None},
                   request=request)
    return ticket


def update_ticket(*, ticket, user, data, request=None):
    """Staff-only edits: priority, category, SLA deadline override."""
    if user.role not in ("ADMIN", "AGENT"):
        raise PermissionDenied("Only support staff can edit tickets.")
    if ticket.status == S.CLOSED:
        raise ValidationError({"detail": "Closed tickets cannot be edited."})

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        changes = {}
        if "priority" in data and data["priority"] != ticket.priority:
            changes["priority"] = (ticket.priority, data["priority"])
            TicketActivity.objects.create(ticket=ticket, actor=user, action=TicketActivity.Action.PRIORITY_CHANGED,
                                          from_value=ticket.priority, to_value=data["priority"], is_public=True)
            ticket.priority = data["priority"]
            if "sla_due_at" not in data:
                ticket.sla_due_at = compute_sla_due(ticket.created_at, ticket.priority)
        if "category" in data and data["category"] != ticket.category:
            old, new = ticket.category, data["category"]
            changes["category"] = (old.name if old else None, new.name if new else None)
            TicketActivity.objects.create(ticket=ticket, actor=user, action=TicketActivity.Action.CATEGORY_CHANGED,
                                          from_value=old.name if old else "", to_value=new.name if new else "")
            ticket.category = new
        if "sla_due_at" in data and data["sla_due_at"] != ticket.sla_due_at:
            due = data["sla_due_at"]
            if due is not None and due <= ticket.created_at:
                raise ValidationError({"sla_due_at": "The SLA deadline must be after the ticket was created."})
            changes["sla_due_at"] = (str(ticket.sla_due_at), str(due))
            TicketActivity.objects.create(ticket=ticket, actor=user, action=TicketActivity.Action.SLA_CHANGED,
                                          from_value=str(ticket.sla_due_at or ""), to_value=str(due or ""))
            ticket.sla_due_at = due
        if changes:
            ticket.save()
            log_action(AuditAction.TICKET_UPDATED, actor=user, target=ticket, description=f"Updated {ticket.number}",
                       metadata={k: [str(v[0]), str(v[1])] for k, v in changes.items()}, request=request)
    return ticket


def add_message(*, ticket, author, body, is_internal=False, is_ai_assisted=False):
    body = (body or "").strip()
    if not body:
        raise ValidationError({"body": "Message cannot be empty."})
    if author.role == "CUSTOMER" and is_internal:
        raise PermissionDenied("Customers cannot add internal notes.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        if ticket.status == S.CLOSED:
            raise ValidationError({"detail": "This ticket is closed. Please open a new ticket."})
        message = TicketMessage.objects.create(
            ticket=ticket, author=author, body=body, is_internal=is_internal, is_ai_assisted=is_ai_assisted
        )
        update_fields = ["updated_at"]
        if author.role != "CUSTOMER" and not is_internal and ticket.first_response_at is None:
            ticket.first_response_at = message.created_at
            update_fields.append("first_response_at")
        if author.role == "CUSTOMER" and ticket.status == S.WAITING_FOR_CUSTOMER:
            # The customer answered: put the ticket back in the agent's queue.
            ticket.status = S.IN_PROGRESS
            update_fields.append("status")
            TicketActivity.objects.create(ticket=ticket, actor=author, action=TicketActivity.Action.STATUS_CHANGED,
                                          from_value=S.WAITING_FOR_CUSTOMER, to_value=S.IN_PROGRESS, is_public=True)
        ticket.save(update_fields=update_fields)
        TicketActivity.objects.create(
            ticket=ticket, actor=author,
            action=TicketActivity.Action.NOTE_ADDED if is_internal else TicketActivity.Action.REPLIED,
            is_public=not is_internal,
        )
    return message


def publish_draft(*, draft, user, body, request=None):
    """An agent approves an AI draft (optionally edited). Only now does the customer see it."""
    with transaction.atomic():
        draft = ReplyDraft.objects.select_for_update().get(pk=draft.pk)
        if draft.status != ReplyDraft.Status.DRAFT:
            raise ValidationError({"detail": "This draft has already been published or discarded."})
        original_body = draft.body
        message = add_message(ticket=draft.ticket, author=user, body=body, is_internal=False, is_ai_assisted=True)
        draft.body = message.body
        draft.status = ReplyDraft.Status.PUBLISHED
        draft.published_message = message
        draft.decided_at = timezone.now()
        draft.save()
        TicketActivity.objects.create(ticket=draft.ticket, actor=user, action=TicketActivity.Action.AI_REPLY_PUBLISHED)
        log_action(AuditAction.AI_REPLY_PUBLISHED, actor=user, target=draft.ticket,
                   description=f"Published AI-assisted reply on {draft.ticket.number}",
                   metadata={"draft_id": draft.pk, "edited": message.body != original_body}, request=request)
    return message


def discard_draft(*, draft, user):
    with transaction.atomic():
        draft = ReplyDraft.objects.select_for_update().get(pk=draft.pk)
        if draft.status != ReplyDraft.Status.DRAFT:
            raise ValidationError({"detail": "This draft has already been published or discarded."})
        draft.status = ReplyDraft.Status.DISCARDED
        draft.decided_at = timezone.now()
        draft.save(update_fields=["status", "decided_at"])
    return draft
