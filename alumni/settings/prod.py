"""Production overrides — strict security, HSTS, no debug."""

from .staging import *  # noqa: F401,F403
from .staging import env

DEBUG = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Inherited from staging: EMAIL_BACKEND is env-driven (default
# ResendBackend) and require_shared_cache() has already run. Re-reading the
# env var here keeps prod explicit without re-hardcoding the value — the
# launch runbook's email rollback depends on it staying overridable.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="alumni.email.ResendBackend")
PASSWORD_RESET_TIMEOUT = 7 * 24 * 60 * 60  # 7 days for the post-approval password-set link
