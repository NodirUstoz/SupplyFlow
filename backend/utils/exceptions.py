"""
Custom exception handler for the SupplyFlow API.

Provides a consistent error response structure:
{
    "error": true,
    "status_code": 400,
    "message": "Human-readable summary",
    "errors": { ... field-level details ... }
}
"""

import logging

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler and normalizes the response body
    into a uniform error envelope.
    """

    # Convert Django exceptions to DRF equivalents so they pass through DRF
    if isinstance(exc, DjangoValidationError):
        exc = DRFValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
    elif isinstance(exc, Http404):
        from rest_framework.exceptions import NotFound
        exc = NotFound()
    elif isinstance(exc, PermissionDenied):
        from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
        exc = DRFPermissionDenied()

    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception -- log and return a generic 500
        logger.exception(
            "Unhandled exception in %s %s",
            context.get("request", {}).method if hasattr(context.get("request", {}), "method") else "UNKNOWN",
            context.get("request", {}).path if hasattr(context.get("request", {}), "path") else "UNKNOWN",
        )
        return Response(
            {
                "error": True,
                "status_code": 500,
                "message": "An unexpected error occurred.",
                "errors": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    error_body = _build_error_body(response, exc)
    response.data = error_body
    return response


def _build_error_body(response, exc):
    """Build the standardized error dictionary."""

    status_code = response.status_code
    errors = {}

    if isinstance(response.data, dict):
        # Field-level errors from serializer validation
        errors = {
            key: value if isinstance(value, list) else [value]
            for key, value in response.data.items()
            if key != "detail"
        }
        detail = response.data.get("detail", None)
    elif isinstance(response.data, list):
        detail = response.data
    else:
        detail = str(response.data)

    # Derive a human-readable message
    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        message = "Authentication credentials were not provided or are invalid."
    elif detail:
        message = str(detail) if not isinstance(detail, list) else "; ".join(str(d) for d in detail)
    elif errors:
        first_field = next(iter(errors))
        first_error = errors[first_field][0] if errors[first_field] else "Validation error."
        message = f"{first_field}: {first_error}"
    else:
        message = "An error occurred."

    return {
        "error": True,
        "status_code": status_code,
        "message": message,
        "errors": errors,
    }


class ServiceUnavailable(APIException):
    """Raised when an external service (carrier API, etc.) is unreachable."""

    status_code = 503
    default_detail = "Service temporarily unavailable. Please try again later."
    default_code = "service_unavailable"


class BusinessLogicError(APIException):
    """Raised for domain-rule violations that don't map to 400 validation errors."""

    status_code = 422
    default_detail = "The request could not be processed due to a business rule violation."
    default_code = "business_logic_error"
