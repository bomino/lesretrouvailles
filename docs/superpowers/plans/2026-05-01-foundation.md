# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the Django 5 project with Postgres, the HTMX + Tailwind + DaisyUI frontend stack, Allauth (email-only login, signup disabled at this layer), French i18n + accessibility baseline, pytest + ruff + pre-commit + GitHub Actions CI, and a `/health` endpoint — providing the working web shell that all subsequent feature plans depend on.

**Architecture:** Single Django 5 monolith with split settings (`base` / `dev` / `staging` / `prod`). Postgres 16 in Docker Compose for development. Tailwind 3 + DaisyUI 4 compiled to a single CSS bundle via the Tailwind CLI. HTMX 2.x served from the project's static files (not CDN — long-term reliability and offline-capable dev). French as the default and only V1 locale, with `gettext` machinery active so Hausa can be added in Phase 4 without refactor. Accessibility baseline enforced in the base template (16px root font, WCAG AA contrast tokens, no hover-only interactions, 44×44 minimum tactile targets).

**Tech Stack:** Python 3.12 · Django 5.x · PostgreSQL 16 · django-allauth · Tailwind CSS 3.4 · DaisyUI 4 · HTMX 2.x · pytest-django · factory-boy · ruff (lint + format) · pre-commit · GitHub Actions.

**Reference spec:** `docs/superpowers/specs/2026-05-01-alumni-platform-design.md` (PRD v1.3).

---

## File Structure

Files created/modified by this plan, with one-line responsibility:

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python project metadata, runtime + dev dependencies, tool config (ruff, black, pytest) |
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
| `tailwind.config.js` | Tailwind + DaisyUI config |
| `postcss.config.js` | PostCSS pipeline |
| `package.json` | Node tooling for Tailwind build |
| `locale/fr/LC_MESSAGES/django.po` | French translations file (placeholder) |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff, black, prettier) |
| `.github/workflows/test.yml` | CI: pytest + ruff + black + djlint on push/PR |
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
<body class="bg-base-100 text-base-content">
  <a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 btn btn-primary">
    {% trans "Aller au contenu principal" %}
  </a>
  <main id="main" class="container mx-auto p-4">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

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
git commit -m "chore: add pre-commit hooks (ruff, black, djlint)"
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

- [ ] **Step 1: Build CSS, compile messages, run all checks**

Run:
```bash
npm run css:build
python manage.py compilemessages
make check
make lint
make test
```

Expected: all four exit cleanly. Final pytest output should show all tests passing across `test_smoke.py`, `test_health.py`, `test_base_template.py`, `test_i18n.py`, `test_auth.py`, `test_static_assets.py`, `test_basic_auth.py`.

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
