"""
Serializers are split by purpose (list / detail / create / update) so each endpoint only
accepts the fields that role may set. This prevents mass assignment: e.g. a customer
posting {"status": "CLOSED", "assigned_agent": 3} to the create endpoint is simply ignored.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserSummarySerializer

from . import services
from .models import (
    Category,
    ReplyDraft,
    SLAPolicy,
    Ticket,
    TicketActivity,
    TicketAIInsight,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)


class CategorySerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True, default=None)

    class Meta:
        model = Category
        fields = ["id", "name", "description", "team", "team_name", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class SLAPolicySerializer(serializers.ModelSerializer):
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)

    class Meta:
        model = SLAPolicy
        fields = ["id", "priority", "priority_label", "resolution_hours", "updated_at"]
        read_only_fields = ["id", "priority", "updated_at"]

    def validate_resolution_hours(self, value):
        if not 1 <= value <= 24 * 90:
            raise serializers.ValidationError("Must be between 1 hour and 90 days.")
        return value


class CustomerSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email"]


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class TicketListSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    assigned_agent = UserSummarySerializer(read_only=True)
    category = CategoryMiniSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    sla_status = serializers.CharField(read_only=True)
    message_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Ticket
        fields = [
            "id", "number", "title", "status", "status_label", "priority", "priority_label", "category",
            "customer", "assigned_agent", "created_at", "updated_at", "resolved_at", "sla_due_at",
            "sla_status", "message_count",
        ]


class AIInsightSerializer(serializers.ModelSerializer):
    suggested_category = CategoryMiniSerializer(read_only=True)
    summary_outdated = serializers.SerializerMethodField()

    class Meta:
        model = TicketAIInsight
        fields = [
            "classification_status", "suggested_category", "suggested_priority", "suggested_first_response",
            "needs_human_review", "classification_reason", "classified_at", "summary", "summary_status",
            "summary_updated_at", "summary_outdated", "error_message", "model_name",
        ]

    def get_summary_outdated(self, obj) -> bool:
        current = self.context.get("message_count")
        return bool(obj.summary) and current is not None and current != obj.summary_message_count


class TicketDetailSerializer(TicketListSerializer):
    description = serializers.CharField(read_only=True)
    ai_insight = serializers.SerializerMethodField()
    allowed_transitions = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + [
            "description", "first_response_at", "closed_at", "ai_insight", "allowed_transitions", "permissions",
        ]

    @extend_schema_field(AIInsightSerializer(allow_null=True))
    def get_ai_insight(self, obj):
        user = self.context["request"].user
        if user.role == "CUSTOMER":  # AI output is internal until an agent publishes it
            return None
        insight = getattr(obj, "ai_insight", None) if hasattr(obj, "ai_insight") else None
        if insight is None:
            return None
        return AIInsightSerializer(insight, context={"message_count": obj.messages.count()}).data

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(choices=TicketStatus.choices)))
    def get_allowed_transitions(self, obj):
        return services.allowed_transitions(obj, self.context["request"].user)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_permissions(self, obj):
        user = self.context["request"].user
        staff = user.role in ("ADMIN", "AGENT")
        is_closed = obj.status == TicketStatus.CLOSED
        return {
            "can_edit": staff and not is_closed,
            "can_assign": services.can_assign(obj, user),
            "can_reply": not is_closed,
            "can_add_internal_note": staff and not is_closed,
            "can_use_ai": staff,
        }


class TicketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=5, max_length=200)
    description = serializers.CharField(min_length=10, max_length=5000)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.filter(is_active=True), required=False, allow_null=True
    )


class TicketUpdateSerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=TicketPriority.choices, required=False)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.filter(is_active=True), required=False, allow_null=True
    )
    sla_due_at = serializers.DateTimeField(required=False, allow_null=True)


class TransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TicketStatus.choices)


class AssignSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField(allow_null=True)


class MessageSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = TicketMessage
        fields = ["id", "author", "body", "is_internal", "is_ai_assisted", "created_at"]


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, trim_whitespace=True)
    is_internal = serializers.BooleanField(default=False)


class ActivitySerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = TicketActivity
        fields = ["id", "action", "action_label", "actor", "from_value", "to_value", "is_public", "created_at"]


class ArticleRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    slug = serializers.CharField()


class ReplyDraftSerializer(serializers.ModelSerializer):
    requested_by = UserSummarySerializer(read_only=True)
    referenced_articles = ArticleRefSerializer(many=True, read_only=True)

    class Meta:
        model = ReplyDraft
        fields = ["id", "body", "status", "requested_by", "referenced_articles", "model_name", "created_at",
                  "decided_at", "published_message"]


class PublishDraftSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)
