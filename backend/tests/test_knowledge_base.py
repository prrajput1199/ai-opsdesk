import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.knowledge_base.models import KnowledgeBaseArticle

pytestmark = pytest.mark.django_db

ARTICLES = "/api/v1/knowledge-base/articles/"


def _titles(res):
    data = res.data["results"] if isinstance(res.data, dict) else res.data
    return {a["title"] for a in data}


def test_article_visibility_by_role(customer, agent, admin_user, articles, api):
    assert _titles(api(customer).get(ARTICLES)) == {"How to reset your password", "Refund policy"}
    assert _titles(api(agent).get(ARTICLES)) == {"How to reset your password", "Refund policy", "Escalation playbook"}
    assert "SSO setup draft" in _titles(api(admin_user).get(ARTICLES))


def test_customer_cannot_open_internal_or_draft_by_id(customer, articles, api):
    for key in ("internal", "draft"):
        assert api(customer).get(f"{ARTICLES}{articles[key].id}/").status_code == 404
    res = api(customer).get(f"{ARTICLES}{articles['password'].id}/")
    assert res.status_code == 200 and "content" in res.data


def test_only_admin_can_write_articles(customer, agent, admin_user, api, categories):
    payload = {"title": "New article title", "content": "Long enough content for an article body here.",
               "status": "published", "category": categories["tech"].id}
    assert api(customer).post(ARTICLES, payload, format="json").status_code == 403
    assert api(agent).post(ARTICLES, payload, format="json").status_code == 403
    res = api(admin_user).post(ARTICLES, payload, format="json")
    assert res.status_code == 201 and res.data["slug"] == "new-article-title" and res.data["published_at"]
    # Same title -> unique slug generated
    res2 = api(admin_user).post(ARTICLES, payload, format="json")
    assert res2.data["slug"] == "new-article-title-2"
    assert AuditLog.objects.filter(action=AuditAction.ARTICLE_CREATED).count() == 2

    article_id = res.data["id"]
    assert api(admin_user).patch(f"{ARTICLES}{article_id}/", {"title": "Renamed"}, format="json").status_code == 200
    assert api(admin_user).delete(f"{ARTICLES}{article_id}/").status_code == 204
    assert not KnowledgeBaseArticle.objects.filter(pk=article_id).exists()


def test_full_text_search_ranks_and_respects_visibility(customer, agent, articles, api):
    res = api(customer).get("/api/v1/knowledge-base/search/", {"q": "reset password"})
    assert res.status_code == 200
    titles = [a["title"] for a in res.data]
    assert titles[0] == "How to reset your password"
    assert "Escalation playbook" not in titles  # internal, even though it mentions password
    assert "<<" in res.data[0]["headline"]  # highlighted excerpt

    staff_titles = [a["title"] for a in api(agent).get("/api/v1/knowledge-base/search/", {"q": "password"}).data]
    assert "Escalation playbook" in staff_titles and "SSO setup draft" not in staff_titles


def test_search_handles_odd_input(customer, articles, api):
    for q in ["", "a", "!!! & | ::", "refund' OR 1=1 --"]:
        assert api(customer).get("/api/v1/knowledge-base/search/", {"q": q}).status_code == 200


def test_related_articles_for_ticket(customer, make_ticket, articles, api):
    ticket = make_ticket(customer, title="Password reset link expired",
                         description="The password reset link says expired.")
    res = api(customer).get(f"/api/v1/tickets/{ticket.id}/related-articles/")
    assert res.status_code == 200
    ids = [a["id"] for a in res.data]
    assert articles["password"].id in ids and articles["internal"].id not in ids
