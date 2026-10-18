from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import models
from django.db.models import Q

# The same expression is used in queries (see selectors.py) so PostgreSQL can use the GIN index.
SEARCH_VECTOR = SearchVector("title", weight="A", config="english") + SearchVector("content", weight="B", config="english")


class KnowledgeBaseArticle(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public (customers and staff)"
        INTERNAL = "internal", "Internal (staff only)"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    summary = models.CharField(max_length=300, blank=True)
    content = models.TextField(max_length=20000)
    category = models.ForeignKey(
        "tickets.Category", null=True, blank=True, on_delete=models.SET_NULL, related_name="articles"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PUBLIC)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="articles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["status", "visibility"]),
            GinIndex(SEARCH_VECTOR, name="kb_article_search_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=["draft", "published"]), name="kb_status_valid"),
            models.CheckConstraint(condition=Q(visibility__in=["public", "internal"]), name="kb_visibility_valid"),
        ]

    def __str__(self):
        return self.title
