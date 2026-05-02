"""Staging environment — basic-auth gated, mirrors prod otherwise."""

import environ

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

env = environ.Env()

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# SECURE_SSL_REDIRECT is env-overridable so docker-compose (HTTP only) can disable it.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
# Required by Django 4+ for cross-origin POST (allauth login over HTTPS)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ALLOWED_HOSTS overridable so Railway and the eventual custom domain
# can be injected without touching code.
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["staging.villageretrouvailles.com", ".up.railway.app", "localhost", "127.0.0.1"],
)

BASIC_AUTH_REQUIRED = env.bool("BASIC_AUTH_REQUIRED", default=True)
BASIC_AUTH_USERNAME = env("BASIC_AUTH_USERNAME", default="")
BASIC_AUTH_PASSWORD = env("BASIC_AUTH_PASSWORD", default="")

MIDDLEWARE = ["core.middleware.BasicAuthMiddleware"] + MIDDLEWARE
