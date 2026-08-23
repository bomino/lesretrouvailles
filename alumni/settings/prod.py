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
# ResendBackend) and the LocMem→DatabaseCache swap at the bottom of
# staging.py has already run. Re-reading the env var here keeps prod
# explicit without re-hardcoding the value — the launch runbook's email
# rollback depends on it staying overridable.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="alumni.email.ResendBackend")
PASSWORD_RESET_TIMEOUT = 7 * 24 * 60 * 60  # 7 days for the post-approval password-set link

# staging.py defaults the basic-auth gate ON, which is right for staging and
# wrong here: staging credentials copied onto the prod service would 401 the
# whole public site while /health (which bypasses the gate) stays green.
# Production is open by default; the env var is the explicit opt-in.
BASIC_AUTH_REQUIRED = env.bool("BASIC_AUTH_REQUIRED", default=False)
