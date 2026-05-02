# P2.5 Staging Deploy: Docker + Railway + Cloudflare Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a private staging environment for Les Retrouvailles at `https://staging.villageretrouvailles.com` — Dockerized Django app deployed to Railway, gated behind HTTP basic-auth (P1's `BasicAuthMiddleware`), with Postgres add-on, Cloudinary signed uploads against real credentials, and Cloudflare DNS pointing the subdomain at Railway. Locally, `docker compose up` brings up the same image plus its database, so dev and staging share an exact build.

**Architecture:**
- **Multi-stage Dockerfile** — stage 1 (`node:20-alpine`) installs npm deps and runs `tailwindcss --minify`; stage 2 (`python:3.12-slim`) installs Python deps, copies the compiled CSS from stage 1, runs `collectstatic` and `compilemessages` at image build time, and exposes a `gunicorn` entrypoint.
- **Single image, two consumers** — local dev (`docker compose up app`) and Railway (auto-detects the Dockerfile and builds it). Same image runs in both places; the only difference is env vars.
- **Postgres** — Railway-managed Postgres add-on injects `DATABASE_URL` automatically. Local dev keeps its existing `db` service in `docker-compose.yml`.
- **Static files** — WhiteNoise (already in `INSTALLED_APPS`/`MIDDLEWARE` from P1) serves the hashed manifest from `staticfiles/` collected at build time.
- **Auth gating** — `BasicAuthMiddleware` (P1 Task 14) wraps the staging response with HTTP basic-auth so the public can't browse the staging site before launch. Already wired in `alumni.settings.staging` via `MIDDLEWARE = ["core.middleware.BasicAuthMiddleware"] + MIDDLEWARE`.
- **DNS** — Cloudflare hosts `villageretrouvailles.com`. A CNAME `staging` → `<railway-app>.up.railway.app` (DNS-only / grey-cloud) routes requests to Railway, which terminates TLS via its built-in Let's Encrypt cert. Cloudflare proxy stays off for staging (simpler; we add it for prod later).
- **Auto-deploy** — Railway watches the GitHub `main` branch (or a `staging` branch later) and rebuilds the image on every push. CI (P1 Task 11) keeps `main` green so deploys never ship red code.

**Tech Stack:** Docker (multi-stage build) · Railway (Dockerfile build, Postgres add-on, custom domain) · Cloudflare (DNS) · Gunicorn (app server) · WhiteNoise (static files) · gettext (compilemessages in image) · Existing project stack (Django 5, Postgres 16, HTMX, Tailwind, Allauth, Cloudinary).

---

## File Structure

**New files:**
- `Dockerfile` — multi-stage build (node → python)
- `.dockerignore` — excludes node_modules, .venv, .git, .pytest_cache, .ruff_cache, locale/.mo source-control noise, etc.
- `docker/entrypoint.sh` — runs `migrate` then execs `gunicorn`
- `docs/runbooks/staging-deploy.md` — concise post-deploy runbook (paste of Tasks 6-11 commands for future operators)

**Modified files:**
- `docker-compose.yml` — add an `app` service that builds from `Dockerfile`, depends on `db`, mounts source for hot reload (dev convenience), exposes port 8000
- `alumni/settings/staging.py` — add `STATIC_ROOT` env-driven, ensure `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` come from env
- `.env.example` — document new staging-only vars (`DJANGO_SETTINGS_MODULE`, `PORT`, `WEB_CONCURRENCY`)
- `Makefile` — add `docker-build` and `docker-run` targets
- `docs/superpowers/STATUS.md` — add a P2.5 row marking staging deploy

---

## Task 1: Multi-stage Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Write the failing build**

A failing build looks like: `docker build -t retrouvailles:test .` returns a non-zero exit. Verify by running it before authoring `Dockerfile` (no file = no image).

```bash
docker build -t retrouvailles:test . 2>&1 | tail -3
```

Expected: `unable to prepare context: ... Dockerfile: no such file or directory`

- [ ] **Step 2: Author `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

# ---- Stage 1: build CSS with Tailwind ----
FROM node:20-alpine AS css-builder

WORKDIR /build

# Copy only files needed for the CSS build
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

# System deps: gettext for compilemessages, libpq for psycopg, build-essential for any C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        gettext \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer-cache friendliness
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install -e .

# Copy source code
COPY alumni/ ./alumni/
COPY core/ ./core/
COPY members/ ./members/
COPY templates/ ./templates/
COPY locale/ ./locale/
COPY manage.py ./

# Copy compiled CSS from stage 1
COPY --from=css-builder /build/static/ ./static/

# Build-time steps that bake the image
RUN python manage.py compilemessages -l fr
RUN SECRET_KEY=build-time-only-not-used DJANGO_SETTINGS_MODULE=alumni.settings.staging \
    DATABASE_URL=postgres://x:x@localhost:5432/x \
    ALLOWED_HOSTS=localhost \
    BASIC_AUTH_REQUIRED=false \
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
```

- [ ] **Step 3: Author `docker/entrypoint.sh`**

```bash
mkdir -p docker
```

`docker/entrypoint.sh`:

```bash
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
```

- [ ] **Step 4: Build the image and verify it succeeds**

Run: `docker build -t retrouvailles:test .`
Expected: build succeeds; final image tagged `retrouvailles:test`. Print `docker images retrouvailles:test` to confirm.

If the build fails on `collectstatic`, the `staging.py` `STATIC_ROOT` config is the likely cause — Task 4 fixes that.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker/entrypoint.sh
git commit -m "feat(deploy): add multi-stage Dockerfile and gunicorn entrypoint"
```

---

## Task 2: `.dockerignore`

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Author `.dockerignore`**

```
# Version control
.git
.gitignore
.github

# Python
__pycache__
*.py[cod]
*$py.class
*.egg-info/
.pytest_cache
.ruff_cache
.venv
venv
env
.coverage
htmlcov

# Node
node_modules
npm-debug.log
yarn-debug.log
yarn-error.log

# Editor / OS
.vscode
.idea
.DS_Store
Thumbs.db

# Project-specific
.env
.env.*
!.env.example
docs/
*.md
!DESIGN.md

# Compiled assets we rebuild in image
staticfiles/
static/css/output.css

# Tests / dev-only
core/tests/
members/tests/
*/migrations/__pycache__

# Pre-commit
.pre-commit-config.yaml
```

> Note: `members/migrations/` itself is **not** ignored — migrations must be in the image. Only their `__pycache__` directories are excluded.

- [ ] **Step 2: Re-build and confirm context is small**

```bash
docker build -t retrouvailles:test . 2>&1 | grep -E "transferring context|sending build context"
```

Expected: build context size dropped (was ~hundreds of MB with node_modules + .venv; should now be <50 MB).

- [ ] **Step 3: Commit**

```bash
git add .dockerignore
git commit -m "chore(deploy): add .dockerignore to shrink build context"
```

---

## Task 3: `docker-compose.yml` app service for local parity

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Makefile`

- [ ] **Step 1: Update `docker-compose.yml`**

Replace the entire file with:

```yaml
# DEVELOPMENT ONLY — do not deploy this compose file.
# Plaintext credentials below are for local convenience.
# Staging and production use Railway with separate, env-injected credentials.

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: alumni
      POSTGRES_USER: alumni
      POSTGRES_PASSWORD: alumni
    ports:
      - "5432:5432"
    volumes:
      - alumni_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U alumni -d alumni"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      db:
        condition: service_healthy
    environment:
      DJANGO_SETTINGS_MODULE: alumni.settings.staging
      SECRET_KEY: dev-compose-secret-not-for-production-aaaaaaaaaaaaaaa
      DATABASE_URL: postgres://alumni:alumni@db:5432/alumni
      ALLOWED_HOSTS: localhost,127.0.0.1,app
      CSRF_TRUSTED_ORIGINS: http://localhost:8000
      SITE_URL: http://localhost:8000
      BASIC_AUTH_REQUIRED: "true"
      BASIC_AUTH_USERNAME: admin
      BASIC_AUTH_PASSWORD: compose-test-pw
      CLOUDINARY_CLIENT_PATH: alumni.cloudinary.FakeCloudinary
      CLOUDINARY_CLOUD_NAME: fake-cloud
      PORT: "8000"
      WEB_CONCURRENCY: "1"
    ports:
      - "8000:8000"

volumes:
  alumni_pgdata:
```

The compose-mode app uses `staging.py` settings (mirrors prod) so `docker compose up` is a true integration smoke test of the production-shaped image. To run dev-mode (Django runserver, debug enabled), keep using `make dev` directly on the host.

- [ ] **Step 2: Add `docker-build` and `docker-run` targets to `Makefile`**

Append:

```make
docker-build:
	docker build -t retrouvailles:local .

docker-run: docker-build
	docker compose up -d
	@echo "Staging-shaped app at http://localhost:8000 (basic-auth: admin / compose-test-pw)"

docker-down:
	docker compose down
```

Update `.PHONY`:
```make
.PHONY: dev test migrate css css-watch lint format check db-up db-down seed docker-build docker-run docker-down
```

- [ ] **Step 3: Run the full local stack**

```bash
make docker-run
```

Then in another shell:

```bash
curl -i -u admin:compose-test-pw http://localhost:8000/health
```

Expected: `200 OK` with body `{"status": "ok", "db": "ok"}`.

```bash
curl -i http://localhost:8000/health
```

Expected: `401 Unauthorized` (basic-auth gate working).

- [ ] **Step 4: Tear down**

```bash
make docker-down
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml Makefile
git commit -m "feat(deploy): add app service to docker-compose for local staging parity"
```

---

## Task 4: Settings tweaks for containerized staging

**Files:**
- Modify: `alumni/settings/staging.py`
- Modify: `alumni/settings/base.py`
- Modify: `.env.example`

- [ ] **Step 1: Verify `STATIC_ROOT` works at build time**

The Dockerfile already sets `STATIC_ROOT` indirectly via the existing `base.py: STATIC_ROOT = BASE_DIR / "staticfiles"`. Confirm `manage.py collectstatic` succeeds at build time inside the container (Task 1 Step 4 already does this — re-verify after settings tweaks).

- [ ] **Step 2: Update `alumni/settings/staging.py`**

Replace the file with:

```python
"""Staging environment — basic-auth gated, mirrors prod otherwise."""

import environ

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

env = environ.Env()

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Required by Django 4+ for cross-origin POST (allauth login over HTTPS)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Allow overriding ALLOWED_HOSTS at deploy time (Railway-injected domain + custom domain)
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["staging.villageretrouvailles.com", ".up.railway.app", "localhost", "127.0.0.1"],
)

BASIC_AUTH_REQUIRED = env.bool("BASIC_AUTH_REQUIRED", default=True)
BASIC_AUTH_USERNAME = env("BASIC_AUTH_USERNAME", default="")
BASIC_AUTH_PASSWORD = env("BASIC_AUTH_PASSWORD", default="")

MIDDLEWARE = ["core.middleware.BasicAuthMiddleware"] + MIDDLEWARE
```

The change: `ALLOWED_HOSTS` is now env-overridable with a sensible default that includes the staging subdomain and Railway's wildcard. `SECURE_SSL_REDIRECT` is env-overridable too — useful for local docker-compose where there's no TLS terminator.

In docker-compose, set `SECURE_SSL_REDIRECT=false` (already done implicitly because `false` becomes the env value when `BASIC_AUTH_REQUIRED=true` doesn't redirect HTTP). Update compose:

In `docker-compose.yml` `app` service `environment` block, add:

```yaml
SECURE_SSL_REDIRECT: "false"
```

- [ ] **Step 3: Document the new env vars in `.env.example`**

Replace the basic-auth/staging section with:

```bash
# Staging deployment — Railway + Cloudflare
# These vars activate the staging settings module via DJANGO_SETTINGS_MODULE=alumni.settings.staging.
# DJANGO_SETTINGS_MODULE=alumni.settings.staging
# ALLOWED_HOSTS=staging.villageretrouvailles.com,.up.railway.app
# CSRF_TRUSTED_ORIGINS=https://staging.villageretrouvailles.com
# SECURE_SSL_REDIRECT=true
# BASIC_AUTH_REQUIRED=true
# BASIC_AUTH_USERNAME=admin
# BASIC_AUTH_PASSWORD=change-me
# PORT=8000
# WEB_CONCURRENCY=2
```

- [ ] **Step 4: Re-run the docker-compose stack**

```bash
make docker-down
make docker-run
curl -i -u admin:compose-test-pw http://localhost:8000/health
curl -i -u admin:compose-test-pw http://localhost:8000/
curl -i -u admin:compose-test-pw -L http://localhost:8000/accounts/login/
```

Expected: 200, 200, 200 (login form HTML in the third).

- [ ] **Step 5: Commit**

```bash
git add alumni/settings/staging.py docker-compose.yml .env.example
git commit -m "feat(deploy): make staging settings env-driven for Railway compatibility"
```

---

## Task 5: Push to GitHub

**Files:** none (git operation)

- [ ] **Step 1: Push the merged main from earlier P2 work**

The user merged `feat/membership` into local `main` at commit `9c1e034` but did not push. Push that first:

```bash
git checkout main
git push origin main
git push origin v0.1.0-foundation 2>/dev/null || true
git push origin v0.2.0-membership
```

- [ ] **Step 2: Push the deploy branch**

```bash
git checkout chore/staging-deploy
git push -u origin chore/staging-deploy
```

- [ ] **Step 3: (Optional) Open a PR for visibility**

```bash
gh pr create --title "chore(deploy): docker + railway staging" --body "$(cat <<'EOF'
## Summary
- Multi-stage Dockerfile (node CSS build → Python runtime)
- docker-compose `app` service for local staging parity
- Settings tweaks for env-driven Railway deployment
- First Railway provisioning + Cloudflare DNS via the runbook

## Test Plan
- [ ] make docker-run + smoke test on http://localhost:8000
- [ ] Railway build succeeds from main
- [ ] staging.villageretrouvailles.com returns 401 (basic-auth) without creds, 200 with creds
- [ ] /health returns ok-ok JSON behind auth
EOF
)"
```

User does not need to merge the PR before continuing — Railway will build from `main` (after we point it at `main` post-merge) or directly from `chore/staging-deploy` for the first deploy.

---

## Task 6: Provision Railway project and Postgres

**Files:** none (Railway dashboard actions; document in `docs/runbooks/staging-deploy.md`)

- [ ] **Step 1: Create the Railway project**

Browser actions:
1. Visit https://railway.app/new and sign in with GitHub
2. Click **Deploy from GitHub repo** → select `bomino/lesretrouvailles` → branch `main` (or `chore/staging-deploy` for the first deploy)
3. Railway auto-detects the `Dockerfile` and starts the first build

- [ ] **Step 2: Add a Postgres add-on**

In the project view:
1. Click **+ New** → **Database** → **Add PostgreSQL**
2. Wait for the database to provision (~30 s)
3. Confirm the `DATABASE_URL` variable is automatically attached to the app service via "Reference variables" — open the app service → Variables tab → confirm `DATABASE_URL=${{ Postgres.DATABASE_URL }}` is set (Railway adds this automatically when you add Postgres in the same project)

- [ ] **Step 3: Verify Postgres extensions can be enabled**

The app's migration `0004_unaccent_and_indexes.py` calls `UnaccentExtension()`, which runs `CREATE EXTENSION IF NOT EXISTS unaccent`. Railway's managed Postgres allows this for the connection user. Migration `0005_check_constraints.py` creates a wrapper function `unaccent_immutable()` — also user-allowed.

If migrations fail with `permission denied to create extension`, contact Railway support to grant SUPERUSER on the database, OR alter the migration to skip the extension (and rely on `CREATE EXTENSION` having been run manually). Document the outcome in the runbook.

- [ ] **Step 4: Document the Railway project ID + database URL pattern**

Capture the Railway project ID and (privately) the database URL pattern in your password manager. Do NOT commit them. Add to `docs/runbooks/staging-deploy.md` only the variable names and reference syntax.

---

## Task 7: Set Railway environment variables

**Files:** none (Railway dashboard action; document in `docs/runbooks/staging-deploy.md`)

In the Railway app service → **Variables** tab, set the following:

| Variable | Value |
|----------|-------|
| `DJANGO_SETTINGS_MODULE` | `alumni.settings.staging` |
| `SECRET_KEY` | Generated 50-char token (see below) |
| `ALLOWED_HOSTS` | `staging.villageretrouvailles.com,.up.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://staging.villageretrouvailles.com,https://*.up.railway.app` |
| `SITE_URL` | `https://staging.villageretrouvailles.com` |
| `SECURE_SSL_REDIRECT` | `true` |
| `BASIC_AUTH_REQUIRED` | `true` |
| `BASIC_AUTH_USERNAME` | `admin` |
| `BASIC_AUTH_PASSWORD` | Generated 24+ char password (see below) |
| `CLOUDINARY_CLIENT_PATH` | `alumni.cloudinary.RealCloudinary` |
| `CLOUDINARY_CLOUD_NAME` | From Cloudinary dashboard |
| `CLOUDINARY_API_KEY` | From Cloudinary dashboard |
| `CLOUDINARY_API_SECRET` | From Cloudinary dashboard |
| `CLOUDINARY_URL` | From Cloudinary dashboard (`cloudinary://<key>:<secret>@<cloud>`) |
| `WEB_CONCURRENCY` | `2` |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` (auto-set by Task 6) |
| `PORT` | (auto-set by Railway; do not override) |

- [ ] **Step 1: Generate `SECRET_KEY`**

Run on local machine:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Paste into Railway's `SECRET_KEY` variable. Do NOT commit.

- [ ] **Step 2: Generate `BASIC_AUTH_PASSWORD`**

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

Save in password manager. Share with the small group of staging testers via a secure channel.

- [ ] **Step 3: Sign up for Cloudinary (if not already)**

1. Visit https://cloudinary.com/users/register/free
2. After verification, the dashboard shows `Cloud name`, `API Key`, `API Secret`, and a `CLOUDINARY_URL` (in format `cloudinary://<key>:<secret>@<cloud>`)
3. Paste each into the corresponding Railway variable
4. Verify the free tier covers your expected usage (25 GB storage / 25 GB bandwidth / 25k transformations per month — comfortably above MVP scale)

- [ ] **Step 4: Trigger a redeploy**

After all variables are set, click **Deploy** in Railway. Watch the build logs:

```
[builder] Step X/Y : RUN python manage.py compilemessages -l fr
[builder] Step X/Y : RUN python manage.py collectstatic --noinput
[runner] migrate ... OK
[runner] gunicorn ... Listening at http://0.0.0.0:8080
```

If `migrate` fails with `permission denied to create extension unaccent`, see Task 6 Step 3.

---

## Task 8: Cloudflare DNS — point `staging` at Railway

**Files:** none (Cloudflare dashboard action)

- [ ] **Step 1: Get Railway's app domain**

In Railway → app service → **Settings** → **Domains**:
1. Click **Generate Domain** if there isn't one yet (this gives you `<project-name>.up.railway.app`)
2. Click **Custom Domain** → enter `staging.villageretrouvailles.com`
3. Railway shows a target hostname like `<hash>.up.railway.app` for the CNAME

- [ ] **Step 2: Configure Cloudflare DNS**

In Cloudflare dashboard for `villageretrouvailles.com`:

1. Go to **DNS** → **Records**
2. Click **Add record**
3. Set:
   - Type: `CNAME`
   - Name: `staging`
   - Target: `<hash>.up.railway.app` (from Railway Step 1)
   - Proxy status: **DNS only** (grey cloud) — Cloudflare proxy interferes with Railway's TLS handshake; we'll add proxying for prod later with origin-cert config
   - TTL: `Auto`
4. Save

- [ ] **Step 3: Wait for DNS propagation**

```bash
dig +short staging.villageretrouvailles.com
```

Expected (after ~30 s): a `<hash>.up.railway.app` answer. Then a few seconds later, an IP address.

- [ ] **Step 4: Verify Railway minted the cert**

In Railway → app service → **Settings** → **Domains** → wait for the green check next to `staging.villageretrouvailles.com` (Let's Encrypt cert issuance, ~30-90 s after DNS resolves).

If the cert never issues, common causes: DNS not propagated yet (wait), or Cloudflare proxy is on (turn it off).

---

## Task 9: First production-shaped smoke test

**Files:** none (manual verification; document the runbook)

- [ ] **Step 1: Verify the basic-auth gate**

```bash
curl -i https://staging.villageretrouvailles.com/health
```

Expected: `401 Unauthorized` with `WWW-Authenticate: Basic realm="Staging"`.

- [ ] **Step 2: Verify health behind the gate**

```bash
curl -i -u admin:<BASIC_AUTH_PASSWORD> https://staging.villageretrouvailles.com/health
```

Expected: `200 OK` with body `{"status": "ok", "db": "ok"}`.

- [ ] **Step 3: Browser smoke test**

Open `https://staging.villageretrouvailles.com/` in a browser. Browser will prompt for HTTP auth. Enter `admin` / `<BASIC_AUTH_PASSWORD>`.

Verify in this order:
1. **Landing** — `/` renders, French copy, base font, `noindex` meta in source.
2. **Login** — `/accounts/login/` renders the French login form.
3. **Seed a member** — In a separate `railway run` shell:
   ```bash
   railway run --service <app> -- python manage.py loaddata seed_members
   railway run --service <app> -- python manage.py shell -c "from django.contrib.auth import get_user_model; u=get_user_model().objects.get(email='seed1@example.test'); u.set_password('TestPass123!'); u.save()"
   ```
   (Or open Railway's web shell and run those.)
4. **Log in** as `seed1@example.test` / `TestPass123!`. After login → `/charte/` charter page.
5. **Accept charter** → redirects to `/`. Visit `/annuaire/` → 6 seeded members.
6. **Profile detail** — click any card → privacy toggles honored.
7. **Profile edit** — `/profil/` → edit nickname → save → success message.
8. **Photo upload** — try uploading a profile photo. The `/api/cloudinary/sign/` endpoint should return real Cloudinary signature; browser uploads succeed; `members/<slug>/<id>` appears in your Cloudinary media library.
9. **Search** — `/annuaire/?q=aich` → matches Aïcha (accent-insensitive).

If any step fails, check Railway logs:

```bash
railway logs --service <app>
```

- [ ] **Step 4: Document the runbook**

Create `docs/runbooks/staging-deploy.md` capturing:
- The URL: `https://staging.villageretrouvailles.com`
- How to access (basic-auth + a seed account)
- How to view logs (`railway logs`)
- How to run shell commands (`railway run`)
- How to redeploy (`git push origin main` triggers it)
- What env vars exist (names only, no values)
- DNS chain (Cloudflare CNAME → Railway → Postgres add-on)
- Cost monitoring link (Railway usage page)

```bash
mkdir -p docs/runbooks
```

`docs/runbooks/staging-deploy.md`:

```markdown
# Staging deploy runbook

**URL:** https://staging.villageretrouvailles.com
**Gate:** HTTP basic-auth (admin / value in 1Password under "Retrouvailles Staging Basic Auth")
**Provider:** Railway · Postgres add-on · Cloudflare DNS (DNS-only)

## Access
- Browser: visit URL, enter basic-auth, log in with seed credentials
- Logs: `railway logs --service <app>` (requires Railway CLI logged in)
- Shell: `railway run --service <app> -- python manage.py <cmd>`
- Redeploy: `git push origin main` (Railway watches main)

## Env vars (names only)
DJANGO_SETTINGS_MODULE, SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS,
SITE_URL, SECURE_SSL_REDIRECT, BASIC_AUTH_REQUIRED, BASIC_AUTH_USERNAME,
BASIC_AUTH_PASSWORD, CLOUDINARY_CLIENT_PATH, CLOUDINARY_CLOUD_NAME,
CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_URL,
WEB_CONCURRENCY, DATABASE_URL (auto), PORT (auto)

## DNS
Cloudflare CNAME `staging.villageretrouvailles.com` → `<hash>.up.railway.app` (grey-cloud / DNS only)

## Cost watch
- Railway: ~$5/mo Hobby + Postgres usage. Budget alert: $10/mo.
- Cloudinary: free tier 25 GB. Budget alert when 80% usage.

## Removing
1. Pause Railway project (or delete).
2. Remove Cloudflare CNAME.
3. Cancel Cloudinary if not used elsewhere.
```

- [ ] **Step 5: Commit the runbook**

```bash
git add docs/runbooks/staging-deploy.md
git commit -m "docs: add staging deploy runbook"
```

---

## Task 10: Update STATUS.md with the deploy phase

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Insert P2.5 in the Phase Index table**

After the P2 row, add:

```markdown
| P2.5 | Staging deploy (Docker + Railway + Cloudflare) | Complete (2026-MM-DD, https://staging.villageretrouvailles.com) | [plan](plans/2026-05-02-staging-deploy.md) |
```

- [ ] **Step 2: Add a P2.5 section after the P2 section**

```markdown
## P2.5 — Staging deploy

**Shipped:** 2026-MM-DD (branch `chore/staging-deploy` merged into `main`)
**Plan:** [plans/2026-05-02-staging-deploy.md](plans/2026-05-02-staging-deploy.md)
**Live:** https://staging.villageretrouvailles.com (basic-auth gated)
**Stack:** Multi-stage Dockerfile · Railway (Hobby + Postgres add-on) · Cloudflare DNS (grey-cloud)
**Runbook:** [runbooks/staging-deploy.md](../runbooks/staging-deploy.md)

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Multi-stage Dockerfile + gunicorn entrypoint | [x] | `<sha>` |
| 2 | .dockerignore | [x] | `<sha>` |
| 3 | docker-compose `app` service for local parity | [x] | `<sha>` |
| 4 | Env-driven staging settings | [x] | `<sha>` |
| 5 | Pushed to GitHub | [x] | (push, no commit) |
| 6 | Railway project + Postgres add-on | [x] | (Railway dashboard) |
| 7 | Railway env vars set | [x] | (Railway dashboard) |
| 8 | Cloudflare DNS CNAME staging → Railway | [x] | (Cloudflare dashboard) |
| 9 | First production-shaped smoke test | [x] | (manual) |
| 10 | STATUS update + runbook | [x] | `<sha>` |

---
```

Replace `<sha>` placeholders with the actual commit SHAs from each task.

- [ ] **Step 2: Commit and push**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs: mark P2.5 staging deploy complete in STATUS.md"
git push origin chore/staging-deploy
```

---

## Acceptance criteria

P2.5 ships when:

- `docker compose up app` brings up a fully working staging-shaped app at `http://localhost:8000` behind basic-auth.
- `https://staging.villageretrouvailles.com` returns `401` without basic-auth and `200` with it.
- Logged-in member at the staging URL can browse `/annuaire/`, `/membres/<slug>/`, `/profil/`, `/charte/` exactly as locally.
- A real Cloudinary photo upload via signed direct upload completes end-to-end.
- The runbook document captures access, redeploy, and env-var names.
- `STATUS.md` lists P2.5 as Complete with the live URL.

## Out of scope

- **Production deploy** to `villageretrouvailles.com` (no subdomain) — separate plan, after P3 (cooptation) at minimum, possibly after P4 (public surface) since the public landing changes.
- **Cloudflare proxy / WAF** — staging stays grey-cloud for simplicity. Prod will turn on orange-cloud with origin certs and rate-limit rules.
- **CI image push to GHCR** — possible future optimization (build once in CI, deploy the same image), but Railway's Nixpacks/Dockerfile build is fast enough for now.
- **Backups + restore drill** — P6 territory.
- **Resend email** — P3 will activate. Staging can stay on console-email-backend.
- **B2 backup of Cloudinary** — P6.
