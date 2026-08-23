"""Staging environment — basic-auth gated, mirrors prod otherwise."""

import environ
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .base import *  # noqa: F401,F403
from .base import (
    CLOUDINARY_CLIENT_PATH,
    CLOUDINARY_CLOUD_NAME,
    MIDDLEWARE,
    STORAGE_ACCESS_KEY_ID,
    STORAGE_BACKUP_REQUIRED,
    STORAGE_BUCKET_NAME,
    STORAGE_CLIENT_PATH,
    STORAGE_ENDPOINT_URL,
    STORAGE_SECRET_ACCESS_KEY,
)

env = environ.Env()

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# SECURE_SSL_REDIRECT is env-overridable so docker-compose (HTTP only) can disable it.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
# Railway's internal healthcheck probe hits the container directly over HTTP
# (no X-Forwarded-Proto), so SecurityMiddleware would otherwise return a 301
# redirect to https. Exempting /health from the redirect lets the probe see
# a real 200 response. The pattern is matched against request.path with the
# leading slash stripped (Django's documented behavior).
SECURE_REDIRECT_EXEMPT = [r"^health$"]
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
# Explicit SameSite stance — Lax matches Django's default but locking it down
# so prod inherits an unambiguous posture and any future override is intentional.
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE = env("CSRF_COOKIE_SAMESITE", default="Lax")
# Required by Django 4+ for cross-origin POST (allauth login over HTTPS)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Hosts that MUST be allowed regardless of the operator's ALLOWED_HOSTS
# env var. These are platform-coupled values the operator should not have
# to know about — Railway sends its internal healthcheck probe with
# `Host: healthcheck.railway.app`, and `.up.railway.app` does not match it
# (Django's leading-dot wildcard matches subdomains of `up.railway.app`,
# not siblings under `railway.app`).
#
# We merge these into whatever ALLOWED_HOSTS the operator set, so the
# deploy can never go red just because the env var omitted them.
_PLATFORM_REQUIRED_HOSTS = ["healthcheck.railway.app"]

_user_hosts = env.list(
    "ALLOWED_HOSTS",
    default=[
        "staging.villageretrouvailles.com",
        ".up.railway.app",
        "localhost",
        "127.0.0.1",
    ],
)
# dict.fromkeys preserves order and dedupes.
ALLOWED_HOSTS = list(dict.fromkeys(_PLATFORM_REQUIRED_HOSTS + _user_hosts))

# Defense-in-depth: prod sets X_FRAME_OPTIONS="DENY" too, but staging should
# match the production posture so embedding-in-iframe surprises surface here
# first, not after a prod release.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

BASIC_AUTH_REQUIRED = env.bool("BASIC_AUTH_REQUIRED", default=True)
BASIC_AUTH_USERNAME = env("BASIC_AUTH_USERNAME", default="")
BASIC_AUTH_PASSWORD = env("BASIC_AUTH_PASSWORD", default="")

MIDDLEWARE = ["core.middleware.BasicAuthMiddleware"] + MIDDLEWARE
# Report-only CSP: observation before enforcement (see the middleware
# docstring). Prod-shaped environments only — dev noise helps nobody.
MIDDLEWARE = MIDDLEWARE + ["core.middleware.ContentSecurityPolicyReportOnlyMiddleware"]

# Catch a deploy-time misconfiguration: the operator pointed at the real
# Cloudinary client but forgot to set CLOUDINARY_CLOUD_NAME, so it would
# default to "fake-cloud" and produce broken upload URLs at runtime.
if CLOUDINARY_CLIENT_PATH.endswith("RealCloudinary") and CLOUDINARY_CLOUD_NAME == "fake-cloud":
    raise ImproperlyConfigured(
        "CLOUDINARY_CLIENT_PATH=RealCloudinary requires CLOUDINARY_CLOUD_NAME "
        "to be set to your real Cloudinary cloud (currently 'fake-cloud')."
    )

