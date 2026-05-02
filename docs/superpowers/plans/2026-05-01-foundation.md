# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the Django 5 project with Postgres, the HTMX + Tailwind + DaisyUI frontend stack driven by a `DESIGN.md` token file (Google Labs `@google/design.md` alpha standard), Allauth (email-only login, signup disabled at this layer), French i18n + accessibility baseline, pytest + ruff + pre-commit + GitHub Actions CI, and a `/health` endpoint — providing the working web shell that all subsequent feature plans depend on.

**Architecture:** Single Django 5 monolith with split settings (`base` / `dev` / `staging` / `prod`). Postgres 16 in Docker Compose for development. Tailwind 3 + DaisyUI 4 compiled to a single CSS bundle via the Tailwind CLI, with the theme tokens (colors, type, spacing) sourced from a `DESIGN.md` file authored against the **`@google/design.md`** alpha standard — exporting `tailwind.theme.json` that the Tailwind config consumes. HTMX 2.x served from the project's static files (not CDN — long-term reliability and offline-capable dev). French as the default and only V1 locale, with `gettext` machinery active so Hausa can be added in Phase 4 without refactor. Accessibility baseline enforced in the base template (16px root font, WCAG AA contrast tokens, no hover-only interactions, 44×44 minimum tactile targets); contrast ratios are checked in CI by `designmd lint`.

**Tech Stack:** Python 3.12 · Django 5.x · PostgreSQL 16 · django-allauth · Tailwind CSS 3.4 · DaisyUI 4 · `@google/design.md` (alpha) · HTMX 2.x · pytest-django · factory-boy · ruff (lint + format) · pre-commit · GitHub Actions.

**Reference spec:** `docs/superpowers/specs/2026-05-01-alumni-platform-design.md` (PRD v1.3).

---

## File Structure

Files created/modified by this plan, with one-line responsibility:

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python project metadata, runtime + dev dependencies, tool config (ruff, pytest) |
| `docker-compose.yml` | Postgres 16 service for local development |
| `.env.example` | Documented environment variables (no secrets) |
| `manage.py` | Django entry point |
| `alumni/__init__.py` | Project package marker |
| `alumni/settings/__init__.py` | Settings package marker |
| `alumni/settings/base.py` | Settings shared across all environments |
| `alumni/settings/dev.py` | Local development overrides |
| `alumni/settings/staging.py` | Staging environment overrides (basic-auth gate) |
| `alumni/settings/prod.py` | Production environment overrides |
| `alumni/urls.py` | Root URL config |
| `alumni/wsgi.py` | WSGI entry point (Django default) |
| `alumni/asgi.py` | ASGI entry point (Django default) |
| `core/__init__.py` | Core app package marker |
| `core/apps.py` | Django AppConfig for `core` |
| `core/views.py` | Health check + landing placeholder views |
| `core/urls.py` | Core app URL config |
| `core/tests/__init__.py` | Test package marker |
| `core/tests/test_health.py` | Health endpoint test |
| `core/tests/test_base_template.py` | Base template a11y/i18n smoke test |
| `templates/base.html` | Site-wide base template with a11y baseline |
| `templates/core/landing_placeholder.html` | Stub landing page (fleshed out in P4) |
| `templates/account/login.html` | Custom Allauth login template |
| `static/css/input.css` | Tailwind source CSS |
| `static/css/output.css` | Tailwind compiled CSS (gitignored) |
| `static/js/htmx.min.js` | HTMX bundled (vendored, not CDN) |
| `static/img/logo.png` | Brand emblem ("Les Retrouvailles") — visual anchor in header/footer |
| `DESIGN.md` | Visual identity (tokens + rationale) authored against `@google/design.md` spec — single source of truth for colors, type, spacing, components |
| `tailwind.theme.json` | Generated Tailwind theme exported from DESIGN.md (committed for reproducible builds) |
| `tailwind.config.js` | Tailwind + DaisyUI config; consumes `tailwind.theme.json` |
| `postcss.config.js` | PostCSS pipeline |
| `package.json` | Node tooling for Tailwind build + `@google/design.md` CLI |
| `locale/fr/LC_MESSAGES/django.po` | French translations file (placeholder) |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff lint + format, djlint, file hygiene) |
| `.github/workflows/test.yml` | CI: ruff + djlint + designmd lint + pytest on push/PR |
| `Makefile` | Common dev commands (`make dev`, `make test`, `make migrate`, `make css`) |

---

## Task 1: Repo skeleton and Python project metadata

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore` (extend with Python/Node)

- [ ] **Step 1: Extend `.gitignore` with Python, Node, and build artefacts**

Read the current `.gitignore` (already created in the bootstrap commit) and add the build/artefact entries that Foundation introduces.

```gitignore
# (keep existing content, then append:)

# Compiled CSS
static/css/output.css

# Locale compiled files
*.mo

# Coverage
.coverage
htmlcov/
.pytest_cache/

# Mypy
.mypy_cache/

# Ruff
.ruff_cache/
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "alumni"
version = "0.1.0"
description = "Plateforme Alumni CEG 1 Birni — Zinder"
requires-python = ">=3.12"
dependencies = [
    "django>=5.0,<5.1",
    "psycopg[binary]>=3.1",
    "django-allauth>=0.61",
    "django-environ>=0.11",
    "whitenoise>=6.6",
    "gunicorn>=21",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-django>=4.8",
    "factory-boy>=3.3",
    "ruff>=0.4",
    "pre-commit>=3.7",
    "djlint>=1.34",
]

