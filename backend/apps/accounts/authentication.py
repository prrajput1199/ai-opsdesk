"""
JWT authentication from HTTP-only cookies.

Why cookies instead of localStorage? JavaScript cannot read an HTTP-only cookie, so an
XSS bug cannot steal the token. The trade-off is that the browser sends cookies
automatically, which opens the door to CSRF - so every cookie-authenticated request
also goes through Django's CSRF check (the frontend sends the X-CSRFToken header).
"""

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication


def enforce_csrf(request):
    """Run Django's CSRF validation (same approach as DRF's SessionAuthentication)."""

    def dummy_get_response(_request):  # pragma: no cover
        return None

    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw_token:
            return None
        validated_token = self.get_validated_token(raw_token)  # raises 401 if invalid/expired
        user = self.get_user(validated_token)  # raises 401 if the user is inactive or deleted
        enforce_csrf(request)
        return user, validated_token

    def authenticate_header(self, request):
        # Makes DRF answer 401 (not 403) for unauthenticated requests, so the frontend knows
        # to try a token refresh.
        return 'Cookie realm="api"'
