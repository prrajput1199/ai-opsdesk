"""Read-side queries for the knowledge base. All access rules for articles live here."""

from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db.models import F, Q

from .models import SEARCH_VECTOR, KnowledgeBaseArticle

STOP_CHARS = str.maketrans({c: " " for c in "!&|:*()<>'\""})


def visible_articles(user):
    """
    - Customers: published + public only.
    - Agents: published (public and internal).
    - Admins: everything, including drafts.
    """
    qs = KnowledgeBaseArticle.objects.select_related("category", "author")
    role = getattr(user, "role", None)
    if role == "ADMIN":
        return qs
    if role == "AGENT":
        return qs.filter(status=KnowledgeBaseArticle.Status.PUBLISHED)
    return qs.filter(status=KnowledgeBaseArticle.Status.PUBLISHED, visibility=KnowledgeBaseArticle.Visibility.PUBLIC)


def answerable_articles(user):
    """Articles that may be sent to the AI to answer a question: always published only."""
    return visible_articles(user).filter(status=KnowledgeBaseArticle.Status.PUBLISHED)


def _clean(query: str) -> str:
    return " ".join(query.translate(STOP_CHARS).split())[:200]


def search_articles(queryset, query, *, limit=10, any_word=False):
    """
    PostgreSQL full-text search ranked by relevance (title matches weigh more than content).

    `any_word=True` ORs the terms together - used when matching a whole ticket description
    against articles, where requiring every word would almost never match.
    """
    text = _clean(query or "")
    if not text:
        return queryset.none()
    if any_word:
        words = [w for w in text.split() if len(w) > 2][:30]
        if not words:
            return queryset.none()
        search_query = None
        for w in words:
            q = SearchQuery(w, search_type="plain", config="english")
            search_query = q if search_query is None else search_query | q
    else:
        search_query = SearchQuery(text, search_type="websearch", config="english")

    return (
        queryset.annotate(search=SEARCH_VECTOR, rank=SearchRank(SEARCH_VECTOR, search_query))
        .filter(search=search_query)
        .annotate(
            headline=SearchHeadline(
                "content", search_query, config="english",
                start_sel="<<", stop_sel=">>", max_words=35, min_words=15, max_fragments=2,
            )
        )
        .order_by(F("rank").desc(), "-updated_at")[:limit]
    )


def fallback_keyword_search(queryset, query, *, limit=10):
    """Simple icontains search, used only if full-text search finds nothing (e.g. very short words)."""
    text = _clean(query or "")
    if not text:
        return queryset.none()
    return queryset.filter(Q(title__icontains=text) | Q(content__icontains=text))[:limit]
