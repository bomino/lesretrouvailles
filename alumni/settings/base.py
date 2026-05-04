"""Settings shared across all environments. Read everything from env."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])
SITE_URL = env("SITE_URL", default="http://localhost:8000").strip().rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "allauth",
    "allauth.account",
    "core",
    "members",
    "cooptation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "alumni.middleware.LoginRequiredMiddleware",
    "alumni.middleware.ConsentRequiredMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "alumni.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "members.context.member_preferences",
                "core.context_processors.site",
                "cooptation.context_processors.pending_vouches_count",
            ],
        },
    },
]

WSGI_APPLICATION = "alumni.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SITE_ID = 1

# i18n — French only for V1, gettext machinery active for Phase 4 expansion
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Africa/Niamey"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="Les Retrouvailles <noreply@villageretrouvailles.com>",
)

# django-allauth (older universal config style for compatibility)
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
# Foundation runs without an outbound email backend. P3 will switch this
# to "mandatory" once Resend + SPF/DKIM/DMARC are wired (spec §7.3).
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ADAPTER = "core.allauth_adapter.NoSignupAdapter"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# P3.1: 90-day sliding session lifetime so parrains stay logged in across
# cooptation email clicks (~2 weeks per request × multiple requests in flight).
# SAVE_EVERY_REQUEST trades one session-row write per request for sliding
# expiry — negligible cost at our scale, big UX win.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90 days
SESSION_SAVE_EVERY_REQUEST = True

# Cloudinary — overridden per environment. Tests fall through to the fake.
CLOUDINARY_CLIENT_PATH = env(
    "CLOUDINARY_CLIENT_PATH",
    default="alumni.cloudinary.FakeCloudinary",
)
CLOUDINARY_CLOUD_NAME = env("CLOUDINARY_CLOUD_NAME", default="fake-cloud")

# Real Cloudinary credentials (only required when CLOUDINARY_CLIENT_PATH points at RealCloudinary)
CLOUDINARY_API_KEY = env("CLOUDINARY_API_KEY", default="")
CLOUDINARY_API_SECRET = env("CLOUDINARY_API_SECRET", default="")
CLOUDINARY_URL = env(
    "CLOUDINARY_URL",
    default=f"cloudinary://{CLOUDINARY_API_KEY}:{CLOUDINARY_API_SECRET}@{CLOUDINARY_CLOUD_NAME}",
)

# Rate limiting and other cache use (django-ratelimit, etc).
#
# Backend selection is env-driven so the same image runs in dev (LocMem),
# staging (DatabaseCache so all gunicorn workers share state), and prod
# (Redis once we provision it).
#
# - CACHE_BACKEND=db     -> Postgres-backed DatabaseCache (cross-worker, persistent)
# - REDIS_URL is set     -> Redis (preferred for prod)
# - otherwise            -> LocMemCache (single-process, fine for tests)
_CACHE_BACKEND = env("CACHE_BACKEND", default="")
_REDIS_URL = env("REDIS_URL", default="")

if _CACHE_BACKEND == "db":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "alumni_cache",
        },
    }
elif _REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _REDIS_URL,
        },
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "alumni-default",
        },
    }

# Login + consent gating
LOGIN_REQUIRED_WHITELIST = [
    "/",
    "/health",
    "/accounts/",
    "/static/",
    "/media/",
    "/inscription/",
    "/questionnaire/",
    "/sitemap.xml",
    "/robots.txt",
    "/retrait/",
]

# P4a: feature flag gating the public ghost list (Nous recherchons aussi…).
# Default off so admins can pre-populate via Django admin without exposing
# names publicly until P4b ships the public removal flow. Operators flip
# this to True via Railway env vars when the removal flow is live.
PUBLIC_GHOST_LIST_ENABLED = env.bool("PUBLIC_GHOST_LIST_ENABLED", default=False)

# P4a: Cloudflare Web Analytics token. Frontend beacon identifier (not a
# secret — appears in HTML). Beacon snippet is omitted from base.html when
# blank, so leaving this unset disables analytics cleanly.
CLOUDFLARE_ANALYTICS_TOKEN = env("CLOUDFLARE_ANALYTICS_TOKEN", default="")

# Resend email
RESEND_API_KEY = env("RESEND_API_KEY", default="")
