from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditAction, AuditLog
from apps.tickets.models import Ticket, TicketActivity, TicketStatus
from apps.tickets.services import add_message, assign_ticket, transition_ticket

pytestmark = pytest.mark.django_db


def test_customer_creates_ticket(customer, categories, api):
    res = api(customer).post("/api/v1/tickets/", {
        "title": "Invoice is missing", "description": "I cannot find last month's invoice anywhere.",
        "category_id": categories["billing"].id,
    }, format="json")
    assert res.status_code == 201
    ticket = Ticket.objects.get(pk=res.data["id"])
    assert ticket.number == f"OPS-{ticket.pk:06d}"
    assert ticket.status == "OPEN" and ticket.priority == "MEDIUM"
    assert ticket.customer == customer
    assert ticket.sla_due_at == ticket.created_at + timedelta(hours=72)
    assert TicketActivity.objects.filter(ticket=ticket, action="created").exists()
    assert AuditLog.objects.filter(action=AuditAction.TICKET_CREATED, target_id=str(ticket.pk)).exists()


def test_create_ignores_protected_fields(customer, agent, api):
    res = api(customer).post("/api/v1/tickets/", {
        "title": "Please help me", "description": "Something is wrong with my account settings.",
        "status": "CLOSED", "priority": "URGENT", "assigned_agent": agent.id, "customer": 999,
    }, format="json")
    assert res.status_code == 201
    ticket = Ticket.objects.get(pk=res.data["id"])
    assert ticket.status == "OPEN" and ticket.priority == "MEDIUM"
    assert ticket.assigned_agent is None and ticket.customer == customer


@pytest.mark.parametrize("payload", [
    {"title": "Hi", "description": "A valid long description here."},
    {"title": "Valid title", "description": "short"},
    {"title": "Valid title", "description": "x" * 5001},
    {"description": "Missing title but long description"},
])
def test_create_validation(customer, api, payload):
    assert api(customer).post("/api/v1/tickets/", payload, format="json").status_code == 400


def test_create_rejects_inactive_category(customer, categories, api):
    categories["general"].is_active = False
    categories["general"].save()
    res = api(customer).post("/api/v1/tickets/", {"title": "Valid title", "description": "Long enough text here",
                                                  "category_id": categories["general"].id}, format="json")
    assert res.status_code == 400


def test_ticket_creation_succeeds_when_ai_fails(customer, api, fake_ai):
    from apps.ai.client import AIServiceError

    fake_ai.push(AIServiceError())
    res = api(customer).post("/api/v1/tickets/", {"title": "App is down", "description": "Nothing loads at all."},
                             format="json")
    assert res.status_code == 201
    assert res.data["ai_insight"] is None  # customers never see AI output
    assert Ticket.objects.get(pk=res.data["id"]).ai_insight.classification_status == "failed"


def test_list_filters_search_pagination_and_ordering(customer, agent, admin_user, make_ticket, api):
    t1 = make_ticket(customer, title="Login broken")
    t2 = make_ticket(customer, category="billing", title="Refund please")
    t3 = make_ticket(customer, category="general", title="Question about export")
    Ticket.objects.filter(pk=t2.pk).update(priority="URGENT")
    Ticket.objects.filter(pk=t3.pk).update(status="RESOLVED", resolved_at=timezone.now())
    assign_ticket(ticket=t1, user=admin_user, agent=agent)
    client = api(admin_user)

    def ids(params):
        return [t["id"] for t in client.get("/api/v1/tickets/", params).data["results"]]

    assert ids({"status": "RESOLVED"}) == [t3.id]
    assert set(ids({"status": ["OPEN", "RESOLVED"]})) == {t1.id, t2.id, t3.id}
    assert ids({"priority": "URGENT"}) == [t2.id]
    assert ids({"category": t2.category_id}) == [t2.id]
    assert ids({"assigned_agent": agent.id}) == [t1.id]
    assert set(ids({"assigned_agent": "unassigned"})) == {t2.id, t3.id}
    assert ids({"search": t1.number}) == [t1.id]
    assert ids({"search": "refund"}) == [t2.id]
    assert ids({"ordering": "-priority_rank"})[0] == t2.id
    assert ids({"created_after": (timezone.localdate() + timedelta(days=1)).isoformat()}) == []
    assert ids({"assigned_agent": "me"}) == []

    page = client.get("/api/v1/tickets/", {"page_size": 2}).data
    assert page["count"] == 3 and len(page["results"]) == 2 and page["next"]
    assert client.get("/api/v1/tickets/", {"status": "NOPE"}).status_code == 400


