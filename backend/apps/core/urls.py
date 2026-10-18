from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.urls import path


@extend_schema(
    responses=inline_serializer("Health", {"status": serializers.CharField(), "database": serializers.CharField()}),
    auth=[],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    """Liveness/readiness check used by Docker and hosting platforms."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
    except Exception:  # pragma: no cover - only when the DB is down
        db = "unavailable"
    return Response({"status": "ok" if db == "ok" else "degraded", "database": db}, status=200 if db == "ok" else 503)


urlpatterns = [path("health/", health, name="health")]
