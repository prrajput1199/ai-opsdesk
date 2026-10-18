"""Settings used by pytest. Requires a reachable PostgreSQL (DATABASE_URL)."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault("DATABASE_URL", "postgres://opsdesk:opsdesk@localhost:5432/opsdesk")

from .settings import *  # noqa: E402,F401,F403

SECURE_SSL_REDIRECT = False
AUTH_COOKIE_SECURE = False
GEMINI_API_KEY = "test-key"  # never used: every Gemini call is mocked in tests
AI_CLASSIFICATION_MODE = "sync"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests only
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405 (no collected static files in tests)
