"""
Analytics computed with database aggregation (COUNT/AVG/GROUP BY in PostgreSQL).

Definitions
-----------
- Resolution time = resolved_at - created_at, only for tickets that have a resolved_at
  (status Resolved, or Closed after being resolved). Unresolved tickets and tickets closed
  without a resolution are excluded from averages - they have no resolution time yet.
  If a ticket is reopened and resolved again, the latest resolution counts.
- First response time = first public staff reply - created_at.
- Overdue = active (Open / In Progress / Waiting) and past its SLA deadline right now.
- SLA met / breached = resolved on/before vs after the deadline.
- Date ranges filter "created" metrics by created_at and "resolved" metrics by resolved_at.
"""

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import User
from apps.tickets.models import ACTIVE_STATUSES, SLAPolicy, TicketPriority, TicketStatus

RESOLUTION = ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField())
FIRST_RESPONSE = ExpressionWrapper(F("first_response_at") - F("created_at"), output_field=DurationField())


def _hours(duration):
    return round(duration.total_seconds() / 3600, 1) if duration is not None else None


def _pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


class DateRange:
    def __init__(self, start: date | None, end: date | None):
        self.start, self.end = start, end
        tz = timezone.get_current_timezone()
        self.start_dt = timezone.make_aware(datetime.combine(start, time.min), tz) if start else None
        self.end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz) if end else None

    def q(self, field):
        cond = Q()
        if self.start_dt:
            cond &= Q(**{f"{field}__gte": self.start_dt})
        if self.end_dt:
            cond &= Q(**{f"{field}__lt": self.end_dt})
        return cond

    def as_dict(self):
        return {"date_from": self.start.isoformat() if self.start else None,
                "date_to": self.end.isoformat() if self.end else None}


def overview(tickets, rng: DateRange):
    now = timezone.now()
    created = tickets.filter(rng.q("created_at"))
    counts = created.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status=TicketStatus.OPEN)),
        in_progress=Count("id", filter=Q(status=TicketStatus.IN_PROGRESS)),
        waiting_for_customer=Count("id", filter=Q(status=TicketStatus.WAITING_FOR_CUSTOMER)),
        resolved=Count("id", filter=Q(status=TicketStatus.RESOLVED)),
        closed=Count("id", filter=Q(status=TicketStatus.CLOSED)),
        urgent=Count("id", filter=Q(priority=TicketPriority.URGENT)),
        avg_first_response=Avg(FIRST_RESPONSE, filter=Q(first_response_at__isnull=False)),
    )
    # "Right now" numbers are not limited by the date range.
    current = tickets.aggregate(
        active=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
        urgent_active=Count("id", filter=Q(status__in=ACTIVE_STATUSES, priority=TicketPriority.URGENT)),
        unassigned_active=Count("id", filter=Q(status__in=ACTIVE_STATUSES, assigned_agent__isnull=True)),
        overdue=Count("id", filter=Q(status__in=ACTIVE_STATUSES, sla_due_at__lt=now)),
    )
    resolved = tickets.filter(rng.q("resolved_at"), resolved_at__isnull=False).aggregate(
        count=Count("id"),
        avg=Avg(RESOLUTION),
        met=Count("id", filter=Q(sla_due_at__isnull=False, resolved_at__lte=F("sla_due_at"))),
        breached=Count("id", filter=Q(sla_due_at__isnull=False, resolved_at__gt=F("sla_due_at"))),
    )
    return {
        "range": rng.as_dict(),
        "total_tickets": counts["total"],
        "open_tickets": counts["open"],
        "in_progress_tickets": counts["in_progress"],
        "waiting_for_customer_tickets": counts["waiting_for_customer"],
        "resolved_tickets": counts["resolved"],
        "closed_tickets": counts["closed"],
        "urgent_tickets": counts["urgent"],
        "active_tickets": current["active"],
        "urgent_active_tickets": current["urgent_active"],
        "unassigned_active_tickets": current["unassigned_active"],
        "overdue_tickets": current["overdue"],
        "resolved_in_range": resolved["count"],
        "avg_resolution_hours": _hours(resolved["avg"]),
        "avg_first_response_hours": _hours(counts["avg_first_response"]),
        "sla_compliance_rate": _pct(resolved["met"], resolved["met"] + resolved["breached"]),
    }


