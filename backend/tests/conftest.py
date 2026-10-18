"""
Shared fixtures.

Every test runs with a fake Gemini client (autouse), so no test can reach the real API,
need a key, or cost money. Tests that need specific AI behaviour queue responses/errors
on the `fake_ai` fixture.
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Team, User
from apps.ai.schemas import ClassificationResult, KnowledgeAnswerResult, ReplyResult, SummaryResult
from apps.knowledge_base.models import KnowledgeBaseArticle
from apps.tickets.models import Category
from apps.tickets.services import create_ticket

PASSWORD = "Str0ng-Pass!2026"

DEFAULT_AI_RESPONSES = {
    ClassificationResult: {
        "category": "Billing", "priority": "HIGH", "summary": "Customer was charged twice.",
        "suggested_first_response": "Thanks for reporting this. We're checking the charges now.",
        "needs_human_review": False, "reason": "Payment issue affecting the customer.",
    },
    SummaryResult: {"summary": "The customer reports a duplicate charge and asks for a refund."},
    ReplyResult: {"reply": "Hello, we have refunded the duplicate charge. The Support Team", "used_article_ids": []},
    KnowledgeAnswerResult: {"answer": "Use the Forgot password link.", "sufficient_information": True,
                            "used_article_ids": []},
}


class FakeGemini:
    model = "fake-gemini"
    is_configured = True

    def __init__(self):
        self.queue = []
        self.calls = []

    def push(self, item):
        """Queue a dict (validated through the schema), a schema instance, or an exception."""
        self.queue.append(item)

    def generate_structured(self, *, system_instruction, prompt, schema, **kwargs):
        self.calls.append({"system": system_instruction, "prompt": prompt, "schema": schema})
        item = self.queue.pop(0) if self.queue else DEFAULT_AI_RESPONSES[schema]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return schema.model_validate(item)
        return item


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    fake = FakeGemini()
    monkeypatch.setattr("apps.ai.client.get_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()  # resets throttling counters between tests
    yield
    cache.clear()


@pytest.fixture
def teams(db):
    return {
        "tech": Team.objects.create(name="Technical Support"),
        "billing": Team.objects.create(name="Billing"),
    }


@pytest.fixture
def categories(teams):
    return {
        "tech": Category.objects.create(name="Technical Issue", team=teams["tech"]),
        "billing": Category.objects.create(name="Billing", team=teams["billing"]),
        "general": Category.objects.create(name="General Inquiry"),
    }


def _user(email, role, team=None, **extra):
    return User.objects.create_user(email=email, password=PASSWORD, first_name=email.split("@")[0].title(),
                                    last_name="Test", role=role, team=team, **extra)


@pytest.fixture
def admin_user(db):
    return _user("admin@example.com", User.Role.ADMIN)


@pytest.fixture
def agent(teams):
    return _user("agent@example.com", User.Role.AGENT, teams["tech"])


@pytest.fixture
def billing_agent(teams):
    return _user("billing@example.com", User.Role.AGENT, teams["billing"])


@pytest.fixture
def customer(db):
    return _user("customer@example.com", User.Role.CUSTOMER)


@pytest.fixture
def other_customer(db):
    return _user("other@example.com", User.Role.CUSTOMER)


@pytest.fixture
def api():
    """Returns a function giving an APIClient authenticated as `user` (or anonymous)."""

    def make(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return make


@pytest.fixture
def make_ticket(categories, fake_ai):
    def make(customer, category="tech", title="Cannot log in to dashboard", description=None):
        return create_ticket(
            customer=customer, title=title,
            description=description or "The login page shows an error every time I try to sign in.",
            category=categories[category] if category else None,
        )

    return make


@pytest.fixture
def articles(categories, admin_user):
    def art(title, content, status="published", visibility="public", category="tech"):
        from django.utils.text import slugify

        return KnowledgeBaseArticle.objects.create(
            title=title, slug=slugify(title), content=content, status=status, visibility=visibility,
            category=categories[category], author=admin_user,
        )

    return {
        "password": art("How to reset your password",
                        "Click Forgot password on the login page. The reset link expires after 30 minutes."),
        "refund": art("Refund policy", "Annual plans can be refunded within 14 days. Duplicate charges are refunded.",
                      category="billing"),
        "internal": art("Escalation playbook", "Internal escalation steps for outages and password lockouts.",
                        visibility="internal"),
        "draft": art("SSO setup draft", "Draft notes about password-less single sign-on.", status="draft"),
    }
