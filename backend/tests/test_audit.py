import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.tickets.services import assign_ticket

pytestmark = pytest.mark.django_db


def test_audit_log_records_actions_and_is_admin_readable(customer, agent, admin_user, make_ticket, api):
    ticket = make_ticket(customer)
    assign_ticket(ticket=ticket, user=admin_user, agent=agent)

    res = api(admin_user).get("/api/v1/audit-logs/", {"action": AuditAction.TICKET_ASSIGNED})
    assert res.status_code == 200 and res.data["count"] == 1
    entry = res.data["results"][0]
    assert entry["actor_email"] == admin_user.email and entry["target_id"] == str(ticket.id)

    assert api(admin_user).get("/api/v1/audit-logs/", {"search": ticket.number}).data["count"] >= 1


def test_audit_log_is_read_only(admin_user, api):
    entry = AuditLog.objects.create(action=AuditAction.LOGIN, description="x")
    client = api(admin_user)
    assert client.post("/api/v1/audit-logs/", {"action": "auth.login"}, format="json").status_code == 405
    assert client.delete(f"/api/v1/audit-logs/{entry.id}/").status_code == 405
    assert client.patch(f"/api/v1/audit-logs/{entry.id}/", {"description": "y"}, format="json").status_code == 405


def test_user_management_is_audited(admin_user, agent, api):
    api(admin_user).patch(f"/api/v1/users/{agent.id}/", {"is_active": False}, format="json")
    api(admin_user).patch(f"/api/v1/users/{agent.id}/", {"is_active": True}, format="json")
    api(admin_user).patch(f"/api/v1/users/{agent.id}/", {"first_name": "Renamed"}, format="json")
    actions = list(AuditLog.objects.filter(target_type="User").values_list("action", flat=True))
    assert AuditAction.USER_DEACTIVATED in actions
    assert AuditAction.USER_ACTIVATED in actions
    assert AuditAction.USER_UPDATED in actions


def test_audit_never_stores_passwords(customer):
    from rest_framework.test import APIClient

    APIClient().post("/api/v1/auth/login/", {"email": customer.email, "password": "secret-guess-123"}, format="json")
    for entry in AuditLog.objects.all():
        assert "secret-guess-123" not in str(entry.metadata) + entry.description


def test_health_endpoint_is_public():
    from rest_framework.test import APIClient

    res = APIClient().get("/api/v1/health/")
    assert res.status_code == 200 and res.data["database"] == "ok"


def test_openapi_schema_is_served(admin_user, api):
    res = api(admin_user).get("/api/v1/schema/")
    assert res.status_code == 200


def test_security_headers_present(customer, api):
    res = api(customer).get("/api/v1/auth/me/")
    assert res["X-Content-Type-Options"] == "nosniff"
    assert res["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in res["Content-Security-Policy"]
    assert res["Cache-Control"] == "no-store"


def test_unexpected_errors_return_generic_json(admin_user, api, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("database password is hunter2")

    monkeypatch.setattr("apps.analytics.services.overview", boom)
    res = api(admin_user).get("/api/v1/analytics/overview/")
    assert res.status_code == 500
    assert "hunter2" not in str(res.data) and "unexpected error" in res.data["detail"]


def test_unknown_api_url_returns_json_404():
    from rest_framework.test import APIClient

    res = APIClient().get("/api/v1/does-not-exist/")
    assert res.status_code == 404 and res.json() == {"detail": "Not found."}
