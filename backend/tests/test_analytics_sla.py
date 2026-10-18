from datetime import timedelta

import pytest
from django.utils import timezone

from apps.tickets.models import SLAPolicy, Ticket
from apps.tickets.services import assign_ticket, compute_sla_due

pytestmark = pytest.mark.django_db


def _make(customer, *, hours_ago, priority="MEDIUM", status="OPEN", resolved_after=None, agent=None, category=None):
    created = timezone.now() - timedelta(hours=hours_ago)
    t = Ticket.objects.create(
        title="t", description="d" * 20, customer=customer, priority=priority, status=status, created_at=created,
        sla_due_at=compute_sla_due(created, priority), assigned_agent=agent, category=category,
    )
    if resolved_after is not None:
        t.resolved_at = created + timedelta(hours=resolved_after)
        t.save()
    return t


# ---------------------------------------------------------------------- SLA ---
def test_sla_due_uses_policy_table():
    now = timezone.now()
    assert compute_sla_due(now, "URGENT") == now + timedelta(hours=4)
    SLAPolicy.objects.filter(priority="URGENT").update(resolution_hours=2)
    assert compute_sla_due(now, "URGENT") == now + timedelta(hours=2)


@pytest.mark.parametrize("hours_ago,priority,status,resolved_after,expected", [
    (1, "MEDIUM", "OPEN", None, "on_track"),        # 72h window, 71h left
    (70, "MEDIUM", "OPEN", None, "at_risk"),        # 2h of 72h left (<25%)
    (80, "MEDIUM", "IN_PROGRESS", None, "breached"),
    (80, "MEDIUM", "RESOLVED", 10, "met"),
    (80, "MEDIUM", "RESOLVED", 75, "breached"),
])
def test_sla_status(customer, hours_ago, priority, status, resolved_after, expected):
    t = _make(customer, hours_ago=hours_ago, priority=priority, status=status, resolved_after=resolved_after)
    assert t.sla_status == expected


def test_overdue_filter(customer, admin_user, api):
    overdue = _make(customer, hours_ago=10, priority="URGENT")  # 4h SLA
    _make(customer, hours_ago=1, priority="URGENT")
    _make(customer, hours_ago=10, priority="URGENT", status="RESOLVED", resolved_after=2)
    res = api(admin_user).get("/api/v1/tickets/", {"sla": "overdue"})
    assert [t["id"] for t in res.data["results"]] == [overdue.id]


# ---------------------------------------------------------------- analytics ---
@pytest.fixture
def dataset(customer, other_customer, agent, categories):
    return {
        "open_urgent_overdue": _make(customer, hours_ago=10, priority="URGENT", agent=agent,
                                     category=categories["tech"]),
        "open_medium": _make(customer, hours_ago=2, category=categories["tech"]),
        "resolved_fast": _make(other_customer, hours_ago=50, status="RESOLVED", resolved_after=2,
                               category=categories["billing"], agent=agent),
        "resolved_slow": _make(other_customer, hours_ago=200, status="CLOSED", resolved_after=100,
                               category=categories["billing"], agent=agent),
        "closed_unresolved": _make(customer, hours_ago=30, status="CLOSED"),
    }


def test_overview_numbers(admin_user, dataset, api):
    data = api(admin_user).get("/api/v1/analytics/overview/").data
    assert data["total_tickets"] == 5
    assert data["open_tickets"] == 2 and data["resolved_tickets"] == 1 and data["closed_tickets"] == 2
    assert data["urgent_tickets"] == 1 and data["overdue_tickets"] == 1
    assert data["active_tickets"] == 2 and data["unassigned_active_tickets"] == 1
    # Average over the two tickets that have a resolution time: (2h + 100h) / 2. The ticket closed
    # without resolution is excluded.
    assert data["resolved_in_range"] == 2 and data["avg_resolution_hours"] == 51.0
    assert data["sla_compliance_rate"] == 50.0  # 2h within 72h; 100h breached 72h


def test_overview_is_scoped_for_customers(customer, dataset, api):
    data = api(customer).get("/api/v1/analytics/overview/").data
    assert data["total_tickets"] == 3  # only their own tickets


def test_overview_date_range(admin_user, dataset, api):
    today = timezone.localdate()
    data = api(admin_user).get("/api/v1/analytics/overview/", {"date_from": today.isoformat()}).data
    assert data["total_tickets"] <= 3
    assert api(admin_user).get("/api/v1/analytics/overview/", {"date_from": "2026-13-01"}).status_code == 400
    assert api(admin_user).get("/api/v1/analytics/overview/",
                               {"date_from": "2026-05-02", "date_to": "2026-05-01"}).status_code == 400
    assert api(admin_user).get("/api/v1/analytics/overview/",
                               {"date_from": "2024-01-01", "date_to": "2026-01-01"}).status_code == 400


def test_trends_fill_every_day(admin_user, dataset, api):
    data = api(admin_user).get("/api/v1/analytics/ticket-trends/").data
    assert len(data["series"]) == 30
    assert sum(d["created"] for d in data["series"]) == 5
    assert sum(d["resolved"] for d in data["series"]) == 2


def test_category_and_priority_breakdown(admin_user, dataset, api):
    data = api(admin_user).get("/api/v1/analytics/category-breakdown/").data
    by_name = {c["category"]: c for c in data["categories"]}
    assert by_name["Technical Issue"]["total"] == 2 and by_name["Technical Issue"]["active"] == 2
    assert by_name["Billing"]["avg_resolution_hours"] == 51.0
    assert by_name["Uncategorised"]["total"] == 1
    assert {p["priority"]: p["total"] for p in data["priorities"]}["URGENT"] == 1


def test_resolution_time_distribution(admin_user, dataset, api):
    data = api(admin_user).get("/api/v1/analytics/resolution-time/").data
    assert data["resolved_count"] == 2
    buckets = {b["bucket"]: b["count"] for b in data["distribution"]}
    assert buckets["≤ 4h"] == 1 and buckets["> 3 days"] == 1


def test_sla_report(admin_user, dataset, api):
    data = api(admin_user).get("/api/v1/analytics/sla/").data
    assert data["overdue"] == 1 and data["on_track"] == 1
    assert data["resolved_within_sla"] == 1 and data["resolved_breached"] == 1
    assert data["overdue_tickets"][0]["id"] == dataset["open_urgent_overdue"].id
    assert data["overdue_tickets"][0]["hours_overdue"] >= 5.9


def test_agent_workload(admin_user, agent, billing_agent, dataset, api):
    rows = {r["email"]: r for r in api(admin_user).get("/api/v1/analytics/agent-workload/").data["agents"]}
    assert rows[agent.email]["active"] == 1 and rows[agent.email]["overdue"] == 1
    assert rows[agent.email]["urgent"] == 1 and rows[agent.email]["resolved_in_range"] == 2
    assert rows[billing_agent.email]["active"] == 0


def test_agent_analytics_are_scoped_to_visible_tickets(billing_agent, dataset, api):
    data = api(billing_agent).get("/api/v1/analytics/overview/").data
    # Billing agent sees billing-category tickets and the uncategorised shared queue ticket.
    assert data["total_tickets"] == 3


def test_analytics_queries_are_bounded(admin_user, dataset, api, django_assert_max_num_queries, customer, agent):
    for _ in range(10):
        assign_ticket(ticket=_make(customer, hours_ago=3), user=admin_user, agent=agent)
    with django_assert_max_num_queries(3):
        api(admin_user).get("/api/v1/analytics/agent-workload/")
    with django_assert_max_num_queries(4):
        api(admin_user).get("/api/v1/analytics/overview/")