[tool.ruff]
line-length = 100
target-version = "py312"
extend-exclude = ["migrations"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "DJ"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "alumni.settings.dev"
python_files = ["test_*.py"]
addopts = "-q"
```

- [ ] **Step 3: Create `.env.example`**

```dotenv
# Django
DJANGO_SETTINGS_MODULE=alumni.settings.dev
SECRET_KEY=change-me-locally-32-chars-minimum-aaaaaaaaa
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://alumni:alumni@localhost:5432/alumni

# Email (P3 will activate; placeholder for now)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@example.local

# Cloudinary (P2 will use; empty for now)
CLOUDINARY_URL=

# Site URL (used for absolute links in emails)
SITE_URL=http://localhost:8000

# Cross-origin POST allow-list (staging/prod only; comma-separated, scheme included)
# CSRF_TRUSTED_ORIGINS=https://staging.example.org,https://example.org

# Staging basic-auth (Task 14)
# BASIC_AUTH_REQUIRED=true
# BASIC_AUTH_USERNAME=admin
# BASIC_AUTH_PASSWORD=change-me
```

- [ ] **Step 4: Verify the file set is staged-ready**

Run: `ls -la pyproject.toml .env.example .gitignore`
Expected: all three files present.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example .gitignore
git commit -m "chore: add Python project metadata and env example"
```

---

## Task 2: Postgres via Docker Compose

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
# DEVELOPMENT ONLY — do not deploy this compose file.
# Plaintext credentials below are for local convenience.
# Staging and production use managed Postgres (Hetzner / Railway) with
# separate, env-injected credentials.

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

volumes:
  alumni_pgdata:
```

- [ ] **Step 2: Start the database and verify it accepts connections**

Run:
```bash
docker compose up -d db
docker compose ps
```
Expected: `db` service status `running` and health `healthy` after ~10s.

- [ ] **Step 3: Verify connectivity from host**

Run: `docker compose exec db psql -U alumni -d alumni -c "SELECT version();"`
Expected: PostgreSQL 16.x version line printed.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add postgres 16 docker compose service for dev"
```

---

## Task 3: Django project scaffold with split settings

**Files:**
- Create: `manage.py`, `alumni/__init__.py`, `alumni/settings/__init__.py`, `alumni/settings/base.py`, `alumni/settings/dev.py`, `alumni/settings/staging.py`, `alumni/settings/prod.py`, `alumni/urls.py`, `alumni/wsgi.py`, `alumni/asgi.py`

- [ ] **Step 1: Install dependencies into a fresh virtualenv**

Run:
```bash
python -m venv .venv
.venv/Scripts/activate   # Windows bash
pip install -e ".[dev]"
```
Expected: dependencies install without error.

- [ ] **Step 2: Generate the Django project skeleton**

Run: `django-admin startproject alumni .`
Expected: `manage.py`, `alumni/settings.py`, `alumni/urls.py`, `alumni/wsgi.py`, `alumni/asgi.py` created.

- [ ] **Step 3: Convert `settings.py` into a `settings/` package**

Delete `alumni/settings.py` and create the package:

```bash
rm alumni/settings.py
mkdir alumni/settings
touch alumni/settings/__init__.py
```

Create `alumni/settings/base.py`:

```python
"""Settings shared across all environments. Read everything from env."""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])
SITE_URL = env("SITE_URL", default="http://localhost:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.local")
```

Create `alumni/settings/dev.py`:

```python
"""Local development overrides."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
INTERNAL_IPS = ["127.0.0.1"]
```

Create `alumni/settings/staging.py`:

```python
"""Staging environment — basic-auth gated, mirrors prod otherwise."""
import environ

from .base import *  # noqa: F401,F403

env = environ.Env()

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Required by Django 4+ for cross-origin POST (allauth login over HTTPS)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
```

Create `alumni/settings/prod.py`:

```python
"""Production overrides — strict security, HSTS, no debug."""
from .staging import *  # noqa: F401,F403

DEBUG = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
```

- [ ] **Step 4: Update `manage.py` to point at the dev settings package**

Edit `manage.py` and change:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alumni.settings.dev")
```

- [ ] **Step 5: Update `alumni/wsgi.py` and `alumni/asgi.py` similarly**

Both files: change `"alumni.settings"` → `"alumni.settings.prod"`.

- [ ] **Step 6: Create `.env` from the example**

```bash
cp .env.example .env
```

Generate a real `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the output into `.env` replacing the placeholder.

- [ ] **Step 7: Run `manage.py check` and confirm no errors**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 8: Run initial migrations**

Run: `python manage.py migrate`
Expected: all built-in Django migrations applied (auth, sessions, sites, etc.).

- [ ] **Step 9: Commit**

```bash
git add manage.py alumni/
git commit -m "feat: scaffold django project with split settings"
```

---

## Task 4: pytest setup with first passing test

**Files:**
- Create: `core/__init__.py`, `core/apps.py`, `core/tests/__init__.py`, `core/tests/test_smoke.py` (pytest config lives in `pyproject.toml`, no separate `pytest.ini` or `conftest.py` needed at this stage)

- [ ] **Step 1: Write the failing smoke test**

Create `core/tests/test_smoke.py`:

```python
"""Smoke test: prove pytest + Django settings load correctly."""
from django.conf import settings


def test_settings_loaded():
    assert settings.SECRET_KEY != ""
    assert "core" in settings.INSTALLED_APPS
```

- [ ] **Step 2: Create the `core` app skeleton**

Create `core/__init__.py` (empty) and `core/apps.py`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
```

Create `core/tests/__init__.py` (empty).

- [ ] **Step 3: Run pytest and confirm the test passes**

Run: `pytest core/tests/test_smoke.py -v`
Expected: `1 passed`.

- [ ] **Step 4: Commit**

```bash
git add core/ pyproject.toml
git commit -m "test: add core app and pytest smoke test"
```

---

## Task 5: Health check endpoint with database probe

**Files:**
- Create: `core/views.py`, `core/urls.py`, `core/tests/test_health.py`
- Modify: `alumni/urls.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_health.py`:

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_returns_ok_when_db_up(client):
    response = client.get(reverse("health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `pytest core/tests/test_health.py -v`
Expected: FAIL with `NoReverseMatch: Reverse for 'health' not found`.

- [ ] **Step 3: Implement the view**

Create `core/views.py`:

```python
from django.db import connection
from django.http import JsonResponse


def health(_request):
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False
    payload = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "fail"}
    status_code = 200 if db_ok else 503
    return JsonResponse(payload, status=status_code)
```

Create `core/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
]
```

Modify `alumni/urls.py`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `pytest core/tests/test_health.py -v`
Expected: `1 passed`.

- [ ] **Step 5: Manually verify in the browser**

Run: `python manage.py runserver`
Open: `http://localhost:8000/health`
Expected: JSON `{"status": "ok", "db": "ok"}`.

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/urls.py core/tests/test_health.py alumni/urls.py
git commit -m "feat: add /health endpoint with database probe"
```

---

## Task 6: Tailwind + DaisyUI build pipeline

**Files:**
- Create: `package.json`, `tailwind.config.js`, `postcss.config.js`, `static/css/input.css`

- [ ] **Step 1: Initialize Node tooling**

Run:
```bash
npm init -y
npm install -D tailwindcss@^3.4 daisyui@^4 postcss autoprefixer
```

- [ ] **Step 2: Create `tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./core/**/*.{html,py}",
  ],
  theme: {
    extend: {
      fontSize: {
        // Accessibility baseline: bump base from 14px → 16px (spec §8.3)
        base: ["16px", { lineHeight: "1.6" }],
      },
      minHeight: {
        // Tactile target floor (spec §8.3)
        tap: "44px",
      },
      minWidth: {
        tap: "44px",
      },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light"],
    logs: false,
  },
};
```

- [ ] **Step 3: Create `postcss.config.js`**

```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 4: Create `static/css/input.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Project base — accessibility baseline */
html { font-size: 16px; }
body { font-family: ui-sans-serif, system-ui, sans-serif; }
button, .btn, a.btn { min-height: 44px; min-width: 44px; }
```

