"""
Middleware for organization-scoped request context.

Extracts the organization from the authenticated user and attaches it to
the request object so that views and serializers can access it without
repeatedly querying the user model.
"""

import logging
import time

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class OrganizationMiddleware(MiddlewareMixin):
    """
    Attach `request.organization` for authenticated users.

    After authentication, the user's organization is read once and stored on
    the request object.  Views can then use ``request.organization`` instead
    of ``request.user.organization`` to keep things concise and consistent.

    If the user is not authenticated or has no organization, the attribute is
    set to ``None``.
    """

    def process_request(self, request):
        if hasattr(request, "user") and request.user.is_authenticated:
            request.organization = getattr(request.user, "organization", None)
        else:
            request.organization = None


class RequestTimingMiddleware(MiddlewareMixin):
    """
    Log the duration of every API request.

    Adds an ``X-Request-Duration-Ms`` response header and emits a DEBUG
    log line for slow requests (> 500 ms).
    """

    SLOW_REQUEST_THRESHOLD_MS = 500

    def process_request(self, request):
        request._start_time = time.monotonic()

    def process_response(self, request, response):
        start = getattr(request, "_start_time", None)
        if start is None:
            return response

        duration_ms = (time.monotonic() - start) * 1000
        response["X-Request-Duration-Ms"] = f"{duration_ms:.1f}"

        if duration_ms > self.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                "Slow request: %s %s took %.1f ms",
                request.method,
                request.path,
                duration_ms,
            )

        return response


class AuditHeaderMiddleware(MiddlewareMixin):
    """
    Inject common audit / correlation headers into responses.

    - ``X-Organization-Id``: the current organization UUID (if any)
    - ``X-Request-Id``: a unique request identifier carried through
      from the client or generated server-side.
    """

    def process_request(self, request):
        import uuid

        request_id = request.headers.get("X-Request-Id")
        if not request_id:
            request_id = str(uuid.uuid4())
        request.request_id = request_id

    def process_response(self, request, response):
        response["X-Request-Id"] = getattr(request, "request_id", "")
        org = getattr(request, "organization", None)
        if org:
            response["X-Organization-Id"] = str(org.id)
        return response
