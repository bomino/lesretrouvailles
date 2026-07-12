#!/usr/bin/env bash
set -euo pipefail

# Apply migrations on every boot. Idempotent and fast.
python manage.py migrate --noinput

# Database-backed cache table. Idempotent — safe to run on every boot.
# staging/prod settings fall back to DatabaseCache whenever REDIS_URL is
# unset (a per-process LocMemCache would give each gunicorn worker its own
# rate-limit counters), so the table must exist in that case too — not only
# when CACHE_BACKEND=db was set explicitly.
if [ -z "${REDIS_URL:-}" ]; then
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