- [ ] **Step 5: Add the build scripts to `package.json`**

Edit `package.json` and ensure the `scripts` section contains:

```json
{
  "scripts": {
    "css:build": "tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify",
    "css:watch": "tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch"
  }
}
```

- [ ] **Step 6: Build the CSS and verify the output exists**

Run: `npm run css:build`
Expected: `static/css/output.css` is created and contains DaisyUI utility classes.

Verify:
```bash
grep -q "btn" static/css/output.css && echo "OK"
```
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add package.json package-lock.json tailwind.config.js postcss.config.js static/css/input.css
git commit -m "feat: add tailwind + daisyui build pipeline"
```

---

## Task 6.5: Author DESIGN.md and wire export to Tailwind theme

> **Why this task:** The platform's visual identity (Sahelien gravitas, accessibility for 55-65 year olds, distinct In Memoriam treatment) is too important to encode only in `tailwind.config.js`. We use **`@google/design.md`** — a Google Labs alpha standard for describing visual identity to coding agents — as the **single source of truth** for design tokens. Subsequent plans (P2 Membership, P4 Public surface, P5 Mémoire seed) all read from this file rather than reinventing colors and type each time. The `lint` command verifies WCAG AA contrast ratios in CI, satisfying spec §8.3 *as a CI check*, not as documentation.

**Files:**
- Create: `DESIGN.md`
- Create: `tailwind.theme.json` (generated, committed)
- Create: `core/tests/test_design_tokens.py`
- Modify: `package.json` (add `@google/design.md` devDep + scripts)
- Modify: `tailwind.config.js` (consume `tailwind.theme.json`)
- Modify: `.github/workflows/test.yml` (add `designmd lint` step)

- [ ] **Step 1: Install the `@google/design.md` CLI as a dev dependency**

Run: `npm install -D @google/design.md`

> *Windows note: invoke via the `designmd` alias (not `design.md`) when calling from `package.json` scripts. The `.md` suffix collides with Markdown file association on Windows.*

- [ ] **Step 2: Add `design:lint` and `design:export` scripts to `package.json`**

Edit `package.json`'s `"scripts"` block to read:

```json
{
  "scripts": {
    "design:lint": "designmd lint DESIGN.md",
    "design:export": "designmd export --format tailwind DESIGN.md > tailwind.theme.json",
    "css:build": "tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify",
    "css:watch": "tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch"
  }
}
```

- [ ] **Step 3: Create `DESIGN.md` at the project root**

```markdown
---
version: alpha
name: Alumni CEG 1 Birni
description: Visual identity for the Alumni CEG 1 Birni — Zinder platform. A digital memory home for the 1980-1985 promotion. Journalistic gravitas, Sahelien restraint.
colors:
  primary: "#1A1C1E"
  secondary: "#6C7278"
  tertiary: "#A04A2C"
  neutral: "#F5F1EA"
  on-primary: "#F5F1EA"
  on-tertiary: "#FFFFFF"
  surface: "#FFFFFF"
  surface-variant: "#EEEAE2"
  in-memoriam: "#5A4A3D"
  whatsapp-green: "#1F6B4F"
  on-whatsapp-green: "#FFFFFF"
  ceremonial-gold: "#C9A227"
  on-ceremonial-gold: "#1A1C1E"
typography:
  display:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: -0.01em
  h1:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: 600
    lineHeight: 1.2
  h2:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: 500
    lineHeight: 1.3
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.6
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0.02em
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1
    letterSpacing: 0.08em
rounded:
  sm: 4px
  md: 8px
  lg: 12px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 12px
    height: 44px
  button-primary-hover:
    backgroundColor: "#8A3F26"
    textColor: "{colors.on-tertiary}"
  button-secondary:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    height: 44px
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: 24px
  in-memoriam-frame:
    backgroundColor: "{colors.surface-variant}"
    textColor: "{colors.in-memoriam}"
    rounded: "{rounded.md}"
    padding: 32px
  whatsapp-link:
    backgroundColor: "{colors.whatsapp-green}"
    textColor: "{colors.on-whatsapp-green}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 12px
    height: 44px
  promo-badge:
    backgroundColor: "{colors.ceremonial-gold}"
    textColor: "{colors.on-ceremonial-gold}"
    typography: "{typography.label-caps}"
    rounded: "{rounded.full}"
    padding: 4px
    height: 28px
---

# Alumni CEG 1 Birni — Design System

## Overview

The visual identity for the Alumni CEG 1 Birni platform serves a single purpose: to feel like a permanent home for the memory of a generation that shared decisive years in Zinder, Niger, between 1980 and 1985. It is journalistic in posture — unhurried, legible, archival — and Sahelien in palette: warm limestone foundations and a single terra-cotta accent that nods to the earthen architecture of Zinder's old city without resorting to ornamental cliché.

The platform must feel respectful enough to host an In Memoriam, structured enough to function as a directory, and quiet enough to recede when the photographs and testimonies take over. Decoration is restrained. Whitespace is generous. The design should not call attention to itself; it should call attention to the people it remembers.

## Colors

The palette is built around high-contrast neutrals with one warm accent. There is no second accent; chromatic restraint is itself a design decision. Reading the alumni directory or an In Memoriam page should feel like turning the page of a quality print publication, not browsing a corporate web app.

