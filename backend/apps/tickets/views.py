import logging

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import User
from apps.ai import services as ai_services
from apps.ai.client import AIError, AIRateLimited
from apps.audit.models import AuditAction
from apps.audit.services import log_action
from apps.core.exceptions import ServiceUnavailable
from apps.core.throttling import AIRateThrottle
from apps.core.permissions import IsStaffRole, ReadOnlyOrAdmin, StaffReadOnlyOrAdmin
from apps.knowledge_base.serializers import ArticleListSerializer

from . import services
from .filters import TicketFilter
from .models import Category, ReplyDraft, SLAPolicy, Ticket, TicketActivity, TicketMessage
from .selectors import visible_tickets, with_priority_rank
from .serializers import (
    ActivitySerializer,
    AIInsightSerializer,
    AssignSerializer,
    CategorySerializer,
    MessageCreateSerializer,
    MessageSerializer,
    PublishDraftSerializer,
    ReplyDraftSerializer,
    SLAPolicySerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
    TicketUpdateSerializer,
    TransitionSerializer,
)

logger = logging.getLogger(__name__)


def _ai_unavailable(exc: AIError):
    err = ServiceUnavailable(detail=exc.user_message)
    if isinstance(exc, AIRateLimited):
        err.status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return err


@extend_schema(parameters=[
    OpenApiParameter("assigned_agent", str, description="Agent id, `me`, or `unassigned`"),
    OpenApiParameter("ordering", str, description="created_at, updated_at, priority_rank, sla_due_at (prefix - for desc)"),
])
class TicketViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    filterset_class = TicketFilter
    search_fields = ["number", "title"]
    ordering_fields = ["created_at", "updated_at", "priority_rank", "sla_due_at"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # OpenAPI schema generation
            return Ticket.objects.none()
        user = self.request.user
        qs = visible_tickets(user).select_related("customer", "assigned_agent", "category")
        if self.action == "list":
            message_filter = Q(messages__is_internal=False) if user.role == "CUSTOMER" else Q()
            qs = qs.annotate(message_count=Count("messages", filter=message_filter, distinct=True))
            return with_priority_rank(qs)
        return qs.select_related("ai_insight", "ai_insight__suggested_category")

    def get_serializer_class(self):
        if self.action == "list":
            return TicketListSerializer
        if self.action == "create":
            return TicketCreateSerializer
        if self.action in ("update", "partial_update"):
            return TicketUpdateSerializer
        return TicketDetailSerializer

    def _detail(self, ticket, code=status.HTTP_200_OK):
        ticket = self.get_queryset().get(pk=ticket.pk)
        return Response(TicketDetailSerializer(ticket, context=self.get_serializer_context()).data, status=code)

    def _require_staff(self):
        if self.request.user.role not in ("ADMIN", "AGENT"):
            raise PermissionDenied("Only support staff can perform this action.")

    @extend_schema(request=TicketCreateSerializer, responses={201: TicketDetailSerializer})
    def create(self, request, *args, **kwargs):
        if request.user.role != "CUSTOMER":
            raise PermissionDenied("Tickets are created by customers.")
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.create_ticket(customer=request.user, request=request, **serializer.validated_data)
        return self._detail(ticket, status.HTTP_201_CREATED)

    @extend_schema(request=TicketUpdateSerializer, responses=TicketDetailSerializer)
    def partial_update(self, request, *args, **kwargs):
        ticket = self.get_object()
        self._require_staff()
        serializer = TicketUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        ticket = services.update_ticket(ticket=ticket, user=request.user, data=serializer.validated_data, request=request)
        return self._detail(ticket)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @extend_schema(request=AssignSerializer, responses=TicketDetailSerializer)
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        ticket = self.get_object()
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agent_id = serializer.validated_data["agent_id"]
        agent = get_object_or_404(User, pk=agent_id) if agent_id is not None else None
        ticket = services.assign_ticket(ticket=ticket, user=request.user, agent=agent, request=request)
        return self._detail(ticket)

    @extend_schema(request=TransitionSerializer, responses=TicketDetailSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        ticket = self.get_object()
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.transition_ticket(
            ticket=ticket, user=request.user, to_status=serializer.validated_data["status"], request=request
        )
        return self._detail(ticket)

    @extend_schema(methods=["GET"], responses=MessageSerializer(many=True))
    @extend_schema(methods=["POST"], request=MessageCreateSerializer, responses={201: MessageSerializer})
    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        """Conversation. Customers never receive internal notes."""
        ticket = self.get_object()
        if request.method == "GET":
            messages = TicketMessage.objects.filter(ticket=ticket).select_related("author")
            if request.user.role == "CUSTOMER":
                messages = messages.filter(is_internal=False)
            return Response(MessageSerializer(messages, many=True).data)

        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.add_message(ticket=ticket, author=request.user, **serializer.validated_data)
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=ActivitySerializer(many=True))
    @action(detail=True, methods=["get"])
    def activities(self, request, pk=None):
        ticket = self.get_object()
        qs = TicketActivity.objects.filter(ticket=ticket).select_related("actor")
        if request.user.role == "CUSTOMER":
            qs = qs.filter(is_public=True)
        return Response(ActivitySerializer(qs[:200], many=True).data)

    # ----------------------------------------------------------------- AI ---
    @extend_schema(request=None, responses=AIInsightSerializer)
    @action(detail=True, methods=["post"], throttle_classes=[AIRateThrottle])
    def classify(self, request, pk=None):
        """Re-run AI classification (staff). Suggestions are not applied automatically."""
        ticket = self.get_object()
        self._require_staff()
        insight = ai_services.classify_ticket(ticket.pk)
        if insight.classification_status != insight.Status.COMPLETED:
            raise ServiceUnavailable(detail=insight.error_message or AIError.user_message)
        return Response(AIInsightSerializer(insight, context={"message_count": ticket.messages.count()}).data)

    @extend_schema(request=None, responses=AIInsightSerializer)
    @action(detail=True, methods=["post"], throttle_classes=[AIRateThrottle])
    def summarize(self, request, pk=None):
        ticket = self.get_object()
        self._require_staff()
        try:
            insight = ai_services.summarize_ticket(ticket, request.user)
        except AIError as exc:
            raise _ai_unavailable(exc)
        return Response(AIInsightSerializer(insight, context={"message_count": ticket.messages.count()}).data)

    @extend_schema(request=None, responses={201: ReplyDraftSerializer})
    @action(detail=True, methods=["post"], url_path="suggest-reply",
            throttle_classes=[AIRateThrottle])
    def suggest_reply(self, request, pk=None):
        ticket = self.get_object()
        self._require_staff()
        if ticket.status == "CLOSED":
            return Response({"detail": "Closed tickets cannot receive replies."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            draft = ai_services.suggest_reply(ticket, request.user)
        except AIError as exc:
            raise _ai_unavailable(exc)
        return Response(ReplyDraftSerializer(draft).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=ReplyDraftSerializer(many=True))
    @action(detail=True, methods=["get"])
    def drafts(self, request, pk=None):
        ticket = self.get_object()
        self._require_staff()
        drafts = ReplyDraft.objects.filter(ticket=ticket).select_related("requested_by").prefetch_related(
            "referenced_articles"
        )
        return Response(ReplyDraftSerializer(drafts[:20], many=True).data)

    def _get_draft(self, ticket, draft_id):
        return get_object_or_404(ReplyDraft, pk=draft_id, ticket=ticket)

    @extend_schema(request=PublishDraftSerializer, responses={201: MessageSerializer})
    @action(detail=True, methods=["post"], url_path=r"drafts/(?P<draft_id>\d+)/publish")
    def publish_draft(self, request, pk=None, draft_id=None):
        """Approve an AI draft (optionally edited) and send it to the customer as a public reply."""
        ticket = self.get_object()
        self._require_staff()
        serializer = PublishDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.publish_draft(draft=self._get_draft(ticket, draft_id), user=request.user,
                                         body=serializer.validated_data["body"], request=request)
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=ReplyDraftSerializer)
    @action(detail=True, methods=["post"], url_path=r"drafts/(?P<draft_id>\d+)/discard")
    def discard_draft(self, request, pk=None, draft_id=None):
        ticket = self.get_object()
        self._require_staff()
        draft = services.discard_draft(draft=self._get_draft(ticket, draft_id), user=request.user)
        return Response(ReplyDraftSerializer(draft).data)

    @extend_schema(responses=ArticleListSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="related-articles")
    def related_articles(self, request, pk=None):
        ticket = self.get_object()
        articles = ai_services.related_articles_for_ticket(ticket, request.user, limit=5)
        return Response(ArticleListSerializer(articles, many=True).data)


class CategoryViewSet(viewsets.ModelViewSet):
    """Everyone can list active categories (for the ticket form); admins manage them."""

    serializer_class = CategorySerializer
    permission_classes = [ReadOnlyOrAdmin]
    pagination_class = None
    search_fields = ["name"]

    def get_queryset(self):
        qs = Category.objects.select_related("team")
        if getattr(self, "swagger_fake_view", False):
            return qs.none()
        if self.request.user.role != "ADMIN":
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        category = serializer.save()
        log_action(AuditAction.CATEGORY_CHANGED, actor=self.request.user, target=category,
                   description=f"Created category {category.name}", request=self.request)

    def perform_update(self, serializer):
        category = serializer.save()
        log_action(AuditAction.CATEGORY_CHANGED, actor=self.request.user, target=category,
                   description=f"Updated category {category.name}", request=self.request)

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        if category.tickets.exists():
            return Response({"detail": "This category has tickets. Deactivate it instead of deleting it."},
                            status=status.HTTP_400_BAD_REQUEST)
        log_action(AuditAction.CATEGORY_CHANGED, actor=request.user, target=category,
                   description=f"Deleted category {category.name}", request=request)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SLAPolicyViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Staff can read SLA targets; admins can change the hours. New targets apply to new or re-prioritised tickets."""

    serializer_class = SLAPolicySerializer
    permission_classes = [StaffReadOnlyOrAdmin]
    pagination_class = None
    queryset = SLAPolicy.objects.all()
    http_method_names = ["get", "patch", "head", "options"]

    def perform_update(self, serializer):
        old = serializer.instance.resolution_hours
        policy = serializer.save()
        log_action(AuditAction.SLA_POLICY_CHANGED, actor=self.request.user, target=policy,
                   description=f"SLA {policy.priority}: {old}h -> {policy.resolution_hours}h", request=self.request)
