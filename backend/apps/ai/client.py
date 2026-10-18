"""
Thin wrapper around the Google Gen AI SDK (`google-genai`).

Responsibilities:
- read the API key and model name from settings (never hardcoded)
- request timeouts and a small number of retries for transient errors
- ask Gemini for JSON that matches a Pydantic schema, then validate it again locally
- translate SDK/network errors into a few app-level exceptions with safe messages

Nothing in this module logs prompts, responses or keys.
"""

import logging
import time

import httpx
from django.conf import settings
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class AIError(Exception):
    """Base class. `user_message` is safe to show to end users."""

    user_message = "The AI assistant is temporarily unavailable. Please try again later."


class AINotConfigured(AIError):
    user_message = "AI features are not configured on this server (missing GEMINI_API_KEY)."


class AIRateLimited(AIError):
    user_message = "The AI service is receiving too many requests. Please try again in a minute."


class AIServiceError(AIError):
    pass


class AIResponseInvalid(AIError):
    user_message = "The AI returned a response that could not be validated. Please try again."


class GeminiClient:
    def __init__(self, api_key=None, model=None, timeout_seconds=None, max_retries=None):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout_seconds = timeout_seconds or settings.GEMINI_TIMEOUT_SECONDS
        self.max_retries = settings.GEMINI_MAX_RETRIES if max_retries is None else max_retries
        self._sdk_client = None

    @property
    def is_configured(self):
        return bool(self.api_key)

    def _client(self):
        if self._sdk_client is None:
            self._sdk_client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
            )
        return self._sdk_client

    def generate_structured(self, *, system_instruction, prompt, schema: type[BaseModel],
                            temperature=0.2, max_output_tokens=4096) -> BaseModel:
        """Call Gemini and return an instance of `schema`, or raise an AIError subclass."""
        if not self.is_configured:
            raise AINotConfigured()

        prompt = prompt[: settings.AI_MAX_INPUT_CHARS]
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        last_error: AIError = AIServiceError()
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                response = self._client().models.generate_content(model=self.model, contents=prompt, config=config)
            except genai_errors.ClientError as exc:
                if exc.code == 429:
                    last_error = AIRateLimited()
                    logger.warning("Gemini rate limited (attempt %s)", attempt + 1)
                else:
                    logger.error("Gemini client error: HTTP %s %s", exc.code, getattr(exc, "status", ""))
                    raise AIServiceError() from exc
            except genai_errors.ServerError as exc:
                logger.warning("Gemini server error: HTTP %s (attempt %s)", exc.code, attempt + 1)
                last_error = AIServiceError()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning("Gemini network error: %s (attempt %s)", exc.__class__.__name__, attempt + 1)
                last_error = AIServiceError()
            else:
                logger.info("Gemini call ok model=%s schema=%s %.1fs", self.model, schema.__name__,
                            time.monotonic() - started)
                return self._parse(response, schema)

            if attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 4))
        raise last_error

    @staticmethod
    def _parse(response, schema):
        text = getattr(response, "text", None)
        if not text:
            logger.warning("Gemini returned an empty response (possibly blocked by safety filters)")
            raise AIResponseInvalid()
        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            logger.warning("Gemini response failed schema validation: %s error(s)", exc.error_count())
            raise AIResponseInvalid() from exc


def get_client() -> GeminiClient:
    """Factory used by services; tests patch this to inject a fake client."""
    return GeminiClient()
