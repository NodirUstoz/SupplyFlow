"""
Development-specific Django settings for SupplyFlow.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Use console email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable throttling in development
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}  # noqa: F405

# Shorter token lifetime for dev testing
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(hours=2)  # noqa: F405

# Allow all CORS origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Additional logging for development
LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "WARNING",
    "propagate": False,
}
