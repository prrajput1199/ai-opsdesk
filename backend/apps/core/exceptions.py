"""
Consistent JSON error responses.

DRF already turns its own exceptions (ValidationError, NotFound, ...) into JSON.
This handler also converts Django's ValidationError and any unexpected exception
into JSON, and makes sure no stack trace or internal detail reaches the client.
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ServiceUnavailable(exceptions.APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "This service is temporarily unavailable. Please try again later."
    default_code = "service_unavailable"


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages}
        exc = exceptions.ValidationError(detail=detail)
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is not None:
        return response

    # Unexpected error: log it server-side with the traceback, return a generic message.
    view = context.get("view")
    logger.exception("Unhandled API error in %s", view.__class__.__name__ if view else "unknown view")
    return Response(
        {"detail": "An unexpected error occurred. Please try again later."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
