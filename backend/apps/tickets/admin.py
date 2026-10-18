from django.contrib import admin

from .models import Category, ReplyDraft, SLAPolicy, Ticket, TicketActivity, TicketAIInsight, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    fields = ("author", "body", "is_internal", "is_ai_assisted", "created_at")
    readonly_fields = ("created_at",)
    raw_id_fields = ("author",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "status", "priority", "category", "customer", "assigned_agent", "created_at")
    list_filter = ("status", "priority", "category")
    search_fields = ("number", "title")
    raw_id_fields = ("customer", "assigned_agent")
    list_select_related = ("category", "customer", "assigned_agent")
    inlines = [TicketMessageInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "is_active")
    list_filter = ("is_active", "team")


@admin.register(SLAPolicy)
class SLAPolicyAdmin(admin.ModelAdmin):
    list_display = ("priority", "resolution_hours", "updated_at")


@admin.register(TicketActivity)
class TicketActivityAdmin(admin.ModelAdmin):
    list_display = ("ticket", "action", "actor", "from_value", "to_value", "created_at")
    list_filter = ("action",)
    raw_id_fields = ("ticket", "actor")


@admin.register(TicketAIInsight)
class TicketAIInsightAdmin(admin.ModelAdmin):
    list_display = ("ticket", "classification_status", "suggested_priority", "needs_human_review", "updated_at")
    raw_id_fields = ("ticket",)


@admin.register(ReplyDraft)
class ReplyDraftAdmin(admin.ModelAdmin):
    list_display = ("ticket", "status", "requested_by", "created_at")
    raw_id_fields = ("ticket", "requested_by", "published_message")
