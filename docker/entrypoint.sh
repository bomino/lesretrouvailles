#!/usr/bin/env bash
set -euo pipefail

# Apply migrations on every boot. Idempotent and fast.
python manage.py migrate --noinput

# Bind to Railway's PORT or default 8000. Worker count tuned for Hobby tier.
PORT="${PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"

exec gunicorn alumni.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WEB_CONCURRENCY}" \
    --access-logfile - \
    --error-logfile - \
    --log-level info
