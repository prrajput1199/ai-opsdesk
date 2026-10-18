"""Gemini integration: validation, failure handling, human-in-the-loop publishing. All AI calls are fake."""

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors

from apps.ai.client import (
    AINotConfigured,
    AIRateLimited,
    AIResponseInvalid,
    AIServiceError,
    GeminiClient,
)
from apps.ai.schemas import ClassificationResult, KnowledgeAnswerResult, SummaryResult
from apps.ai.services import build_ticket_context, classify_ticket
from apps.audit.models import AuditAction, AuditLog
from apps.tickets.models import ReplyDraft, TicketAIInsight, TicketMessage
from apps.tickets.services import add_message

pytestmark = pytest.mark.django_db


# ----------------------------------------------------------------- schemas ---
def test_schema_rejects_invalid_priority_and_empty_text():
    from pydantic import ValidationError

    base = {"category": "Billing", "priority": "HIGH", "summary": "s", "suggested_first_response": "r",
            "needs_human_review": False, "reason": ""}
    ClassificationResult.model_validate(base)
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({**base, "priority": "CRITICAL"})
    with pytest.raises(ValidationError):
        ClassificationResult.model_validate({**base, "summary": "   "})
    with pytest.raises(ValidationError):
        SummaryResult.model_validate({})


def test_schema_truncates_overlong_text():
    result = SummaryResult.model_validate({"summary": "x" * 10_000})
    assert len(result.summary) == 2000


# ------------------------------------------------------------ GeminiClient ---
class _FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


def _client_with(outcomes, retries=1):
    client = GeminiClient(api_key="k", model="m", max_retries=retries)
    client._sdk_client = SimpleNamespace(models=_FakeModels(outcomes))
    return client


def _call(client):
    return client.generate_structured(system_instruction="s", prompt="p", schema=SummaryResult)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("apps.ai.client.time.sleep", lambda s: None)


def test_client_requires_api_key():
    with pytest.raises(AINotConfigured):
        _call(GeminiClient(api_key=""))


def test_client_parses_valid_json():
    assert _call(_client_with(['{"summary": "All good"}'])).summary == "All good"


@pytest.mark.parametrize("payload", ["not json", '{"wrong": 1}', "", '{"summary": ""}'])
def test_client_rejects_invalid_responses(payload):
    with pytest.raises(AIResponseInvalid):
        _call(_client_with([payload]))


def test_client_retries_server_errors_then_succeeds():
    client = _client_with([genai_errors.ServerError(503, {"error": {"message": "busy"}}), '{"summary": "ok"}'])
    assert _call(client).summary == "ok"
    assert client._sdk_client.models.calls == 2


