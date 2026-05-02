"""Staging environment — basic-auth gated, mirrors prod otherwise."""

import environ
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import CLOUDINARY_CLIENT_PATH, CLOUDINARY_CLOUD_NAME, MIDDLEWARE

env = environ.Env()

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# SECURE_SSL_REDIRECT is env-overridable so docker-compose (HTTP only) can disable it.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
# Explicit SameSite stance — Lax matches Django's default but locking it down
# so prod inherits an unambiguous posture and any future override is intentional.
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE = env("CSRF_COOKIE_SAMESITE", default="Lax")
# Required by Django 4+ for cross-origin POST (allauth login over HTTPS)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ALLOWED_HOSTS overridable so Railway and the eventual custom domain
# can be injected without touching code.
#
# `healthcheck.railway.app` is the hostname Railway's internal probe sends
# in the Host header. Django's `.up.railway.app` wildcard only matches
# subdomains of `up.railway.app`, NOT siblings under `railway.app`, so
# the probe must be listed explicitly or every healthcheck returns 400
# (DisallowedHost) and the deploy never goes green.
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=[
        "staging.villageretrouvailles.com",
        ".up.railway.app",
        "healthcheck.railway.app",
        "localhost",
        "127.0.0.1",
    ],
)

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

# Catch a deploy-time misconfiguration: the operator pointed at the real
# Cloudinary client but forgot to set CLOUDINARY_CLOUD_NAME, so it would
# default to "fake-cloud" and produce broken upload URLs at runtime.
if CLOUDINARY_CLIENT_PATH.endswith("RealCloudinary") and CLOUDINARY_CLOUD_NAME == "fake-cloud":
    raise ImproperlyConfigured(
        "CLOUDINARY_CLIENT_PATH=RealCloudinary requires CLOUDINARY_CLOUD_NAME "
        "to be set to your real Cloudinary cloud (currently 'fake-cloud')."
    )
