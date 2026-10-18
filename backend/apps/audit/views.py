import django_filters
from rest_framework import serializers, viewsets

from apps.core.permissions import IsAdminRole

from .models import AuditAction, AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_email", "action", "action_label", "target_type",
            "target_id", "description", "metadata", "ip_address", "created_at",
        ]


class AuditLogFilter(django_filters.FilterSet):
    action = django_filters.ChoiceFilter(choices=AuditAction.choices)
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["action", "actor", "target_type", "target_id"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin-only, read-only. Audit entries cannot be edited or deleted through the API."""

    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]
    filterset_class = AuditLogFilter
    search_fields = ["actor_email", "description", "target_id"]
    ordering_fields = ["created_at"]