- **Primary (#1A1C1E):** Deep ink for headlines, body copy, and structural elements. Conveys gravity and permanence.
- **Secondary (#6C7278):** Sophisticated slate for borders, captions, dates, profession labels, and metadata. Never used as primary text.
- **Tertiary (#A04A2C):** "Sahel Terre Cuite" — the single interaction color. Used exclusively for primary CTAs ("Je suis un ancien"), active states, and rare highlights. Its scarcity makes each appearance meaningful.
- **Neutral (#F5F1EA):** Warm limestone — the page foundation. Softer than pure white, with a faint earthy undertone.
- **In Memoriam (#5A4A3D):** Earth brown reserved exclusively for In Memoriam frames and copy. Never appears outside that context.

## Typography

The type system pairs **Playfair Display** for editorial weight with **Inter** for utilitarian clarity. The juxtaposition mirrors the platform's dual nature: a place of memory (Playfair) and a place of function (Inter).

- **Display & Headlines:** Playfair Display 600. Used sparingly for major page titles, member names on profile pages, and In Memoriam dedications. Negative letter-spacing tightens display sizes.
- **Body:** Inter 400 at 16px is the floor. Per spec §8.3, the platform's audience is 55-65 years old and 16px is a non-negotiable accessibility baseline.
- **Labels:** Inter 500/600 with positive letter-spacing for metadata, button text, and tags.

Avoid Playfair below 18px — its serifs collapse and undermine readability for older users.

## Layout

A 12-column grid on desktop with 24px gutters; on mobile, content is full-width with 16px page padding. The maximum readable line length for body copy is 65ch — beyond that, prose becomes uncomfortable for the cohort. Card-based components stack vertically on mobile, never carousel-paged. Vertical rhythm follows the spacing scale (8/16/24/32/48/64).

## Components

- **button-primary:** The single CTA color (Sahel Terre Cuite) on neutral background. 44×44 minimum tactile target (spec §8.3). Used at most once per visible viewport.
- **card:** Surface white with 24px padding, 8px radius. Houses member profiles, testimonials, photo entries.
- **in-memoriam-frame:** Bordered surface variant (limestone shade darker than page background), earth-brown copy. Visually distinct from any other component on the site — designed to feel set apart, like a memorial plaque.
- **whatsapp-link:** Pill-shaped button in `whatsapp-green` with white copy. Used **only** for WhatsApp-related affordances (header CTA "Rejoindre le groupe WhatsApp", share-to-WA links, in-message WA-icon links). Never used as a generic UI button.
- **promo-badge:** Small pill with **`ceremonial-gold` background and deep-ink text** (gold-medal feel, WCAG AA compliant). Used for the "Promo 1980-1985" stamp, anniversary milestone marks, and the founding-date footer chip ("Depuis le 1ᵉʳ Septembre 2020"). Decorative role only — never wraps interactive content.

## Logo

The platform's emblem — *Les Retrouvailles* — predates this website. It was created for the WhatsApp group founded on 1 September 2020 and is the community's existing brand mark. We do not redesign it; we **host** it.

The logo combines a green crest (referencing the WhatsApp group's origin), gold laurels and ribbons (promotion / class anniversary), the *CEG 1 BIRNI DE ZINDER* wordmark, and the graduation cap and open book (school identity).

### Where the logo appears

- **Header (every page):** Top-left, 48px tall on mobile, 56px tall on desktop. The site's primary visual anchor.
- **Footer:** Same logo at 32px tall, paired with the founding date chip (`promo-badge`).
- **Favicon:** 32×32px crop of the central crest (deferred to P5 / Soft launch).
- **OG / share images:** Full logo over a `neutral` limestone background.

### Color extracts

The site palette includes two colors **drawn from the logo** and used sparingly to keep the visual link to the WhatsApp origin without saturating the UI:

- `whatsapp-green` (#1F6B4F): a desaturated forest variant of the logo's bright WhatsApp green. **Reserved for WhatsApp-related affordances only** (the `whatsapp-link` component, share icons, "online in WA group" indicators).
- `ceremonial-gold` (#C9A227): a muted version of the laurel/ribbon gold. **Reserved for promotion-anniversary marks** (`promo-badge`, milestone year labels, decorative top borders on commemorative frames).

The terra-cotta accent (`tertiary`, "Sahel Terre Cuite") remains the **single primary call-to-action color** — distinct from both logo-derived colors. This separation is deliberate: WhatsApp green pulls toward "the group we already are"; Sahel terra-cotta pulls toward "the new home we are building." They cohabit without competing.

### Logo do's and don'ts

- **Don't recolor the logo.** No alpha, no monochrome variants, no themed versions. The logo always appears full-color on a neutral or surface background.
- **Don't crop or alter the *Les Retrouvailles* wordmark** in the logo.
- **Don't use `whatsapp-green` as a generic UI primary** (page backgrounds, headers, CTAs unrelated to WhatsApp).
- **Don't use `ceremonial-gold` as text color** for body or labels — its low contrast against limestone fails WCAG AA.

## Do's and Don'ts

- **Do** keep the Sahel Terre Cuite accent for true calls-to-action; reusing it for decorative borders or info badges dilutes its meaning.
- **Don't** introduce a fourth accent color. The design budget is `tertiary` for primary CTAs, `whatsapp-green` for WhatsApp affordances, `ceremonial-gold` for anniversary marks. Any new highlight must come from one of these.
- **Don't** combine `whatsapp-green` and `tertiary` (terra-cotta) in the same component — both pull attention; they fight each other if placed side by side.
- **Do** use generous whitespace around photographs; they are the primary content.
- **Don't** compress vertical rhythm to fit "more above the fold." This audience reads carefully, not skims.
- **Do** keep the In Memoriam visual language reserved for In Memoriam contexts only.
- **Don't** use icon-only buttons (spec §8.3); always pair an icon with a text label.
```

- [ ] **Step 3b: Position the brand logo at `static/img/logo.png`**

The community already has an emblem (`logo_retrouvailles.png` — green crest, gold laurels, "Les Retrouvailles" wordmark). It is the visual anchor of every page (DESIGN.md `## Logo` section).

Run:
```bash
mkdir -p static/img
mv logo_retrouvailles.png static/img/logo.png
```

If you are starting from a fresh checkout where the file is already at `static/img/logo.png`, skip this step.

Verify:
```bash
test -s static/img/logo.png && echo "OK"
```
Expected: `OK`.

- [ ] **Step 4: Lint DESIGN.md and confirm zero errors**

Run: `npm run design:lint`
Expected: JSON output with `"summary": { "errors": 0, ... }`. Warnings are acceptable; errors fail the task.

If contrast warnings appear (e.g. `secondary` text on `surface` falling under WCAG AA 4.5:1), adjust the affected color in DESIGN.md and re-lint.

- [ ] **Step 5: Export DESIGN.md to a Tailwind theme JSON**

Run: `npm run design:export`
Expected: `tailwind.theme.json` is created with `colors`, `fontFamily`, `fontSize`, `borderRadius`, `spacing` keys derived from DESIGN.md tokens.

Inspect the file and confirm the alumni-specific colors are present:
```bash
grep -E '"primary"|"tertiary"|"in-memoriam"' tailwind.theme.json
```
Expected: all three keys appear.

- [ ] **Step 6: Modify `tailwind.config.js` to consume the exported theme**

Replace the contents of `tailwind.config.js`:

```javascript
const theme = require("./tailwind.theme.json");

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./core/**/*.{html,py}",
  ],
  theme: {
    extend: {
      // Tokens from DESIGN.md (single source of truth for visual identity)
      ...(theme.colors && { colors: theme.colors }),
      ...(theme.fontFamily && { fontFamily: theme.fontFamily }),
      ...(theme.fontSize && { fontSize: theme.fontSize }),
      ...(theme.borderRadius && { borderRadius: theme.borderRadius }),
      ...(theme.spacing && { spacing: theme.spacing }),
      // Project-specific extensions not expressed in DESIGN.md
      minHeight: { tap: "44px" },
      minWidth: { tap: "44px" },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light"],
    logs: false,
  },
};
```

- [ ] **Step 7: Rebuild the CSS and verify token application**

Run: `npm run css:build`
Expected: `static/css/output.css` is rebuilt without error.

Verify the key tokens compiled into utility classes:
```bash
grep -q "1A1C1E" static/css/output.css && echo "primary OK"
grep -q "A04A2C" static/css/output.css && echo "tertiary OK"
grep -q "5A4A3D" static/css/output.css && echo "in-memoriam OK"
grep -q "1F6B4F" static/css/output.css && echo "whatsapp-green OK"
grep -q "C9A227" static/css/output.css && echo "ceremonial-gold OK"
```
Expected: all five lines print `OK`. Lowercase variants (`a04a2c` etc.) are also valid since Tailwind may emit either case.

- [ ] **Step 8: Write the design-token smoke test**

Create `core/tests/test_design_tokens.py`:

```python
"""Anti-regression smoke test: DESIGN.md tokens must reach compiled CSS.

If any of these assertions fail, either DESIGN.md was edited and
`npm run design:export && npm run css:build` was not re-run, or the
tailwind.config.js stopped consuming the exported theme.
"""
from pathlib import Path

from django.conf import settings


def _read_compiled_css() -> str:
    css_path = Path(settings.STATICFILES_DIRS[0]) / "css" / "output.css"
    assert css_path.exists(), "Run `npm run css:build` first"
    return css_path.read_text(encoding="utf-8")


def test_primary_color_token_compiled():
    assert "1A1C1E" in _read_compiled_css() or "1a1c1e" in _read_compiled_css()


def test_sahel_terra_cotta_token_compiled():
    css = _read_compiled_css()
    assert "A04A2C" in css or "a04a2c" in css


def test_in_memoriam_brown_compiled():
    css = _read_compiled_css()
    assert "5A4A3D" in css or "5a4a3d" in css


def test_whatsapp_green_compiled():
    """The logo-derived WhatsApp green must reach the compiled CSS so
    the `whatsapp-link` component can be styled."""
    css = _read_compiled_css()
    assert "1F6B4F" in css or "1f6b4f" in css


def test_ceremonial_gold_compiled():
    """The logo-derived ceremonial gold must reach the compiled CSS so
    the `promo-badge` component can be styled."""
    css = _read_compiled_css()
    assert "C9A227" in css or "c9a227" in css
```

- [ ] **Step 9: Run the new tests and confirm they pass**

Run: `pytest core/tests/test_design_tokens.py -v`
Expected: `3 passed`.

- [ ] **Step 10: Add `designmd lint` to CI**

Modify `.github/workflows/test.yml` — insert one step **after** `npm ci` and **before** `npm run css:build`:

```yaml
      - run: npm ci
      - run: npm run design:lint
      - run: npm run design:export
      - run: npm run css:build
```

> *We re-export in CI to catch drift between committed `tailwind.theme.json` and `DESIGN.md`. If the freshly-generated theme differs from the committed one, the subsequent CSS build still succeeds (the new theme overwrites the committed file in the CI workspace), but a developer running `git status` after CI would see the diff. To make drift a hard CI failure, add a follow-up `git diff --exit-code tailwind.theme.json` step — left out of Foundation to avoid CI flakiness during early iteration.*

- [ ] **Step 11: Commit**

```bash
git add DESIGN.md static/img/logo.png tailwind.theme.json package.json package-lock.json tailwind.config.js core/tests/test_design_tokens.py .github/workflows/test.yml
git commit -m "feat: adopt DESIGN.md as single source of truth for visual identity"
```

---

## Task 7: Vendor HTMX and base template with a11y baseline

**Files:**
- Create: `static/js/htmx.min.js` (downloaded), `templates/base.html`, `templates/core/landing_placeholder.html`, `core/tests/test_base_template.py`
- Modify: `core/views.py` (add `landing_placeholder` view), `core/urls.py`

- [ ] **Step 1: Download HTMX 2.x and vendor it**

Run:
```bash
mkdir -p static/js
curl -fsSL https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js -o static/js/htmx.min.js
```

> *HTMX 2.x is the project default. Migration from 1.x has minor breaking changes (notably `hx-on` syntax, removal of some deprecated extensions); see <https://htmx.org/migration-guide-htmx-1/>. We pin a specific 2.x patch version so the bundled file is reproducible.*

Verify:
```bash
test -s static/js/htmx.min.js && echo "OK"
```
Expected: `OK`.

- [ ] **Step 2: Write the failing template test**

Create `core/tests/test_base_template.py`:

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_base_template_has_a11y_baseline(client):
    response = client.get(reverse("landing_placeholder"))
    html = response.content.decode("utf-8")

    assert response.status_code == 200
    assert '<html lang="fr">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1' in html
    assert "output.css" in html
    assert "htmx.min.js" in html


@pytest.mark.django_db
def test_base_template_renders_logo_and_whatsapp_link(client):
    """The header must render the brand logo and a WhatsApp affordance
    (DESIGN.md §Logo). The footer must render the founding-date badge."""
    response = client.get(reverse("landing_placeholder"))
    html = response.content.decode("utf-8")

    assert "img/logo.png" in html
    assert "Les Retrouvailles" in html
    assert "Rejoindre le groupe WhatsApp" in html
    assert "1F6B4F" in html  # whatsapp-green
    assert "C9A227" in html  # ceremonial-gold
    assert "1ᵉʳ Septembre 2020" in html or "1er Septembre 2020" in html


@pytest.mark.django_db
def test_base_template_blocks_robots_for_member_pages(client):
    """Default behavior: pages opt-in to indexing. Landing placeholder
    is NOT yet the public landing — it must be noindex by default."""
    response = client.get(reverse("landing_placeholder"))
    html = response.content.decode("utf-8")
    assert '<meta name="robots" content="noindex"' in html
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `pytest core/tests/test_base_template.py -v`
Expected: FAIL with `NoReverseMatch: Reverse for 'landing_placeholder' not found`.

- [ ] **Step 4: Create the base template**

Create `templates/base.html`:

```django
{% load static i18n %}
<!DOCTYPE html>
<html lang="{% get_current_language as LANGUAGE_CODE %}{{ LANGUAGE_CODE }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=yes">
  {% block robots %}<meta name="robots" content="noindex,nofollow">{% endblock %}
  <title>{% block title %}{% trans "Alumni CEG 1 Birni" %}{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/output.css' %}">
  <script defer src="{% static 'js/htmx.min.js' %}"></script>
</head>
<body class="bg-neutral text-primary">
  <a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 btn btn-primary">
    {% trans "Aller au contenu principal" %}
  </a>

  <header class="border-b border-secondary/20 bg-surface">
    <div class="container mx-auto flex items-center justify-between gap-md px-md py-sm">
      <a href="{% url 'landing_placeholder' %}" class="flex items-center gap-sm" aria-label="{% trans 'Les Retrouvailles — accueil' %}">
        <img src="{% static 'img/logo.png' %}" alt="{% trans 'Les Retrouvailles — CEG 1 Birni de Zinder' %}" class="h-12 md:h-14 w-auto" width="112" height="112">
        <span class="hidden md:inline-block text-lg font-medium">{% trans "Les Retrouvailles" %}</span>
      </a>
      {% block header_actions %}
        <a href="https://chat.whatsapp.com/" rel="noopener noreferrer" target="_blank"
           class="inline-flex items-center gap-xs rounded-full px-md py-xs min-h-tap text-sm font-medium"
           style="background-color: #1F6B4F; color: #FFFFFF;">
          <span aria-hidden="true">💬</span>
          {% trans "Rejoindre le groupe WhatsApp" %}
        </a>
      {% endblock %}
    </div>
  </header>

  <main id="main" class="container mx-auto p-md">
    {% block content %}{% endblock %}
  </main>

  <footer class="container mx-auto px-md py-lg mt-2xl border-t border-secondary/20 flex items-center gap-md text-sm text-secondary">
    <img src="{% static 'img/logo.png' %}" alt="" class="h-8 w-auto" width="64" height="64">
    <span class="rounded-full px-md py-xs text-xs font-semibold tracking-wider uppercase"
          style="background-color: #C9A227; color: #1A1C1E;">
      {% trans "Depuis le 1ᵉʳ Septembre 2020" %}
    </span>
  </footer>
</body>
</html>
```

> *Inline `style` attributes for `whatsapp-green` and `ceremonial-gold` are a deliberate Foundation-stage shortcut: the Tailwind theme exported from DESIGN.md doesn't auto-generate utility classes for arbitrary token names (it generates `bg-whatsapp-green` only if Tailwind's color plugin recognizes the key, which depends on the export shape). Once Task 6.5 step 7 is verified, switch these to `bg-whatsapp-green text-on-whatsapp-green` and `text-ceremonial-gold` utility classes if they resolve. The colors-as-inline-style fallback is documented but discouraged for ongoing work.*

Create `templates/core/landing_placeholder.html`:

```django
{% extends "base.html" %}
{% load i18n %}

{% block content %}
  <h1 class="text-3xl font-bold">{% trans "Plateforme Alumni — en construction" %}</h1>
  <p class="mt-4">{% trans "Le site est en cours de développement." %}</p>
{% endblock %}
```

- [ ] **Step 5: Add the placeholder view**

Modify `core/views.py` — add at the bottom:

```python
from django.shortcuts import render


def landing_placeholder(request):
    return render(request, "core/landing_placeholder.html")
```

Modify `core/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing_placeholder, name="landing_placeholder"),
    path("health", views.health, name="health"),
]
```

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `pytest core/tests/test_base_template.py -v`
Expected: `2 passed`.

- [ ] **Step 7: Manually verify in the browser**

Run: `python manage.py runserver`
Open: `http://localhost:8000/`
Expected: page renders with French heading, base font is 16px (use browser inspect), `noindex` meta visible in source.

- [ ] **Step 8: Commit**

```bash
git add static/js/htmx.min.js templates/ core/views.py core/urls.py core/tests/test_base_template.py
git commit -m "feat: add base template with a11y baseline and htmx"
```

---

## Task 8: i18n machinery active for French (Hausa-ready architecture)

**Files:**
- Create: `locale/fr/LC_MESSAGES/django.po` (after extraction), `core/tests/test_i18n.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_i18n.py`:

```python
from django.utils.translation import activate, gettext as _


def test_french_translation_active():
    activate("fr")
    # Strings tagged in templates should be translatable. We assert the
    # gettext machinery resolves a known string round-trip.
    assert _("Aller au contenu principal") == "Aller au contenu principal"


def test_locale_path_exists():
    from django.conf import settings
    from pathlib import Path

    locale_dir = Path(settings.LOCALE_PATHS[0]) / "fr" / "LC_MESSAGES"
    assert locale_dir.exists(), "Locale directory must exist for French"
```

- [ ] **Step 2: Run the test and confirm it fails on the locale path check**

Run: `pytest core/tests/test_i18n.py -v`
Expected: second test fails with `AssertionError: Locale directory must exist`.

- [ ] **Step 3: Create the locale directory and run `makemessages`**

Run:
```bash
mkdir -p locale/fr/LC_MESSAGES
python manage.py makemessages -l fr --ignore=.venv --ignore=node_modules
```

Expected: `locale/fr/LC_MESSAGES/django.po` created with `msgid` entries for the strings tagged in `base.html` and `landing_placeholder.html`.

- [ ] **Step 4: Compile the messages**

Run: `python manage.py compilemessages`
Expected: `django.mo` produced next to `django.po` (excluded from git via `.gitignore`).

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `pytest core/tests/test_i18n.py -v`
Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add locale/
git commit -m "feat: add french locale and i18n smoke tests"
```

---

## Task 9: Allauth integration (login only, signup disabled)

**Files:**
- Create: `templates/account/login.html`, `core/tests/test_auth.py`
- Modify: `alumni/settings/base.py`, `alumni/urls.py`

> **Note on signup:** Allauth's built-in signup is *disabled* at this layer because Phase 1 inscription goes through the cooptation flow (P3), not direct self-signup. Login-by-email-and-password remains active for already-validated members.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_auth.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_login_page_renders(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200
    assert b"Connexion" in response.content or b"login" in response.content.lower()


@pytest.mark.django_db
def test_signup_returns_closed_response(client):
    """Self-signup is disabled. Members enter via cooptation (P3).

    Allauth's SignupView returns the signup_closed template (200) when
    the adapter's is_open_for_signup() returns False — it does NOT 404.
    We assert there is no functional signup form in the response.
    """
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    assert b'name="password1"' not in response.content
    assert b'name="password2"' not in response.content


@pytest.mark.django_db
def test_existing_user_can_login(client):
    User.objects.create_user(email="moussa@example.com", username="moussa", password="testpass123")
    response = client.post(
        reverse("account_login"),
        {"login": "moussa@example.com", "password": "testpass123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.context["user"].is_authenticated
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest core/tests/test_auth.py -v`
Expected: FAIL with `NoReverseMatch: Reverse for 'account_login' not found`.

- [ ] **Step 3: Add Allauth to `INSTALLED_APPS` and middleware**

Modify `alumni/settings/base.py` — extend `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... existing ...
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "core",
]
```

Add to `MIDDLEWARE` after `AuthenticationMiddleware`:

```python
MIDDLEWARE = [
    # ... existing ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    # ... rest ...
]
```

Append Allauth config at the bottom of `base.py`:

```python
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
```

- [ ] **Step 4: Create the adapter that disables signup**

Create `core/allauth_adapter.py`:

```python
from allauth.account.adapter import DefaultAccountAdapter


class NoSignupAdapter(DefaultAccountAdapter):
    """Direct self-signup is disabled. Members enter via cooptation (P3)."""

    def is_open_for_signup(self, request):
        return False
```

- [ ] **Step 5: Wire Allauth URLs**

Modify `alumni/urls.py`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("core.urls")),
]
```

- [ ] **Step 6: Provide the custom login template**

Create `templates/account/login.html`:

```django
{% extends "base.html" %}
{% load i18n %}

{% block title %}{% trans "Connexion" %}{% endblock %}

{% block content %}
  <div class="max-w-md mx-auto card bg-base-200 p-6">
    <h1 class="text-2xl font-bold mb-4">{% trans "Connexion" %}</h1>
    <form method="post" action="{% url 'account_login' %}">
      {% csrf_token %}
      {{ form.as_p }}
      <button type="submit" class="btn btn-primary w-full mt-4">{% trans "Se connecter" %}</button>
    </form>
  </div>
{% endblock %}
```

- [ ] **Step 6b: Provide the signup-closed template**

Create `templates/account/signup_closed.html`:

```django
{% extends "base.html" %}
{% load i18n %}

{% block title %}{% trans "Inscription fermée" %}{% endblock %}

{% block content %}
  <div class="max-w-md mx-auto card bg-base-200 p-6">
    <h1 class="text-2xl font-bold mb-4">{% trans "Inscription fermée" %}</h1>
    <p>
      {% trans "Les inscriptions au site se font par cooptation. Si vous êtes un ancien du CEG 1 Birni (1980-1985), contactez un membre actuel pour qu'il devienne votre parrain." %}
    </p>
  </div>
{% endblock %}
```

- [ ] **Step 7: Run migrations for `allauth` and `sites`**

Run: `python manage.py migrate`
Expected: `allauth.account` migrations applied.

> **Note for staging/prod:** `django.contrib.sites` seeds a default `Site` row with `domain=example.com`. Allauth uses `SITE_ID=1` to fetch this row when generating absolute URLs in emails. Before any staging/prod email goes out (P3), update this row:
>
> ```python
> # python manage.py shell
> from django.contrib.sites.models import Site
> s = Site.objects.get(pk=1)
> s.domain = "alumni-ceg1-birni.org"  # or staging.alumni-ceg1-birni.org
> s.name = "Alumni CEG 1 Birni"
> s.save()
> ```
>
> Or do it via a data migration when the prod domain is finalized. Tracked as a P3/P7 prerequisite.

- [ ] **Step 8: Run the tests and confirm they pass**

Run: `pytest core/tests/test_auth.py -v`
Expected: `3 passed`.

- [ ] **Step 9: Commit**

```bash
git add core/allauth_adapter.py templates/account/ alumni/settings/base.py alumni/urls.py core/tests/test_auth.py
git commit -m "feat: integrate allauth with email login (signup disabled)"
```

---

## Task 10: Pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create the pre-commit config**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/Riverside-Healthcare/djLint
    rev: v1.34.1
    hooks:
      - id: djlint-django
        args: [--reformat]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=500]
```

> *Black is intentionally absent. `ruff format` is the project's sole formatter — running both creates conflicting fixes (parens, trailing commas). The Ruff team aims for Black-compatible output, so the migration is essentially free.*

- [ ] **Step 2: Install hooks and run on all files**

Run:
```bash
pre-commit install
pre-commit run --all-files
```

Expected: hooks run; some may fix files in-place. Re-run until clean.

- [ ] **Step 3: Commit any auto-fixes plus the config**

```bash
git add .pre-commit-config.yaml
git add -u  # stage any auto-fixes
git commit -m "chore: add pre-commit hooks (ruff, djlint)"
```

---

## Task 11: GitHub Actions CI

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Create the CI workflow**

```yaml
name: tests
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: alumni
          POSTGRES_USER: alumni
          POSTGRES_PASSWORD: alumni
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U alumni" --health-interval 5s
          --health-timeout 3s --health-retries 5
    env:
      DATABASE_URL: postgres://alumni:alumni@localhost:5432/alumni
      SECRET_KEY: ci-secret-key-not-for-production-32chars
      DEBUG: "true"
      ALLOWED_HOSTS: localhost
      DJANGO_SETTINGS_MODULE: alumni.settings.dev
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
      - run: pip install -e ".[dev]"
      - run: npm ci
      - run: npm run css:build
      - run: ruff check .
      - run: ruff format --check .
      - run: djlint templates/ --check
      - run: python manage.py compilemessages
      - run: pytest -v
```

- [ ] **Step 2: Verify the workflow file is valid YAML locally**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: add github actions workflow for tests + lint"
```

- [ ] **Step 4: Push to a remote and confirm CI is green**

> *Deferred: requires the user to create a GitHub repo and push. Re-visit once a remote exists.*

---

## Task 12: Makefile for common dev commands

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create the Makefile**

```makefile
.PHONY: dev test migrate css css-watch lint format check db-up db-down

dev:
	python manage.py runserver

test:
	pytest -v

migrate:
	python manage.py migrate

css:
	npm run css:build

css-watch:
	npm run css:watch

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

check:
	python manage.py check
	python manage.py makemigrations --dry-run --check

db-up:
	docker compose up -d db

db-down:
	docker compose down
```

- [ ] **Step 2: Smoke-test a few targets**

Run:
```bash
make check
make lint
make test
```
Expected: all three exit cleanly (no errors).

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add makefile for common dev commands"
```

---

## Task 13: Wire compiled CSS into the Django static pipeline

**Files:**
- Modify: `alumni/settings/base.py` (already present, just verify), `Makefile`
- Create: `core/tests/test_static_assets.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_static_assets.py`:

```python
from pathlib import Path

from django.conf import settings


def test_compiled_css_is_findable():
    """Tailwind output.css must be present in STATICFILES_DIRS for whitenoise."""
    css_path = Path(settings.STATICFILES_DIRS[0]) / "css" / "output.css"
    assert css_path.exists(), (
        "Compiled CSS missing. Run `npm run css:build` before tests, "
        "or add it to the test setup."
    )


def test_htmx_js_is_findable():
    js_path = Path(settings.STATICFILES_DIRS[0]) / "js" / "htmx.min.js"
    assert js_path.exists()
```

- [ ] **Step 2: Run the tests and confirm they pass (CSS already built in Task 6)**

Run: `pytest core/tests/test_static_assets.py -v`
Expected: `2 passed`. If CSS test fails, run `npm run css:build` and re-run.

- [ ] **Step 3: Add a `pretest` hook to the Makefile so CSS builds before tests**

Modify `Makefile` — replace the `test` target:

```makefile
test: css
	pytest -v
```

- [ ] **Step 4: Commit**

```bash
git add core/tests/test_static_assets.py Makefile
git commit -m "test: assert compiled css and htmx are present in static dirs"
```

---

## Task 14: Staging environment hardening

**Files:**
- Modify: `alumni/settings/staging.py`
- Create: `core/middleware.py`, `core/tests/test_basic_auth.py`

> **Goal of staging:** Mirror prod but gate behind HTTP basic-auth so only the 2-3 Super Admins can preview before WhatsApp announcement (spec §10).

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_basic_auth.py`:

```python
import pytest
from django.test import override_settings
from django.urls import reverse


@override_settings(
    MIDDLEWARE=[
        "core.middleware.BasicAuthMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ],
    BASIC_AUTH_REQUIRED=True,
    BASIC_AUTH_USERNAME="admin",
    BASIC_AUTH_PASSWORD="staging-pass",
)
@pytest.mark.django_db
def test_basic_auth_required_when_enabled(client):
    response = client.get(reverse("health"))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic")


@override_settings(
    MIDDLEWARE=[
        "core.middleware.BasicAuthMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ],
    BASIC_AUTH_REQUIRED=True,
    BASIC_AUTH_USERNAME="admin",
    BASIC_AUTH_PASSWORD="staging-pass",
)
@pytest.mark.django_db
def test_basic_auth_passes_with_correct_credentials(client):
    import base64

    creds = base64.b64encode(b"admin:staging-pass").decode()
    response = client.get(
        reverse("health"),
        HTTP_AUTHORIZATION=f"Basic {creds}",
    )
    assert response.status_code == 200
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest core/tests/test_basic_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.middleware'`.

- [ ] **Step 3: Implement the middleware**

Create `core/middleware.py`:

```python
import base64

from django.conf import settings
from django.http import HttpResponse


class BasicAuthMiddleware:
    """Optional HTTP basic-auth gate, used in staging only.

    Activated by setting BASIC_AUTH_REQUIRED=True plus BASIC_AUTH_USERNAME
    and BASIC_AUTH_PASSWORD. Off by default in dev and prod.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.required = getattr(settings, "BASIC_AUTH_REQUIRED", False)
        self.username = getattr(settings, "BASIC_AUTH_USERNAME", "")
        self.password = getattr(settings, "BASIC_AUTH_PASSWORD", "")

    def __call__(self, request):
        if not self.required:
            return self.get_response(request)

        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Basic "):
            try:
                creds = base64.b64decode(header[6:]).decode("utf-8")
                user, _, pwd = creds.partition(":")
                if user == self.username and pwd == self.password:
                    return self.get_response(request)
            except (ValueError, UnicodeDecodeError):
                pass

        response = HttpResponse("Authentication required", status=401)
        response["WWW-Authenticate"] = 'Basic realm="Staging"'
        return response
```

- [ ] **Step 4: Wire it into staging settings**

Modify `alumni/settings/staging.py`:

```python
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
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `pytest core/tests/test_basic_auth.py -v`
Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add core/middleware.py core/tests/test_basic_auth.py alumni/settings/staging.py
git commit -m "feat: add basic-auth middleware for staging gate"
```

---

## Task 15: Final verification — full test suite green

**Files:** none (verification only)

- [ ] **Step 1: Lint design tokens, rebuild CSS, compile messages, run all checks**

Run:
```bash
npm run design:lint
npm run design:export
npm run css:build
python manage.py compilemessages
make check
make lint
make test
```

Expected: all commands exit cleanly. Final pytest output should show all tests passing across `test_smoke.py`, `test_health.py`, `test_base_template.py`, `test_i18n.py`, `test_design_tokens.py`, `test_auth.py`, `test_static_assets.py`, `test_basic_auth.py`.

- [ ] **Step 2: Manually browse the running site one last time**

Run: `make db-up && python manage.py runserver`

Visit and verify:
- `http://localhost:8000/` — landing placeholder renders, French copy, base font 16px (inspect in DevTools), `noindex` meta in source.
- `http://localhost:8000/health` — JSON `{"status": "ok", "db": "ok"}`.
- `http://localhost:8000/accounts/login/` — login form renders with French labels.
- `http://localhost:8000/accounts/signup/` — 404 (signup disabled).
- `http://localhost:8000/admin/` — Django admin login renders.

- [ ] **Step 3: Tag the foundation milestone**

```bash
git tag -a v0.1.0-foundation -m "Foundation milestone: Django + Postgres + HTMX + Tailwind + Allauth + i18n + a11y + CI"
```

> *No `git push` here — the user will push to their chosen remote when ready.*

---

## Out of scope (handed off to subsequent plans)

- **P2 (Membership):** `Member` model, profile pages, directory with search/filters/pagination, Cloudinary upload integration, `NotificationPreference`, `ConsentRecord`.
- **P3 (Cooptation):** `AdminApplication`, `CooptationRequest`, J+7/J+14 deadline machinery (Django management command + cron), knowledge questionnaire, admin moderation UI, email templates, Resend integration, `AdminApplication` 6-month retention purge.
- **P4 (Public surface):** Public landing page (replaces the placeholder), `PublicSearchEntry` model with collegial validation, public removal flow without auth, `noindex` differentiation between public and private pages.
- **P5 (Mémoire seed):** `Memory` model, Mur des souvenirs admin-only gallery, `InMemoriamEntry`, In Memoriam seed page.
- **P6 (Ops & RGPD):** GitHub Actions backup workflow Cloudinary→B2, `purge_user_from_backups.py`, RGPD deletion flow, DMARC monitoring, `AuditLog` model + decorator.
- **P7 (Soft launch):** Seed content prep, pilot rollout, production launch checklist.

> *Each subsequent plan will be written individually, after the prior one ships.*