def test_client_gives_up_after_retries():
    client = _client_with([httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow")], retries=1)
    with pytest.raises(AIServiceError):
        _call(client)


def test_client_maps_rate_limit():
    client = _client_with([genai_errors.ClientError(429, {"error": {"message": "quota"}})], retries=0)
    with pytest.raises(AIRateLimited):
        _call(client)


def test_client_does_not_retry_bad_requests():
    client = _client_with([genai_errors.ClientError(400, {"error": {"message": "bad"}}), '{"summary": "x"}'])
    with pytest.raises(AIServiceError):
        _call(client)
    assert client._sdk_client.models.calls == 1


# ---------------------------------------------------------- classification ---
def test_classification_stores_suggestions_without_applying_them(customer, make_ticket, categories):
    ticket = make_ticket(customer, category="tech")
    insight = TicketAIInsight.objects.get(ticket=ticket)
    assert insight.classification_status == "completed"
    assert insight.suggested_priority == "HIGH"
    assert insight.suggested_category == categories["billing"]
    ticket.refresh_from_db()
    assert ticket.priority == "MEDIUM" and ticket.category == categories["tech"]  # unchanged


def test_unknown_category_forces_human_review(customer, make_ticket, fake_ai):
    fake_ai.push({"category": "Space Travel", "priority": "LOW", "summary": "s", "suggested_first_response": "r",
                  "needs_human_review": False, "reason": ""})
    insight = TicketAIInsight.objects.get(ticket=make_ticket(customer))
    assert insight.suggested_category is None and insight.needs_human_review is True


def test_classification_failure_and_not_configured_are_recorded(customer, make_ticket, fake_ai):
    fake_ai.push(AIServiceError())
    ticket = make_ticket(customer)
    insight = TicketAIInsight.objects.get(ticket=ticket)
    assert insight.classification_status == "failed"
    assert "temporarily unavailable" in insight.error_message

    fake_ai.push(AINotConfigured())
    assert classify_ticket(ticket.id).classification_status == "unavailable"


def test_reclassify_endpoint_returns_503_on_failure(customer, agent, make_ticket, fake_ai, api):
    ticket = make_ticket(customer)
    fake_ai.push(AIResponseInvalid())
    assert api(agent).post(f"/api/v1/tickets/{ticket.id}/classify/").status_code == 503
    assert api(agent).post(f"/api/v1/tickets/{ticket.id}/classify/").status_code == 200


def test_prompt_contains_no_customer_personal_data(customer, agent, make_ticket, fake_ai):
    ticket = make_ticket(customer)
    add_message(ticket=ticket, author=agent, body="Internal detail", is_internal=True)
    prompt = fake_ai.calls[0]["prompt"]
    assert customer.email not in prompt and customer.first_name not in prompt
    assert "Internal detail" not in build_ticket_context(ticket, include_internal=False)


# ------------------------------------------------------------ summarisation ---
def test_summarize_endpoint(customer, agent, make_ticket, fake_ai, api):
    ticket = make_ticket(customer)
    fake_ai.push({"summary": "A fresh summary."})
    res = api(agent).post(f"/api/v1/tickets/{ticket.id}/summarize/")
    assert res.status_code == 200 and res.data["summary"] == "A fresh summary."
    assert res.data["summary_outdated"] is False

    add_message(ticket=ticket, author=customer, body="New info")
    detail = api(agent).get(f"/api/v1/tickets/{ticket.id}/").data
    assert detail["ai_insight"]["summary_outdated"] is True

    fake_ai.push(AIRateLimited())
    assert api(agent).post(f"/api/v1/tickets/{ticket.id}/summarize/").status_code == 429
    fake_ai.push(AIServiceError())
    res = api(agent).post(f"/api/v1/tickets/{ticket.id}/summarize/")
    assert res.status_code == 503 and "unavailable" in res.data["detail"]


# ---------------------------------------------------------- reply drafts ---
def test_suggest_reply_uses_kb_and_drops_invented_citations(customer, agent, make_ticket, articles, fake_ai, api):
    ticket = make_ticket(customer, title="Forgot my password", description="I need to reset my password please.")
    fake_ai.push({"reply": "Please use Forgot password. The Support Team",
                  "used_article_ids": [articles["password"].id, 999999]})
    res = api(agent).post(f"/api/v1/tickets/{ticket.id}/suggest-reply/")
    assert res.status_code == 201
    assert [a["id"] for a in res.data["referenced_articles"]] == [articles["password"].id]
    prompt = fake_ai.calls[-1]["prompt"]
    assert "Forgot password on the login page" in prompt
    assert "SSO setup draft" not in prompt  # drafts are never sent to the AI
    # Nothing is visible to the customer yet
    assert api(customer).get(f"/api/v1/tickets/{ticket.id}/comments/").data == []


def test_publish_and_discard_drafts(customer, agent, make_ticket, api):
    ticket = make_ticket(customer)
    draft_id = api(agent).post(f"/api/v1/tickets/{ticket.id}/suggest-reply/").data["id"]

    res = api(agent).post(f"/api/v1/tickets/{ticket.id}/drafts/{draft_id}/publish/",
                          {"body": "Edited by the agent before sending."}, format="json")
    assert res.status_code == 201 and res.data["is_ai_assisted"] is True
    msgs = api(customer).get(f"/api/v1/tickets/{ticket.id}/comments/").data
    assert [m["body"] for m in msgs] == ["Edited by the agent before sending."]
    assert ReplyDraft.objects.get(pk=draft_id).status == "published"
    log = AuditLog.objects.get(action=AuditAction.AI_REPLY_PUBLISHED)
    assert log.metadata["edited"] is True

    # Cannot publish twice
    assert api(agent).post(f"/api/v1/tickets/{ticket.id}/drafts/{draft_id}/publish/",
                           {"body": "again"}, format="json").status_code == 400

    other = api(agent).post(f"/api/v1/tickets/{ticket.id}/suggest-reply/").data["id"]
    assert api(agent).post(f"/api/v1/tickets/{ticket.id}/drafts/{other}/discard/").status_code == 200
    assert TicketMessage.objects.filter(ticket=ticket).count() == 1


def test_draft_from_another_ticket_is_not_reachable(customer, agent, make_ticket, api):
    a, b = make_ticket(customer), make_ticket(customer, title="Second ticket here")
    draft_id = api(agent).post(f"/api/v1/tickets/{a.id}/suggest-reply/").data["id"]
    res = api(agent).post(f"/api/v1/tickets/{b.id}/drafts/{draft_id}/publish/", {"body": "x"}, format="json")
    assert res.status_code == 404


def test_suggest_reply_failure_returns_503_and_creates_nothing(customer, agent, make_ticket, fake_ai, api):
    ticket = make_ticket(customer)
    fake_ai.push(AIServiceError())
    assert api(agent).post(f"/api/v1/tickets/{ticket.id}/suggest-reply/").status_code == 503
    assert ReplyDraft.objects.count() == 0


# ------------------------------------------------------------- KB answers ---
def test_kb_answer_cites_only_supplied_articles(customer, articles, fake_ai, api):
    fake_ai.push({"answer": "Click Forgot password; the link expires after 30 minutes.",
                  "sufficient_information": True,
                  "used_article_ids": [articles["password"].id, articles["internal"].id, 424242]})
    res = api(customer).post("/api/v1/knowledge-base/ask/", {"question": "How do I reset my password?"},
                             format="json")
    assert res.status_code == 200
    assert res.data["sufficient_information"] is True and res.data["ai_generated"] is True
    assert [c["id"] for c in res.data["citations"]] == [articles["password"].id]
    prompt = fake_ai.calls[-1]["prompt"]
    assert "Internal escalation steps" not in prompt  # customers' questions never include internal articles


def test_kb_answer_without_matching_articles_skips_ai(customer, articles, fake_ai, api):
    res = api(customer).post("/api/v1/knowledge-base/ask/", {"question": "zebra migration patterns"}, format="json")
    assert res.status_code == 200
    assert res.data["sufficient_information"] is False and res.data["ai_generated"] is False
    assert res.data["citations"] == [] and fake_ai.calls == []


def test_kb_answer_insufficient_has_no_citations(customer, articles, fake_ai, api):
    fake_ai.push(KnowledgeAnswerResult(answer="The knowledge base does not cover this.",
                                       sufficient_information=False, used_article_ids=[articles["refund"].id]))
    res = api(customer).post("/api/v1/knowledge-base/ask/", {"question": "refund for monthly plan in crypto?"},
                             format="json")
    assert res.data["sufficient_information"] is False and res.data["citations"] == []


def test_kb_ask_validation_and_failure(customer, articles, fake_ai, api):
    assert api(customer).post("/api/v1/knowledge-base/ask/", {"question": "hi"}, format="json").status_code == 400
    assert api(customer).post("/api/v1/knowledge-base/ask/", {"question": "x" * 501},
                              format="json").status_code == 400
    fake_ai.push(AIServiceError())
    res = api(customer).post("/api/v1/knowledge-base/ask/", {"question": "reset password"}, format="json")
    assert res.status_code == 503


def test_ai_endpoints_are_rate_limited(customer, agent, make_ticket, api, monkeypatch):
    from apps.core.throttling import AIRateThrottle

    monkeypatch.setattr(AIRateThrottle, "THROTTLE_RATES", {**AIRateThrottle.THROTTLE_RATES, "ai": "2/min"})
    ticket = make_ticket(customer)
    codes = [api(agent).post(f"/api/v1/tickets/{ticket.id}/summarize/").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
