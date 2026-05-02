"""Local development overrides."""

from .base import *  # noqa: F401,F403
from .base import STORAGES

DEBUG = True
ALLOWED_HOSTS = ["*"]
INTERNAL_IPS = ["127.0.0.1"]

# Disable rate limiting in dev/tests so repeated POST requests aren't blocked.
RATELIMIT_ENABLE = False

# Use the non-manifest staticfiles storage in dev/tests so {% static %} works
# without requiring `collectstatic`. Production keeps the hashed manifest.
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
