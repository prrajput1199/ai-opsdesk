import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


def _client_ip(request):
    # REMOTE_ADDR is used deliberately: X-Forwarded-For can be spoofed unless a trusted proxy
    # rewrites it. Behind a known proxy, configure the proxy to set REMOTE_ADDR instead.
    return request.META.get("REMOTE_ADDR") if request is not None else None


def log_action(action, *, actor=None, target=None, description="", metadata=None, request=None):
    """
    Record an audit entry. Never raises: a failed audit write is logged but must not
    break the user's action. Do not pass secrets or message bodies in `metadata`.
    """
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    try:
        return AuditLog.objects.create(
            actor=actor,
            actor_email=getattr(actor, "email", "") or "",
            action=action,
            target_type=target.__class__.__name__ if target is not None else "",
            target_id=str(target.pk) if target is not None else "",
            description=description[:255],
            metadata=metadata or {},
            ip_address=_client_ip(request),
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to write audit log entry for action %s", action)
        return None
