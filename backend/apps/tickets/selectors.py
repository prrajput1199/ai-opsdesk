"""Who can see which tickets. Every ticket endpoint starts from `visible_tickets(user)`."""

from django.db.models import Case, IntegerField, Q, Value, When

from .models import Ticket


def visible_tickets(user):
    """
    - Admin: every ticket.
    - Agent: tickets assigned to them, tickets in categories routed to their team, and
      unassigned tickets that are not routed to any team (the shared queue).
    - Customer: only tickets they created.

    Objects outside this queryset return 404 (not 403), so IDs of other users' tickets
    cannot even be confirmed to exist.
    """
    qs = Ticket.objects.all()
    role = getattr(user, "role", None)
    if role == "ADMIN":
        return qs
    if role == "AGENT":
        condition = Q(assigned_agent=user) | Q(assigned_agent__isnull=True, category__team__isnull=True)
        if user.team_id:
            condition |= Q(category__team_id=user.team_id)
        return qs.filter(condition)
    if role == "CUSTOMER":
        return qs.filter(customer=user)
    return qs.none()


def with_priority_rank(qs):
    """Annotate a sortable priority (LOW=1 ... URGENT=4)."""
    return qs.annotate(
        priority_rank=Case(
            When(priority="LOW", then=Value(1)),
            When(priority="MEDIUM", then=Value(2)),
            When(priority="HIGH", then=Value(3)),
            When(priority="URGENT", then=Value(4)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )
