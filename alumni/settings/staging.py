"""Staging environment — basic-auth gated, mirrors prod otherwise."""

import environ

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

env = environ.Env()

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Required by Django 4+ for cross-origin POST (allauth login over HTTPS)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

BASIC_AUTH_REQUIRED = env.bool("BASIC_AUTH_REQUIRED", default=True)
BASIC_AUTH_USERNAME = env("BASIC_AUTH_USERNAME", default="")
BASIC_AUTH_PASSWORD = env("BASIC_AUTH_PASSWORD", default="")

MIDDLEWARE = ["core.middleware.BasicAuthMiddleware"] + MIDDLEWARE
