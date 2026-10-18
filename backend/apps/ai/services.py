"""
AI features used by the API. Views call these functions; nothing else talks to Gemini.

Privacy: only ticket text, conversation text and KB excerpts are sent. Customer names,
emails and other account data are replaced by role labels ("Customer", "Agent").
"""

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.knowledge_base.selectors import answerable_articles, fallback_keyword_search, search_articles
from apps.tickets.models import Category, ReplyDraft, Ticket, TicketActivity, TicketAIInsight

from . import client as ai_client
from .client import AIError, AINotConfigured
from .prompts import CLASSIFY_SYSTEM, KB_ANSWER_SYSTEM, REPLY_SYSTEM, SUMMARY_SYSTEM
from .schemas import ClassificationResult, KnowledgeAnswerResult, ReplyResult, SummaryResult

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_CHARS = 4000
MAX_MESSAGE_CHARS = 1200
MAX_MESSAGES = 15
MAX_ARTICLE_CHARS = 1800
MAX_ARTICLES = 4


def _truncate(text, limit):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + " [...]"


def _author_label(message):
    if message.is_internal:
        return "Internal note (agent)"
    return "Customer" if message.author.role == "CUSTOMER" else "Support agent"


def build_ticket_context(ticket, *, include_internal):
    messages = ticket.messages.select_related("author").order_by("-created_at")
    if not include_internal:
        messages = messages.filter(is_internal=False)
    recent = list(messages[:MAX_MESSAGES])[::-1]
    lines = [
        "<ticket>",
        f"Title: {_truncate(ticket.title, 200)}",
        f"Current category: {ticket.category.name if ticket.category else 'Uncategorised'}",
        f"Current priority: {ticket.priority}",
        f"Status: {ticket.status}",
        "Description:",
        _truncate(ticket.description, MAX_DESCRIPTION_CHARS),
        "</ticket>",
    ]
    if recent:
        lines.append("<conversation>")
        for m in recent:
            lines.append(f"[{_author_label(m)} | {m.created_at:%Y-%m-%d %H:%M}] {_truncate(m.body, MAX_MESSAGE_CHARS)}")
        lines.append("</conversation>")
    return "\n".join(lines)[: settings.AI_MAX_INPUT_CHARS]


def _articles_block(articles):
    parts = []
    for a in articles:
        parts.append(
            f'<article id="{a.id}" title="{_truncate(a.title, 200)}">\n{_truncate(a.content, MAX_ARTICLE_CHARS)}\n</article>'
        )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# A. Classification
# ---------------------------------------------------------------------------
def classify_ticket(ticket_id):
    """
    Suggest category, priority, summary and first response. Never raises for AI failures:
    the outcome is recorded on the insight (status=failed/unavailable) so ticket handling
    continues normally. Suggestions are not applied to the ticket automatically.
    """
    ticket = Ticket.objects.select_related("category").get(pk=ticket_id)
    insight, _ = TicketAIInsight.objects.get_or_create(ticket=ticket)
    categories = {c.name.lower(): c for c in Category.objects.filter(is_active=True)}
    client = ai_client.get_client()

    prompt = (
        f"Allowed categories: {', '.join(c.name for c in categories.values()) or 'NONE'}\n\n"
        + build_ticket_context(ticket, include_internal=False)
    )
    try:
        result: ClassificationResult = client.generate_structured(
            system_instruction=CLASSIFY_SYSTEM, prompt=prompt, schema=ClassificationResult
        )
    except AINotConfigured as exc:
        insight.classification_status = TicketAIInsight.Status.UNAVAILABLE
        insight.error_message = exc.user_message
        insight.save()
        return insight
    except AIError as exc:
        insight.classification_status = TicketAIInsight.Status.FAILED
        insight.error_message = exc.user_message
        insight.save()
        return insight

    category = categories.get(result.category.lower())
    insight.suggested_category = category
    insight.suggested_priority = result.priority
    insight.suggested_first_response = result.suggested_first_response
    # Unknown category from the model -> force human review.
    insight.needs_human_review = result.needs_human_review or (category is None and result.category.upper() != "NONE")
    insight.classification_reason = result.reason
    insight.classification_status = TicketAIInsight.Status.COMPLETED
    insight.classified_at = timezone.now()
    insight.model_name = client.model
    insight.error_message = ""
    if not insight.summary:
        insight.summary = result.summary
        insight.summary_status = TicketAIInsight.Status.COMPLETED
        insight.summary_updated_at = timezone.now()
        insight.summary_message_count = ticket.messages.count()
    insight.save()
    TicketActivity.objects.create(
        ticket=ticket, action=TicketActivity.Action.AI_CLASSIFIED,
        to_value=f"{result.priority} / {category.name if category else 'no category'}",
    )
    return insight


def run_classification_safely(ticket_id, *, close_connection=False):
    """
    Entry point for automatic classification: never lets an exception escape.
    `close_connection=True` when running in a background thread, which owns its own DB connection.
    """
    from django.db import connection

    try:
        classify_ticket(ticket_id)
    except Exception:  # pragma: no cover - defensive, e.g. ticket deleted
        logger.exception("Background classification failed for ticket %s", ticket_id)
        TicketAIInsight.objects.filter(ticket_id=ticket_id).update(
            classification_status=TicketAIInsight.Status.FAILED, error_message=AIError.user_message
        )
    finally:
        if close_connection:
            connection.close()


