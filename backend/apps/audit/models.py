from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    LOGIN = "auth.login", "Logged in"
    LOGIN_FAILED = "auth.login_failed", "Failed login"
    LOGOUT = "auth.logout", "Logged out"
    REGISTER = "auth.register", "Registered"
    PASSWORD_CHANGED = "auth.password_changed", "Changed password"
    USER_CREATED = "user.created", "Created user"
    USER_UPDATED = "user.updated", "Updated user"
    USER_DEACTIVATED = "user.deactivated", "Deactivated user"
    USER_ACTIVATED = "user.activated", "Activated user"
    TICKET_CREATED = "ticket.created", "Created ticket"
    TICKET_UPDATED = "ticket.updated", "Updated ticket"
    TICKET_ASSIGNED = "ticket.assigned", "Assigned ticket"
    TICKET_STATUS_CHANGED = "ticket.status_changed", "Changed ticket status"
    AI_REPLY_PUBLISHED = "ai.reply_published", "Published AI-assisted reply"
    CATEGORY_CHANGED = "category.changed", "Changed category"
    SLA_POLICY_CHANGED = "sla.changed", "Changed SLA policy"
    TEAM_CHANGED = "team.changed", "Changed team"
    ARTICLE_CREATED = "kb.article_created", "Created article"
    ARTICLE_UPDATED = "kb.article_updated", "Updated article"
    ARTICLE_DELETED = "kb.article_deleted", "Deleted article"


class AuditLog(models.Model):
    """Append-only record of security-relevant and business-critical actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    # Snapshot so the log stays readable even if the user is later changed.
    actor_email = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=64, choices=AuditAction.choices)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_email or 'system'} {self.action}"