def test_list_has_no_n_plus_one(customer, admin_user, make_ticket, api, django_assert_max_num_queries):
    for i in range(8):
        t = make_ticket(customer, title=f"Ticket number {i}")
        add_message(ticket=t, author=customer, body="More info")
    client = api(admin_user)
    with django_assert_max_num_queries(4):  # count + page (+ throttle cache is in-memory)
        res = client.get("/api/v1/tickets/")
    assert res.data["count"] == 8 and res.data["results"][0]["message_count"] == 1


def test_valid_transitions_set_timestamps(customer, agent, make_ticket, api):
    ticket = make_ticket(customer)
    client = api(agent)
    url = f"/api/v1/tickets/{ticket.id}/transition/"

    res = client.post(url, {"status": "IN_PROGRESS"}, format="json")
    assert res.status_code == 200
    assert res.data["assigned_agent"]["id"] == agent.id  # agent took ownership

    res = client.post(url, {"status": "RESOLVED"}, format="json")
    assert res.status_code == 200 and res.data["resolved_at"]

    res = api(customer).post(url, {"status": "OPEN"}, format="json")  # customer reopens
    assert res.status_code == 200 and res.data["resolved_at"] is None

    client.post(url, {"status": "RESOLVED"}, format="json")
    res = api(customer).post(url, {"status": "CLOSED"}, format="json")
    assert res.status_code == 200 and res.data["closed_at"] and res.data["allowed_transitions"] == []


@pytest.mark.parametrize("start,target,role", [
    ("CLOSED", "OPEN", "agent"),
    ("CLOSED", "IN_PROGRESS", "agent"),
    ("OPEN", "OPEN", "agent"),
    ("OPEN", "RESOLVED", "customer"),
    ("IN_PROGRESS", "WAITING_FOR_CUSTOMER", "customer"),
    ("WAITING_FOR_CUSTOMER", "OPEN", "agent"),
])
def test_invalid_transitions_rejected(customer, agent, make_ticket, api, start, target, role):
    ticket = make_ticket(customer)
    Ticket.objects.filter(pk=ticket.pk).update(status=start)
    user = agent if role == "agent" else customer
    res = api(user).post(f"/api/v1/tickets/{ticket.id}/transition/", {"status": target}, format="json")
    assert res.status_code == 400
    ticket.refresh_from_db()
    assert ticket.status == start


def test_status_change_is_audited(customer, agent, make_ticket):
    ticket = make_ticket(customer)
    transition_ticket(ticket=ticket, user=agent, to_status="WAITING_FOR_CUSTOMER")
    log = AuditLog.objects.get(action=AuditAction.TICKET_STATUS_CHANGED)
    assert log.actor == agent and log.metadata == {"from": "OPEN", "to": "WAITING_FOR_CUSTOMER"}


def test_assignment_rules(customer, agent, billing_agent, admin_user, make_ticket, api):
    ticket = make_ticket(customer, category="general")
    url = f"/api/v1/tickets/{ticket.id}/assign/"
    # Agent can't assign to someone else
    assert api(agent).post(url, {"agent_id": billing_agent.id}, format="json").status_code == 403
    # Agent can take an unassigned ticket
    assert api(agent).post(url, {"agent_id": agent.id}, format="json").status_code == 200
    # ...but cannot re-take it once assigned (only admins reassign)
    assert api(billing_agent).post(url, {"agent_id": billing_agent.id}, format="json").status_code == 404
    # Admin reassigns, cannot assign to a customer
    assert api(admin_user).post(url, {"agent_id": customer.id}, format="json").status_code == 400
    res = api(admin_user).post(url, {"agent_id": billing_agent.id}, format="json")
    assert res.status_code == 200 and res.data["assigned_agent"]["id"] == billing_agent.id
    assert AuditLog.objects.filter(action=AuditAction.TICKET_ASSIGNED, target_id=str(ticket.id)).count() == 2
    res = api(admin_user).post(url, {"agent_id": None}, format="json")
    assert res.status_code == 200 and res.data["assigned_agent"] is None


def test_staff_updates_priority_and_sla_is_recomputed(customer, agent, make_ticket, api):
    ticket = make_ticket(customer)
    res = api(agent).patch(f"/api/v1/tickets/{ticket.id}/", {"priority": "URGENT"}, format="json")
    assert res.status_code == 200
    ticket.refresh_from_db()
    assert ticket.priority == "URGENT"
    assert ticket.sla_due_at == ticket.created_at + timedelta(hours=4)
    assert TicketActivity.objects.filter(ticket=ticket, action="priority_changed").exists()

    bad = api(agent).patch(f"/api/v1/tickets/{ticket.id}/",
                           {"sla_due_at": (ticket.created_at - timedelta(hours=1)).isoformat()}, format="json")
    assert bad.status_code == 400


def test_messages_update_response_time_and_waiting_status(customer, agent, make_ticket, api):
    ticket = make_ticket(customer)
    api(agent).post(f"/api/v1/tickets/{ticket.id}/comments/", {"body": "Internal", "is_internal": True}, format="json")
    ticket.refresh_from_db()
    assert ticket.first_response_at is None  # internal notes are not a response to the customer

    res = api(agent).post(f"/api/v1/tickets/{ticket.id}/comments/", {"body": "Can you send a screenshot?"},
                          format="json")
    assert res.status_code == 201
    transition_ticket(ticket=ticket, user=agent, to_status="WAITING_FOR_CUSTOMER")
    api(customer).post(f"/api/v1/tickets/{ticket.id}/comments/", {"body": "Here it is"}, format="json")
    ticket.refresh_from_db()
    assert ticket.first_response_at is not None
    assert ticket.status == TicketStatus.IN_PROGRESS


def test_closed_ticket_rejects_messages_and_edits(customer, agent, make_ticket, api):
    ticket = make_ticket(customer)
    transition_ticket(ticket=ticket, user=agent, to_status="CLOSED")
    assert api(customer).post(f"/api/v1/tickets/{ticket.id}/comments/", {"body": "hello"},
                              format="json").status_code == 400
    assert api(agent).patch(f"/api/v1/tickets/{ticket.id}/", {"priority": "HIGH"}, format="json").status_code == 400


def test_empty_message_rejected(customer, make_ticket, api):
    ticket = make_ticket(customer)
    assert api(customer).post(f"/api/v1/tickets/{ticket.id}/comments/", {"body": "   "},
                              format="json").status_code == 400


def test_detail_includes_permission_flags(customer, agent, make_ticket, api):
    ticket = make_ticket(customer)
    cust = api(customer).get(f"/api/v1/tickets/{ticket.id}/").data
    assert cust["permissions"]["can_add_internal_note"] is False
    assert cust["allowed_transitions"] == ["CLOSED"]
    staff = api(agent).get(f"/api/v1/tickets/{ticket.id}/").data
    assert staff["permissions"]["can_add_internal_note"] is True and staff["permissions"]["can_assign"] is True
    assert staff["ai_insight"]["classification_status"] == "completed"


def test_stale_self_assignment_is_rejected(customer, agent, make_ticket, teams):
    """Two agents load the same unassigned ticket; the second self-assignment must fail."""
    from django.core.exceptions import PermissionDenied

    from apps.accounts.models import User

    other = User.objects.create_user(email="agent2@example.com", password="x", role="AGENT", team=teams["tech"])
    ticket = make_ticket(customer)
    stale_copy = Ticket.objects.get(pk=ticket.pk)  # loaded before the first assignment
    assign_ticket(ticket=ticket, user=agent, agent=agent)
    with pytest.raises(PermissionDenied):
        assign_ticket(ticket=stale_copy, user=other, agent=other)
    ticket.refresh_from_db()
    assert ticket.assigned_agent == agent