def ticket_trends(tickets, rng: DateRange):
    created = dict(
        tickets.filter(rng.q("created_at")).annotate(day=TruncDate("created_at")).values("day")
        .annotate(n=Count("id")).values_list("day", "n")
    )
    resolved = dict(
        tickets.filter(rng.q("resolved_at"), resolved_at__isnull=False).annotate(day=TruncDate("resolved_at"))
        .values("day").annotate(n=Count("id")).values_list("day", "n")
    )
    days = []
    day = rng.start
    while day <= rng.end:
        days.append({"date": day.isoformat(), "created": created.get(day, 0), "resolved": resolved.get(day, 0)})
        day += timedelta(days=1)
    return {"range": rng.as_dict(), "series": days}


def category_breakdown(tickets, rng: DateRange):
    rows = (
        tickets.filter(rng.q("created_at"))
        .values("category_id", "category__name")
        .annotate(
            total=Count("id"),
            active=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
            avg_resolution=Avg(RESOLUTION, filter=Q(resolved_at__isnull=False)),
        )
        .order_by("-total")
    )
    by_priority = dict(
        tickets.filter(rng.q("created_at")).values("priority").annotate(n=Count("id")).values_list("priority", "n")
    )
    return {
        "range": rng.as_dict(),
        "categories": [
            {
                "category_id": r["category_id"],
                "category": r["category__name"] or "Uncategorised",
                "total": r["total"],
                "active": r["active"],
                "avg_resolution_hours": _hours(r["avg_resolution"]),
            }
            for r in rows
        ],
        "priorities": [
            {"priority": p.value, "label": p.label, "total": by_priority.get(p.value, 0)} for p in TicketPriority
        ],
    }


def resolution_time(tickets, rng: DateRange):
    resolved = tickets.filter(rng.q("resolved_at"), resolved_at__isnull=False).annotate(duration=RESOLUTION)
    overall = resolved.aggregate(
        count=Count("id"),
        avg=Avg("duration"),
        under_4h=Count("id", filter=Q(duration__lte=timedelta(hours=4))),
        under_24h=Count("id", filter=Q(duration__gt=timedelta(hours=4), duration__lte=timedelta(hours=24))),
        under_72h=Count("id", filter=Q(duration__gt=timedelta(hours=24), duration__lte=timedelta(hours=72))),
        over_72h=Count("id", filter=Q(duration__gt=timedelta(hours=72))),
    )
    per_priority = {
        r["priority"]: r for r in resolved.values("priority").annotate(n=Count("id"), avg=Avg("duration"))
    }
    return {
        "range": rng.as_dict(),
        "definition": "resolved_at - created_at for tickets resolved in the range; unresolved tickets are excluded.",
        "resolved_count": overall["count"],
        "avg_resolution_hours": _hours(overall["avg"]),
        "distribution": [
            {"bucket": "≤ 4h", "count": overall["under_4h"]},
            {"bucket": "4–24h", "count": overall["under_24h"]},
            {"bucket": "1–3 days", "count": overall["under_72h"]},
            {"bucket": "> 3 days", "count": overall["over_72h"]},
        ],
        "by_priority": [
            {
                "priority": p.value,
                "label": p.label,
                "resolved_count": per_priority.get(p.value, {}).get("n", 0),
                "avg_resolution_hours": _hours(per_priority.get(p.value, {}).get("avg")),
            }
            for p in TicketPriority
        ],
    }


