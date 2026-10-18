from datetime import date, timedelta

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminRole, IsStaffRole
from apps.tickets.selectors import visible_tickets

from . import services

RANGE_PARAMS = [
    OpenApiParameter("date_from", OpenApiTypes.DATE, description="Inclusive start date (YYYY-MM-DD)"),
    OpenApiParameter("date_to", OpenApiTypes.DATE, description="Inclusive end date (YYYY-MM-DD)"),
]
MAX_RANGE_DAYS = 366


def parse_range(request, *, default_days=None):
    def _parse(name):
        raw = request.query_params.get(name)
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            raise ValidationError({name: "Use the format YYYY-MM-DD."})

    start, end = _parse("date_from"), _parse("date_to")
    today = timezone.localdate()
    if default_days:
        end = end or today
        start = start or end - timedelta(days=default_days - 1)
    if start and end:
        if start > end:
            raise ValidationError({"date_from": "date_from must be on or before date_to."})
        if (end - start).days >= MAX_RANGE_DAYS:
            raise ValidationError({"date_from": f"The range can be at most {MAX_RANGE_DAYS} days."})
    return services.DateRange(start, end)


class OverviewView(APIView):
    """Headline numbers, scoped to the tickets the current user can see (customers: their own)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(parameters=RANGE_PARAMS, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.overview(visible_tickets(request.user), parse_range(request)))


class TicketTrendsView(APIView):
    permission_classes = [IsStaffRole]

    @extend_schema(parameters=RANGE_PARAMS, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        """Tickets created and resolved per day (default: last 30 days)."""
        return Response(services.ticket_trends(visible_tickets(request.user), parse_range(request, default_days=30)))


class CategoryBreakdownView(APIView):
    permission_classes = [IsStaffRole]

    @extend_schema(parameters=RANGE_PARAMS, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.category_breakdown(visible_tickets(request.user), parse_range(request)))


class ResolutionTimeView(APIView):
    permission_classes = [IsStaffRole]

    @extend_schema(parameters=RANGE_PARAMS, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.resolution_time(visible_tickets(request.user), parse_range(request)))


class SLAView(APIView):
    permission_classes = [IsStaffRole]

    @extend_schema(parameters=RANGE_PARAMS, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.sla_report(visible_tickets(request.user), parse_range(request)))


class AgentWorkloadView(APIView):
    """Organisation-wide workload per agent: admins only."""

    permission_classes = [IsAdminRole]

    @extend_schema(parameters=RANGE_PARAMS, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.agent_workload(parse_range(request)))
