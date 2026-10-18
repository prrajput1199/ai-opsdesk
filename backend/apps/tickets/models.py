from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class TicketStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER", "Waiting for Customer"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"


ACTIVE_STATUSES = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_FOR_CUSTOMER]
DONE_STATUSES = [TicketStatus.RESOLVED, TicketStatus.CLOSED]


class TicketPriority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    URGENT = "URGENT", "Urgent"


PRIORITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "URGENT": 4}


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)
    # Tickets in this category are visible to every agent of this team.
    team = models.ForeignKey("accounts.Team", null=True, blank=True, on_delete=models.SET_NULL, related_name="categories")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class SLAPolicy(models.Model):
    """Target resolution time for each priority."""

    priority = models.CharField(max_length=10, choices=TicketPriority.choices, unique=True)
    resolution_hours = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["resolution_hours"]
        verbose_name = "SLA policy"
        verbose_name_plural = "SLA policies"
        constraints = [models.CheckConstraint(condition=Q(resolution_hours__gte=1), name="sla_hours_positive")]

    def __str__(self):
        return f"{self.priority}: {self.resolution_hours}h"


class Ticket(models.Model):
    number = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=5000)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tickets")
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tickets"
    )
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    priority = models.CharField(max_length=10, choices=TicketPriority.choices, default=TicketPriority.MEDIUM)
    status = models.CharField(max_length=24, choices=TicketStatus.choices, default=TicketStatus.OPEN)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["assigned_agent", "status"]),
            models.Index(fields=["sla_due_at"]),
            models.Index(fields=["resolved_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=TicketStatus.values), name="ticket_status_valid"),
            models.CheckConstraint(condition=Q(priority__in=TicketPriority.values), name="ticket_priority_valid"),
            models.CheckConstraint(
                condition=Q(resolved_at__isnull=True) | Q(resolved_at__gte=F("created_at")),
                name="ticket_resolved_after_created",
            ),
        ]

    def __str__(self):
        return f"{self.number or 'new'}: {self.title}"

    @property
    def is_active(self):
        return self.status in ACTIVE_STATUSES

    @property
    def sla_status(self):
        """
        - none:      no deadline
        - met:       resolved on or before the deadline
        - breached:  resolved after the deadline, or still active past it
        - at_risk:   active, less than 25% of the SLA window left
        - on_track:  active, plenty of time left
        """
        if not self.sla_due_at:
            return "none"
        if self.resolved_at:
            return "met" if self.resolved_at <= self.sla_due_at else "breached"
        if self.status == TicketStatus.CLOSED:
            return "none"
        now = timezone.now()
        if now > self.sla_due_at:
            return "breached"
        window = (self.sla_due_at - self.created_at).total_seconds()
        remaining = (self.sla_due_at - now).total_seconds()
        if window > 0 and remaining / window < 0.25:
            return "at_risk"
        return "on_track"


class TicketMessage(models.Model):
    """A public reply (visible to the customer) or an internal note (staff only)."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ticket_messages")
    body = models.TextField(max_length=5000)
    is_internal = models.BooleanField(default=False)
    # True when an agent published an AI-generated draft (after reviewing/editing it).
    is_ai_assisted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["ticket", "created_at"])]

    def __str__(self):
        return f"{'Note' if self.is_internal else 'Reply'} on {self.ticket_id} by {self.author_id}"


class TicketActivity(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        STATUS_CHANGED = "status_changed", "Status changed"
        PRIORITY_CHANGED = "priority_changed", "Priority changed"
        CATEGORY_CHANGED = "category_changed", "Category changed"
        ASSIGNED = "assigned", "Assigned"
        REPLIED = "replied", "Public reply"
        NOTE_ADDED = "note_added", "Internal note"
        SLA_CHANGED = "sla_changed", "SLA deadline changed"
        AI_CLASSIFIED = "ai_classified", "AI classification"
        AI_SUMMARIZED = "ai_summarized", "AI summary"
        AI_REPLY_PUBLISHED = "ai_reply_published", "AI-assisted reply published"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=32, choices=Action.choices)
    from_value = models.CharField(max_length=120, blank=True)
    to_value = models.CharField(max_length=120, blank=True)
    # Customers only see public activities (status changes, replies), never notes or AI events.
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "ticket activities"
        indexes = [models.Index(fields=["ticket", "-created_at"])]


class TicketAIInsight(models.Model):
    """Latest AI classification and summary for a ticket. Suggestions only - never applied automatically."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        UNAVAILABLE = "unavailable", "AI not configured"

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="ai_insight")
    classification_status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    suggested_category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    suggested_priority = models.CharField(max_length=10, choices=TicketPriority.choices, blank=True)
    suggested_first_response = models.TextField(blank=True)
    needs_human_review = models.BooleanField(default=True)
    classification_reason = models.CharField(max_length=500, blank=True)
    classified_at = models.DateTimeField(null=True, blank=True)

    summary = models.TextField(blank=True)
    summary_status = models.CharField(max_length=16, choices=Status.choices, blank=True)
    summary_updated_at = models.DateTimeField(null=True, blank=True)
    # Number of messages included when the summary was generated (to show "outdated" in the UI).
    summary_message_count = models.PositiveIntegerField(default=0)

    error_message = models.CharField(max_length=255, blank=True)
    model_name = models.CharField(max_length=80, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReplyDraft(models.Model):
    """An AI-generated reply. Customers never see it until an agent approves (publishes) it."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        DISCARDED = "discarded", "Discarded"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="reply_drafts")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.TextField(max_length=5000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    referenced_articles = models.ManyToManyField("knowledge_base.KnowledgeBaseArticle", blank=True, related_name="+")
    published_message = models.OneToOneField(
        TicketMessage, null=True, blank=True, on_delete=models.SET_NULL, related_name="source_draft"
    )
    model_name = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
