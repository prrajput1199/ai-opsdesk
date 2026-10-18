"""
Structured output schemas.

The same Pydantic model is (1) sent to Gemini as `response_schema` so it returns JSON in
this shape, and (2) used to validate that JSON locally. Validators below only run locally
(they are not part of the JSON schema), so they can trim and reject bad values safely.
"""

from typing import Literal

from pydantic import BaseModel, field_validator

Priority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]


def _clean_text(value: str, limit: int, *, required=True) -> str:
    value = (value or "").strip()
    if required and not value:
        raise ValueError("must not be empty")
    return value[:limit]


class ClassificationResult(BaseModel):
    category: str
    priority: Priority
    summary: str
    suggested_first_response: str
    needs_human_review: bool
    reason: str

    @field_validator("category")
    @classmethod
    def _category(cls, v):
        return _clean_text(v, 80, required=False)

    @field_validator("summary")
    @classmethod
    def _summary(cls, v):
        return _clean_text(v, 1200)

    @field_validator("suggested_first_response")
    @classmethod
    def _first_response(cls, v):
        return _clean_text(v, 3000)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v):
        return _clean_text(v, 500, required=False)


class SummaryResult(BaseModel):
    summary: str

    @field_validator("summary")
    @classmethod
    def _summary(cls, v):
        return _clean_text(v, 2000)


class ReplyResult(BaseModel):
    reply: str
    used_article_ids: list[int]

    @field_validator("reply")
    @classmethod
    def _reply(cls, v):
        return _clean_text(v, 5000)


class KnowledgeAnswerResult(BaseModel):
    answer: str
    sufficient_information: bool
    used_article_ids: list[int]

    @field_validator("answer")
    @classmethod
    def _answer(cls, v):
        return _clean_text(v, 4000)
