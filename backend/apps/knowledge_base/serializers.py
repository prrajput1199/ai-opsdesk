from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from apps.tickets.models import Category

from .models import KnowledgeBaseArticle


class ArticleListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    author_name = serializers.CharField(source="author.full_name", read_only=True, default=None)

    class Meta:
        model = KnowledgeBaseArticle
        fields = [
            "id", "title", "slug", "summary", "category", "category_name", "status", "visibility",
            "author_name", "updated_at", "published_at",
        ]


class ArticleDetailSerializer(ArticleListSerializer):
    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields + ["content", "created_at"]


class ArticleWriteSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)
    slug = serializers.SlugField(max_length=220, required=False)

    class Meta:
        model = KnowledgeBaseArticle
        fields = ["title", "slug", "summary", "content", "category", "status", "visibility"]
        extra_kwargs = {"title": {"min_length": 3}, "content": {"min_length": 20}}

    def validate(self, attrs):
        title = attrs.get("title") or (self.instance.title if self.instance else "")
        slug = attrs.get("slug") or (self.instance.slug if self.instance else "") or slugify(title)[:200]
        if not slug:
            raise serializers.ValidationError({"slug": "Could not generate a slug from the title."})
        base, n = slug, 2
        qs = KnowledgeBaseArticle.objects.all()
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if "slug" in attrs and qs.filter(slug=slug).exists():
            raise serializers.ValidationError({"slug": "An article with this slug already exists."})
        while qs.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        attrs["slug"] = slug
        new_status = attrs.get("status", self.instance.status if self.instance else "draft")
        if new_status == "published" and not (self.instance and self.instance.published_at):
            attrs["published_at"] = timezone.now()
        return attrs


class SearchResultSerializer(ArticleListSerializer):
    headline = serializers.CharField(read_only=True, default="")
    rank = serializers.FloatField(read_only=True, default=0)

    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields + ["headline", "rank"]


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(min_length=5, max_length=500)


class CitationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    slug = serializers.CharField()


class AnswerSerializer(serializers.Serializer):
    question = serializers.CharField()
    answer = serializers.CharField()
    sufficient_information = serializers.BooleanField()
    ai_generated = serializers.BooleanField()
    citations = CitationSerializer(many=True)
    articles_considered = CitationSerializer(many=True)
