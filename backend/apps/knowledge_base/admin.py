from django.contrib import admin

from .models import KnowledgeBaseArticle


@admin.register(KnowledgeBaseArticle)
class KnowledgeBaseArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "visibility", "updated_at")
    list_filter = ("status", "visibility", "category")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ("author",)