# ---------------------------------------------------------------------------
# B. Summarisation
# ---------------------------------------------------------------------------
def summarize_ticket(ticket, actor):
    """Regenerate the agent-facing summary. Raises AIError on failure (after recording it)."""
    insight, _ = TicketAIInsight.objects.get_or_create(ticket=ticket)
    client = ai_client.get_client()
    try:
        result: SummaryResult = client.generate_structured(
            system_instruction=SUMMARY_SYSTEM,
            prompt=build_ticket_context(ticket, include_internal=True),
            schema=SummaryResult,
        )
    except AIError as exc:
        insight.summary_status = (
            TicketAIInsight.Status.UNAVAILABLE if isinstance(exc, AINotConfigured) else TicketAIInsight.Status.FAILED
        )
        insight.error_message = exc.user_message
        insight.save(update_fields=["summary_status", "error_message", "updated_at"])
        raise

    insight.summary = result.summary
    insight.summary_status = TicketAIInsight.Status.COMPLETED
    insight.summary_updated_at = timezone.now()
    insight.summary_message_count = ticket.messages.count()
    insight.model_name = client.model
    insight.error_message = ""
    insight.save()
    TicketActivity.objects.create(ticket=ticket, actor=actor, action=TicketActivity.Action.AI_SUMMARIZED)
    return insight


# ---------------------------------------------------------------------------
# C. Suggested replies
# ---------------------------------------------------------------------------
def related_articles_for_ticket(ticket, user, limit=MAX_ARTICLES):
    base = answerable_articles(user)
    text = f"{ticket.title} {ticket.description[:600]}"
    articles = list(search_articles(base, text, limit=limit, any_word=True))
    if not articles and ticket.category_id:
        articles = list(base.filter(category_id=ticket.category_id)[:limit])
    return articles


def suggest_reply(ticket, actor):
    """Create a ReplyDraft. Raises AIError on failure. The draft is never sent automatically."""
    articles = related_articles_for_ticket(ticket, actor)
    supplied_ids = {a.id for a in articles}
    prompt = build_ticket_context(ticket, include_internal=False)
    prompt += "\n\nKnowledge base articles:\n" + (_articles_block(articles) if articles else "(none found)")

    client = ai_client.get_client()
    result: ReplyResult = client.generate_structured(
        system_instruction=REPLY_SYSTEM, prompt=prompt[: settings.AI_MAX_INPUT_CHARS], schema=ReplyResult,
        temperature=0.4,
    )
    used_ids = [i for i in result.used_article_ids if i in supplied_ids]  # drop invented ids
    with transaction.atomic():
        draft = ReplyDraft.objects.create(
            ticket=ticket, requested_by=actor, body=result.reply, model_name=client.model
        )
        if used_ids:
            draft.referenced_articles.set(used_ids)
    return draft


# ---------------------------------------------------------------------------
# D. Knowledge-base question answering
# ---------------------------------------------------------------------------
@dataclass
class KnowledgeAnswer:
    question: str
    answer: str
    sufficient_information: bool
    ai_generated: bool
    citations: list = field(default_factory=list)  # [{id, title, slug}]
    articles_considered: list = field(default_factory=list)


NOT_FOUND_ANSWER = (
    "The knowledge base doesn't contain information about this yet. "
    "Try different keywords, or create a support ticket and our team will help."
)


def answer_question(question, user):
    """
    Retrieval-augmented answer: find relevant published articles the user may read, send only
    their excerpts to Gemini, and return citations limited to the articles that were supplied.
    If no article matches, Gemini is not called at all.
    """
    base = answerable_articles(user)
    articles = list(search_articles(base, question, limit=MAX_ARTICLES))
    if not articles:
        articles = list(search_articles(base, question, limit=MAX_ARTICLES, any_word=True))
    if not articles:
        articles = list(fallback_keyword_search(base, question, limit=MAX_ARTICLES))
    considered = [{"id": a.id, "title": a.title, "slug": a.slug} for a in articles]

    if not articles:
        return KnowledgeAnswer(question=question, answer=NOT_FOUND_ANSWER, sufficient_information=False,
                               ai_generated=False, articles_considered=[])

    prompt = f"<question>{question}</question>\n\nArticles:\n{_articles_block(articles)}"
    result: KnowledgeAnswerResult = ai_client.get_client().generate_structured(
        system_instruction=KB_ANSWER_SYSTEM, prompt=prompt, schema=KnowledgeAnswerResult, temperature=0.1
    )
    by_id = {a.id: a for a in articles}
    used = [by_id[i] for i in dict.fromkeys(result.used_article_ids) if i in by_id]
    sufficient = result.sufficient_information and bool(used)
    return KnowledgeAnswer(
        question=question,
        answer=result.answer,
        sufficient_information=sufficient,
        ai_generated=True,
        citations=[{"id": a.id, "title": a.title, "slug": a.slug} for a in used] if sufficient else [],
        articles_considered=considered,
    )