# P6a: defense-in-depth for the media-backup cron service. STORAGE_BACKUP_REQUIRED
# is set to true on the media-backup-cron service only; if the operator forgot
# any of the credential vars, refuse to boot rather than fail silently a week
# later when the first scheduled run hits.
if STORAGE_BACKUP_REQUIRED and STORAGE_CLIENT_PATH.endswith("RealStorage"):
    if not all(
        [
            STORAGE_BUCKET_NAME,
            STORAGE_ENDPOINT_URL,
            STORAGE_ACCESS_KEY_ID,
            STORAGE_SECRET_ACCESS_KEY,
        ],
    ):
        raise ImproperlyConfigured(
            "STORAGE_BACKUP_REQUIRED=true with RealStorage selected, but one or more "
            "of STORAGE_BUCKET_NAME / STORAGE_ENDPOINT_URL / STORAGE_ACCESS_KEY_ID / "
            "STORAGE_SECRET_ACCESS_KEY is missing.",
        )

# Env-driven (default ResendBackend) so the launch runbook's "emails are
# bouncing en masse" rollback — `railway variables --remove EMAIL_BACKEND`
# / set it to the console backend — actually takes effect. Hardcoding it
# here made that documented rollback a silent no-op.
# F-29: these two fail SILENTLY, and the first symptom is user-visible.
#
# SITE_URL feeds every magic link. Left at base.py's http://localhost:8000
# default, the roster import would DM ~200 members a link to their own machine
# — and the operator would find out from the members. 127.0.0.1 is the same
# footgun spelled differently. docker-compose.yml (the local prod-repro
# stack, where a localhost SITE_URL is the *correct* value) opts out
# explicitly via SITE_URL_ALLOW_LOCAL — a deployed service never sets it.
_local_site_url = SITE_URL.startswith(("http://localhost", "http://127.0.0.1"))  # noqa: F405
if _local_site_url and not env.bool("SITE_URL_ALLOW_LOCAL", default=False):
    raise ImproperlyConfigured(
        "SITE_URL is still a localhost value. Every magic link and email "
        "URL would point at localhost. Set SITE_URL on the service (or, for "
        "the local docker-compose stack only, SITE_URL_ALLOW_LOCAL=true)."
    )

EMAIL_BACKEND = env("EMAIL_BACKEND", default="alumni.email.ResendBackend")

# Resolve the dotted path now. Django only imports the backend at the first
# get_connection(), so a value that exists nowhere in the image (prod ran for
# weeks with django_resend.EmailBackend) boots green and fails on the first
# password-set email a member is waiting for. The name-based Resend guard
# below cannot see that case.
try:
    import_string(EMAIL_BACKEND)
except ImportError as exc:
    raise ImproperlyConfigured(
        f"EMAIL_BACKEND {EMAIL_BACKEND!r} cannot be imported: {exc}. "
        "This platform's backend is alumni.email.ResendBackend."
    ) from exc

# ResendBackend without a key does not fail loudly at boot — it fails at the
# first send, which is the password-set email a new member is waiting for.
if EMAIL_BACKEND.endswith("ResendBackend") and not RESEND_API_KEY:  # noqa: F405
    raise ImproperlyConfigured(
        "EMAIL_BACKEND is ResendBackend but RESEND_API_KEY is empty. Every "
        "outbound email would fail at send time. Set RESEND_API_KEY, or point "
        "EMAIL_BACKEND at the console backend."
    )
PASSWORD_RESET_TIMEOUT = 7 * 24 * 60 * 60  # 7 days for the post-approval password-set link

# Allauth's login/reset/signup throttles key on ITS OWN client-IP resolver,
# not on RATELIMIT_IP_META_KEY. Left at the default (REMOTE_ADDR = Railway's
# edge proxy), every visitor shares one bucket: a single attacker can exhaust
# the login/reset limits platform-wide. 1 = take the rightmost X-Forwarded-For
# token — the hop Railway actually observed, same choice as alumni/ratelimit.py.
ALLAUTH_TRUSTED_PROXY_COUNT = 1

# Every rate limiter (django-ratelimit decorators, allauth's login throttle)
# rides on the default cache. base.py falls back to a per-process LocMemCache
# when neither CACHE_BACKEND=db nor REDIS_URL is set — behind N gunicorn
# workers that means N independent counters that also reset on every deploy,
# so the throttles silently don't throttle. Prod-shaped environments default
# to the Postgres-backed DatabaseCache instead: no new infrastructure, and
# docker/entrypoint.sh creates the table on boot.
if CACHES["default"]["BACKEND"].endswith("locmem.LocMemCache"):  # noqa: F405
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "alumni_cache",
        },
    }
