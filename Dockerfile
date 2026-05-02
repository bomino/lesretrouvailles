# syntax=docker/dockerfile:1.7

# ---- Stage 1: build CSS with Tailwind ----
FROM node:20-alpine AS css-builder

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY tailwind.config.js postcss.config.js tailwind.theme.json ./
COPY DESIGN.md ./
COPY static/ ./static/
COPY templates/ ./templates/
COPY core/ ./core/
COPY members/ ./members/

RUN npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=alumni.settings.staging

# System deps: gettext for compilemessages, libpq for psycopg, curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        gettext \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python runtime deps. Listed explicitly (rather than `pip install -e .`)
# so this layer caches until the dep set itself changes, and we don't need the
# source tree present at install time. The Django app runs from /app via the
# default working dir; no editable install needed.
RUN pip install --upgrade pip && pip install \
    "django>=5.0,<5.1" \
    "psycopg[binary]>=3.1" \
    "django-allauth>=0.61" \
    "django-environ>=0.11" \
    "whitenoise>=6.6" \
    "gunicorn>=21" \
    "cloudinary>=1.40" \
    "django-ratelimit>=4.1" \
    "markdown>=3.6"

# Copy source code
COPY pyproject.toml ./
COPY alumni/ ./alumni/
COPY core/ ./core/
COPY members/ ./members/
COPY templates/ ./templates/
COPY locale/ ./locale/
COPY manage.py ./

# Copy compiled CSS from stage 1
COPY --from=css-builder /build/static/ ./static/

# Build-time steps that bake the image. SECRET_KEY etc. are dummies used only
# to satisfy Django settings parsing; collectstatic and compilemessages do not
# touch the database. Real values are injected by Railway at runtime.
RUN SECRET_KEY=build-time-only-not-used \
    DJANGO_SETTINGS_MODULE=alumni.settings.staging \
    DATABASE_URL=postgres://x:x@localhost:5432/x \
    ALLOWED_HOSTS=localhost \
    BASIC_AUTH_REQUIRED=false \
    SECURE_SSL_REDIRECT=false \
    python manage.py compilemessages -l fr

RUN SECRET_KEY=build-time-only-not-used \
    DJANGO_SETTINGS_MODULE=alumni.settings.staging \
    DATABASE_URL=postgres://x:x@localhost:5432/x \
    ALLOWED_HOSTS=localhost \
    BASIC_AUTH_REQUIRED=false \
    SECURE_SSL_REDIRECT=false \
    python manage.py collectstatic --noinput

# Entrypoint
COPY docker/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Healthcheck — Django's /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
