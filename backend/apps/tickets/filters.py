import django_filters
from django.db.models import Q
from django.utils import timezone

from .models import ACTIVE_STATUSES, Ticket, TicketPriority, TicketStatus


class TicketFilter(django_filters.FilterSet):
    """
    ?status=OPEN&status=IN_PROGRESS   (repeat for several values)
    ?priority=HIGH&category=2&assigned_agent=5 | assigned_agent=me | assigned_agent=unassigned
    ?created_after=2026-01-01&created_before=2026-01-31&sla=overdue
    """

    status = django_filters.MultipleChoiceFilter(choices=TicketStatus.choices)
    priority = django_filters.MultipleChoiceFilter(choices=TicketPriority.choices)
    category = django_filters.NumberFilter(field_name="category_id")
    assigned_agent = django_filters.CharFilter(method="filter_assigned_agent")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    sla = django_filters.ChoiceFilter(choices=[("overdue", "Overdue"), ("breached", "Breached")], method="filter_sla")

    class Meta:
        model = Ticket
        fields = ["status", "priority", "category"]

    def filter_assigned_agent(self, queryset, name, value):
        if value == "me":
            return queryset.filter(assigned_agent=self.request.user)
        if value == "unassigned":
            return queryset.filter(assigned_agent__isnull=True)
        if value.isdigit():
            return queryset.filter(assigned_agent_id=int(value))
        return queryset.none()

    def filter_sla(self, queryset, name, value):
        now = timezone.now()
        overdue = Q(status__in=ACTIVE_STATUSES, sla_due_at__lt=now)
        if value == "overdue":
            return queryset.filter(overdue)
        # breached = still overdue, or resolved after the deadline
        from django.db.models import F

        return queryset.filter(overdue | Q(resolved_at__isnull=False, resolved_at__gt=F("sla_due_at")))
