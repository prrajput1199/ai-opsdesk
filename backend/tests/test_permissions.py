"""Role-based access and insecure-direct-object-reference (IDOR) tests."""

import pytest

from apps.tickets.services import add_message, assign_ticket

pytestmark = pytest.mark.django_db


def test_customer_cannot_read_another_customers_ticket(customer, other_customer, make_ticket, api):
    ticket = make_ticket(other_customer)
    client = api(customer)
    base = f"/api/v1/tickets/{ticket.id}/"
    assert client.get(base).status_code == 404
    assert client.get(base + "comments/").status_code == 404
    assert client.post(base + "comments/", {"body": "hi"}, format="json").status_code == 404
    assert client.get(base + "activities/").status_code == 404
    assert client.post(base + "transition/", {"status": "CLOSED"}, format="json").status_code == 404
    ids = [t["id"] for t in client.get("/api/v1/tickets/").data["results"]]
    assert ticket.id not in ids


def test_customer_never_sees_internal_notes(customer, agent, make_ticket, api):
    ticket = make_ticket(customer)
    add_message(ticket=ticket, author=agent, body="Public answer")
    add_message(ticket=ticket, author=agent, body="Secret internal note", is_internal=True)

    bodies = [m["body"] for m in api(customer).get(f"/api/v1/tickets/{ticket.id}/comments/").data]
    assert bodies == ["Public answer"]
    staff_bodies = [m["body"] for m in api(agent).get(f"/api/v1/tickets/{ticket.id}/comments/").data]
    assert "Secret internal note" in staff_bodies

    actions = [a["action"] for a in api(customer).get(f"/api/v1/tickets/{ticket.id}/activities/").data]
    assert "note_added" not in actions and "ai_classified" not in actions


def test_customer_cannot_post_internal_note(customer, make_ticket, api):
    ticket = make_ticket(customer)
    res = api(customer).post(f"/api/v1/tickets/{ticket.id}/comments/", {"body": "x", "is_internal": True},
                             format="json")
    assert res.status_code == 403


def test_customer_cannot_assign_or_edit_priority(customer, agent, make_ticket, api):
    ticket = make_ticket(customer)
    client = api(customer)
    assert client.post(f"/api/v1/tickets/{ticket.id}/assign/", {"agent_id": agent.id}, format="json").status_code == 403
    assert client.patch(f"/api/v1/tickets/{ticket.id}/", {"priority": "URGENT"}, format="json").status_code == 403
    ticket.refresh_from_db()
    assert ticket.priority == "MEDIUM" and ticket.assigned_agent is None


def test_customer_cannot_use_ai_or_see_ai_insight(customer, make_ticket, api):
    ticket = make_ticket(customer)
    client = api(customer)
    assert client.get(f"/api/v1/tickets/{ticket.id}/").data["ai_insight"] is None
    assert client.post(f"/api/v1/tickets/{ticket.id}/suggest-reply/").status_code == 403
    assert client.post(f"/api/v1/tickets/{ticket.id}/summarize/").status_code == 403
    assert client.get(f"/api/v1/tickets/{ticket.id}/drafts/").status_code == 403


def test_staff_cannot_create_tickets_as_customer(agent, api):
    res = api(agent).post("/api/v1/tickets/", {"title": "Hello there", "description": "Long enough text here"},
                          format="json")
    assert res.status_code == 403


def test_agent_visibility_is_limited_to_team_and_assignment(customer, agent, billing_agent, make_ticket, api):
    tech = make_ticket(customer, category="tech")
    billing = make_ticket(customer, category="billing", title="Refund my duplicate charge")
    general = make_ticket(customer, category="general", title="General question here")

    tech_ids = {t["id"] for t in api(agent).get("/api/v1/tickets/").data["results"]}
    assert tech.id in tech_ids and general.id in tech_ids and billing.id not in tech_ids
    assert api(agent).get(f"/api/v1/tickets/{billing.id}/").status_code == 404

    # Once someone takes the shared-queue ticket, other teams' agents lose access to it.
    assign_ticket(ticket=general, user=billing_agent, agent=billing_agent)
    assert api(agent).get(f"/api/v1/tickets/{general.id}/").status_code == 404
    assert api(billing_agent).get(f"/api/v1/tickets/{general.id}/").status_code == 200


def test_admin_sees_all_tickets(customer, other_customer, admin_user, make_ticket, api):
    a, b = make_ticket(customer), make_ticket(other_customer, category="billing")
    ids = {t["id"] for t in api(admin_user).get("/api/v1/tickets/").data["results"]}
    assert {a.id, b.id} <= ids


@pytest.mark.parametrize("url", [
    "/api/v1/users/", "/api/v1/audit-logs/", "/api/v1/analytics/agent-workload/",
])
def test_admin_only_endpoints(url, customer, agent, admin_user, api):
    assert api(customer).get(url).status_code == 403
    assert api(agent).get(url).status_code == 403
    assert api(admin_user).get(url).status_code == 200


@pytest.mark.parametrize("url", [
    "/api/v1/analytics/ticket-trends/", "/api/v1/analytics/category-breakdown/", "/api/v1/analytics/sla/",
    "/api/v1/analytics/resolution-time/", "/api/v1/agents/",
])
def test_staff_only_endpoints(url, customer, agent, api):
    assert api(customer).get(url).status_code == 403
    assert api(agent).get(url).status_code == 200


def test_only_admin_can_manage_categories_and_sla(customer, agent, admin_user, api):
    payload = {"name": "New category"}
    assert api(customer).post("/api/v1/categories/", payload, format="json").status_code == 403
    assert api(agent).post("/api/v1/categories/", payload, format="json").status_code == 403
    assert api(admin_user).post("/api/v1/categories/", payload, format="json").status_code == 201
    from apps.tickets.models import SLAPolicy

    policy = SLAPolicy.objects.get(priority="URGENT")
    assert api(agent).patch(f"/api/v1/sla-policies/{policy.id}/", {"resolution_hours": 2}, format="json").status_code == 403
    assert api(admin_user).patch(f"/api/v1/sla-policies/{policy.id}/", {"resolution_hours": 2},
                                 format="json").status_code == 200


def test_admin_user_management(admin_user, agent, api, teams):
    client = api(admin_user)
    res = client.post("/api/v1/users/", {"email": "new.agent@example.com", "first_name": "New", "last_name": "Agent",
                                         "role": "AGENT", "team_id": teams["tech"].id, "password": "Ag3nt-Strong!pw"},
                      format="json")
    assert res.status_code == 201 and res.data["role"] == "AGENT"

    # Admins cannot create customers through this endpoint or set arbitrary roles.
    res = client.post("/api/v1/users/", {"email": "c@example.com", "first_name": "C", "last_name": "D",
                                         "role": "CUSTOMER", "password": "Ag3nt-Strong!pw"}, format="json")
    assert res.status_code == 400

    res = client.patch(f"/api/v1/users/{agent.id}/", {"is_active": False}, format="json")
    assert res.status_code == 200 and res.data["is_active"] is False

    res = client.patch(f"/api/v1/users/{admin_user.id}/", {"is_active": False}, format="json")
    assert res.status_code == 400  # cannot deactivate yourself


def test_deactivated_user_loses_access_immediately(agent, admin_user):
    from django.conf import settings
    from rest_framework.test import APIClient

    from .conftest import PASSWORD

    client = APIClient()
    client.post("/api/v1/auth/login/", {"email": agent.email, "password": PASSWORD}, format="json")
    assert client.get("/api/v1/auth/me/").status_code == 200
    agent.is_active = False
    agent.save()
    assert client.get("/api/v1/auth/me/").status_code == 401
    assert client.post("/api/v1/auth/refresh/").status_code == 401
    assert settings.AUTH_COOKIE_ACCESS