def sla_report(tickets, rng: DateRange):
    now = timezone.now()
    active = tickets.filter(status__in=ACTIVE_STATUSES, sla_due_at__isnull=False)
    remaining = ExpressionWrapper(F("sla_due_at") - now, output_field=DurationField())
    quarter_window = ExpressionWrapper((F("sla_due_at") - F("created_at")) / 4, output_field=DurationField())
    current = active.annotate(remaining=remaining, quarter=quarter_window).aggregate(
        overdue=Count("id", filter=Q(sla_due_at__lt=now)),
        at_risk=Count("id", filter=Q(sla_due_at__gte=now, remaining__lt=F("quarter"))),
        on_track=Count("id", filter=Q(sla_due_at__gte=now, remaining__gte=F("quarter"))),
    )
    resolved = tickets.filter(rng.q("resolved_at"), resolved_at__isnull=False, sla_due_at__isnull=False).aggregate(
        met=Count("id", filter=Q(resolved_at__lte=F("sla_due_at"))),
        breached=Count("id", filter=Q(resolved_at__gt=F("sla_due_at"))),
    )
    by_priority = {
        r["priority"]: r["n"]
        for r in active.filter(sla_due_at__lt=now).values("priority").annotate(n=Count("id"))
    }
    overdue_list = (
        active.filter(sla_due_at__lt=now).select_related("assigned_agent").order_by("sla_due_at")[:10]
    )
    policies = {p.priority: p.resolution_hours for p in SLAPolicy.objects.all()}
    return {
        "range": rng.as_dict(),
        "overdue": current["overdue"],
        "at_risk": current["at_risk"],
        "on_track": current["on_track"],
        "resolved_within_sla": resolved["met"],
        "resolved_breached": resolved["breached"],
        "compliance_rate": _pct(resolved["met"], resolved["met"] + resolved["breached"]),
        "overdue_by_priority": [{"priority": p.value, "label": p.label, "count": by_priority.get(p.value, 0)}
                                for p in TicketPriority],
        "policies": [{"priority": p.value, "label": p.label,
                      "resolution_hours": policies.get(p.value, settings.DEFAULT_SLA_HOURS[p.value])}
                     for p in TicketPriority],
        "overdue_tickets": [
            {
                "id": t.id, "number": t.number, "title": t.title, "priority": t.priority, "status": t.status,
                "sla_due_at": t.sla_due_at, "hours_overdue": _hours(now - t.sla_due_at),
                "assigned_agent": t.assigned_agent.full_name if t.assigned_agent else None,
            }
            for t in overdue_list
        ],
    }


def agent_workload(rng: DateRange):
    now = timezone.now()
    t = "assigned_tickets__"
    resolution = ExpressionWrapper(F(f"{t}resolved_at") - F(f"{t}created_at"), output_field=DurationField())
    resolved_in_range = Q(**{f"{t}resolved_at__isnull": False})
    if rng.start_dt:
        resolved_in_range &= Q(**{f"{t}resolved_at__gte": rng.start_dt})
    if rng.end_dt:
        resolved_in_range &= Q(**{f"{t}resolved_at__lt": rng.end_dt})

    agents = (
        User.objects.filter(role=User.Role.AGENT, is_active=True)
        .select_related("team")
        .annotate(
            active=Count("assigned_tickets", filter=Q(**{f"{t}status__in": ACTIVE_STATUSES})),
            in_progress=Count("assigned_tickets", filter=Q(**{f"{t}status": TicketStatus.IN_PROGRESS})),
            waiting=Count("assigned_tickets", filter=Q(**{f"{t}status": TicketStatus.WAITING_FOR_CUSTOMER})),
            urgent=Count("assigned_tickets", filter=Q(**{f"{t}status__in": ACTIVE_STATUSES,
                                                         f"{t}priority": TicketPriority.URGENT})),
            overdue=Count("assigned_tickets", filter=Q(**{f"{t}status__in": ACTIVE_STATUSES,
                                                          f"{t}sla_due_at__lt": now})),
            resolved=Count("assigned_tickets", filter=resolved_in_range),
            avg_resolution=Avg(resolution, filter=resolved_in_range),
        )
        .order_by("-active", "first_name")
    )
    return {
        "range": rng.as_dict(),
        "agents": [
            {
                "id": a.id, "name": a.full_name, "email": a.email, "team": a.team.name if a.team else None,
                "active": a.active, "in_progress": a.in_progress, "waiting_for_customer": a.waiting,
                "urgent": a.urgent, "overdue": a.overdue, "resolved_in_range": a.resolved,
                "avg_resolution_hours": _hours(a.avg_resolution),
            }
            for a in agents
        ],
    }
