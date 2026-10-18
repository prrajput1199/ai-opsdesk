import django_filters
from dataclasses import asdict
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from apps.core.throttling import AIRateThrottle
from rest_framework.views import APIView

from apps.ai import services as ai_services
from apps.ai.client import AIError, AIRateLimited
from apps.audit.models import AuditAction
from apps.audit.services import log_action
from apps.core.exceptions import ServiceUnavailable
from apps.core.permissions import ReadOnlyOrAdmin

from .models import KnowledgeBaseArticle
from .selectors import fallback_keyword_search, search_articles, visible_articles
from .serializers import (
    AnswerSerializer,
    ArticleDetailSerializer,
    ArticleListSerializer,
    ArticleWriteSerializer,
    AskSerializer,
    SearchResultSerializer,
)


class ArticleFilter(django_filters.FilterSet):
    class Meta:
        model = KnowledgeBaseArticle
        fields = ["category", "status", "visibility"]


class ArticleViewSet(viewsets.ModelViewSet):
    """Everyone reads what their role may see (see selectors.visible_articles); admins write."""

    permission_classes = [ReadOnlyOrAdmin]
    filterset_class = ArticleFilter
    search_fields = ["title", "summary"]
    ordering_fields = ["updated_at", "title", "published_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return visible_articles(self.request.user)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ArticleWriteSerializer
        if self.action == "retrieve":
            return ArticleDetailSerializer
        return ArticleListSerializer

    @extend_schema(responses={201: ArticleDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = ArticleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        article = serializer.save(author=request.user)
        log_action(AuditAction.ARTICLE_CREATED, actor=request.user, target=article,
                   description=f"Created article '{article.title}'", request=request)
        return Response(ArticleDetailSerializer(article).data, status=201)

    @extend_schema(responses=ArticleDetailSerializer)
    def partial_update(self, request, *args, **kwargs):
        article = self.get_object()
        serializer = ArticleWriteSerializer(article, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        article = serializer.save()
        log_action(AuditAction.ARTICLE_UPDATED, actor=request.user, target=article,
                   description=f"Updated article '{article.title}'", request=request)
        return Response(ArticleDetailSerializer(article).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        log_action(AuditAction.ARTICLE_DELETED, actor=self.request.user, target=instance,
                   description=f"Deleted article '{instance.title}'", request=self.request)
        instance.delete()


class ArticleSearchView(APIView):
    @extend_schema(
        parameters=[OpenApiParameter("q", str, required=True), OpenApiParameter("limit", int)],
        responses=SearchResultSerializer(many=True),
    )
    def get(self, request):
        """Full-text search (PostgreSQL) over articles the current user may read."""
        query = (request.query_params.get("q") or "").strip()[:200]
        try:
            limit = max(1, min(int(request.query_params.get("limit", 10)), 25))
        except ValueError:
            limit = 10
        if len(query) < 2:
            return Response([])
        base = visible_articles(request.user)
        results = list(search_articles(base, query, limit=limit))
        if not results:
            results = list(fallback_keyword_search(base, query, limit=limit))
        return Response(SearchResultSerializer(results, many=True).data)


class AskKnowledgeBaseView(APIView):
    throttle_classes = [AIRateThrottle]

    @extend_schema(request=AskSerializer, responses=AnswerSerializer)
    def post(self, request):
        """Answer a question with Gemini using only matching published articles, with citations."""
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            answer = ai_services.answer_question(serializer.validated_data["question"].strip(), request.user)
        except AIError as exc:
            err = ServiceUnavailable(detail=exc.user_message)
            if isinstance(exc, AIRateLimited):
                err.status_code = 429
            raise err
        return Response(AnswerSerializer(asdict(answer)).data)
