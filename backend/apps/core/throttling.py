from rest_framework.throttling import UserRateThrottle


class AIRateThrottle(UserRateThrottle):
    """Per-user limit for endpoints that call Gemini (rate set by THROTTLE_AI)."""

    scope = "ai"
