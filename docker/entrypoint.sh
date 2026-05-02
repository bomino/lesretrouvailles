#!/usr/bin/env bash
set -euo pipefail

# Apply migrations on every boot. Idempotent and fast.
python manage.py migrate --noinput

# Database-backed cache table. Idempotent — safe to run on every boot.
# Only used when CACHE_BACKEND=db (staging / multi-worker setups).
if [ "${CACHE_BACKEND:-}" = "db" ]; then
    python manage.py createcachetable
fi

# Bind to Railway's PORT or default 8000. Worker count and request timeout
# tuned for the Hobby tier; both env-overridable.
PORT="${PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-60}"

exec gunicorn alumni.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WEB_CONCURRENCY}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --access-logfile - \
    --error-logfile - \
    --log-level info
