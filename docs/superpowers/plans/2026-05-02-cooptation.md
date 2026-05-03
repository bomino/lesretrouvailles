# P3 Cooptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the cooptation flow end-to-end — public signup form, secure-link parrain vouching, J+7/J+14 deadline machinery via a daily Railway cron, knowledge-questionnaire fallback (2 closed auto-graded + 1 open admin-graded), admin moderation actions, Allauth password-set link on approval, 6-month retention purge of rejected applications, and full Resend email integration for all 10 notifications in PRD Annexe E.

**Architecture:** New `cooptation/` Django app, separate from `members/`. The cooptation flow creates a `Member` row at admin approval time; `members/` does not depend on `cooptation/`. A custom `alumni.email.ResendBackend` (wrapping the official `resend` SDK) ships every transactional email; tests use a `FakeResendBackend` that records calls without network. Approve/reject/purge logic lives in `cooptation/services.py`, called from the admin's custom actions. A daily `manage.py process_cooptation_deadlines` command runs in a separate Railway cron service sharing the same Docker image and env, handling J+7 reminders, J+14 expiry transitions, and retention purges.

**Tech Stack:** Django 5.0 · PostgreSQL 16 · `resend` (Python SDK) · `django-ratelimit` · Allauth (password-reset machinery) · pytest-django · `freezegun` (cron time-travel tests) · BeautifulSoup (a11y assertions) · Railway cron service.

**Spec:** [docs/superpowers/specs/2026-05-02-cooptation-design.md](../specs/2026-05-02-cooptation-design.md)

---

## File Structure

**New files:**

- `alumni/email.py` — `ResendBackend`, `FakeResendBackend`, `send_email()` helper
- `cooptation/__init__.py`, `apps.py`, `admin.py`, `models.py`, `forms.py`, `views.py`, `services.py`, `emails.py`, `urls.py`
- `cooptation/management/__init__.py`, `cooptation/management/commands/__init__.py`
- `cooptation/management/commands/process_cooptation_deadlines.py`
- `cooptation/management/commands/seed_questions.py`
- `cooptation/migrations/0001_initial.py` (auto-generated)
- `cooptation/templates/cooptation/signup.html`, `signup_success.html`, `parrain_vouch.html`, `parrain_vouch_done.html`, `parrain_vouch_expired.html`, `questionnaire.html`, `questionnaire_done.html`
- `cooptation/templates/emails/cooptation/<10 templates>.{txt,html,subject.txt}` (30 files total)
- `cooptation/tests/__init__.py`, `conftest.py`
- `cooptation/tests/test_email_backend.py`, `test_models.py`, `test_seed_questions.py`, `test_email_templates.py`, `test_services.py`, `test_signup_view.py`, `test_parrain_vouch_view.py`, `test_questionnaire_view.py`, `test_admin_actions.py`, `test_process_deadlines.py`, `test_a11y.py`, `test_e2e_happy_path.py`

**Modified files:**

- `pyproject.toml` — add `resend>=2.0` and `freezegun>=1.5` (test-only)
- `alumni/settings/base.py` — `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`, `LOGIN_REQUIRED_WHITELIST` additions
- `alumni/settings/staging.py` — `EMAIL_BACKEND="alumni.email.ResendBackend"`, `PASSWORD_RESET_TIMEOUT=7*24*60*60`
- `alumni/settings/prod.py` — same
- `alumni/middleware.py` — add `/cooptation/` to `ConsentRequiredMiddleware.SKIP_PREFIXES`
- `alumni/urls.py` — include `cooptation.urls`
- `.env.example` — document new env vars
- `docs/superpowers/STATUS.md` — P3 row + task table

---

## Task 1: Add dependencies and scaffold the `cooptation` app

**Files:**
- Modify: `pyproject.toml`
- Modify: `alumni/settings/base.py`
- Modify: `alumni/middleware.py`
- Modify: `alumni/urls.py`
- Modify: `.env.example`
- Create: `cooptation/__init__.py`, `apps.py`, `admin.py`, `models.py`, `forms.py`, `views.py`, `services.py`, `emails.py`, `urls.py`
- Create: `cooptation/migrations/__init__.py`, `cooptation/tests/__init__.py`

- [ ] **Step 1: Add deps to `pyproject.toml`**

In the `dependencies = [...]` block, add `"resend>=2.0"` after `"redis>=5.0"`:

```toml
dependencies = [
    "django>=5.0,<5.1",
    "psycopg[binary]>=3.1",
    "django-allauth>=0.61",
    "django-environ>=0.11",
    "whitenoise>=6.6",
    "gunicorn>=21",
    "cloudinary>=1.40",
    "django-ratelimit>=4.1",
    "markdown>=3.6",
    "redis>=5.0",
    "resend>=2.0",
]
```

In `dev = [...]`, add `"freezegun>=1.5"` for time-travel tests:

```toml
dev = [
    "pytest>=8",
    "pytest-django>=4.8",
    "factory-boy>=3.3",
    "ruff>=0.4",
    "pre-commit>=3.7",
    "djlint>=1.34",
    "beautifulsoup4>=4.12",
    "freezegun>=1.5",
]
```

Mirror the addition in `requirements.txt` (Railpack fallback):

```
django>=5.0,<5.1
psycopg[binary]>=3.1
django-allauth>=0.61
django-environ>=0.11
whitenoise>=6.6
gunicorn>=21
cloudinary>=1.40
django-ratelimit>=4.1
markdown>=3.6
redis>=5.0
resend>=2.0
```

- [ ] **Step 2: Install**

Run: `python -m pip install -e ".[dev]"`
Expected: `resend` and `freezegun` installed.

- [ ] **Step 3: Scaffold the app**

`cooptation/__init__.py`: empty file.

`cooptation/apps.py`:

```python
from django.apps import AppConfig


class CooptationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cooptation"
    verbose_name = "Cooptation"
```

`cooptation/admin.py`: empty (Task 12 fills it):

```python
# Admin registrations land in Task 12.
```

`cooptation/models.py`, `forms.py`, `views.py`, `services.py`, `emails.py`, `urls.py`: each contains a single comment line:

```python
# Implemented in subsequent tasks.
```

`cooptation/migrations/__init__.py`: empty.
`cooptation/tests/__init__.py`: empty.

- [ ] **Step 4: Register the app in `alumni/settings/base.py`**

Add `"cooptation"` as the last entry in `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "core",
    "members",
    "cooptation",
]
```

- [ ] **Step 5: Add settings additions to `alumni/settings/base.py`**

Append at the bottom:

```python
# Resend email
RESEND_API_KEY = env("RESEND_API_KEY", default="")

# Email defaults — DEFAULT_FROM_EMAIL applies in dev (console) and overrideable per env.
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="Les Retrouvailles <noreply@villageretrouvailles.com>",
)
```

In the existing `LOGIN_REQUIRED_WHITELIST` list, add the public cooptation paths:

```python
LOGIN_REQUIRED_WHITELIST = [
    "/",
    "/health",
    "/accounts/",
    "/static/",
    "/media/",
    "/inscription/",
    "/questionnaire/",
]
```

- [ ] **Step 6: Add `/cooptation/` skip to `ConsentRequiredMiddleware`**

In `alumni/middleware.py`, find the `ConsentRequiredMiddleware` class and update `SKIP_PREFIXES`:

```python
class ConsentRequiredMiddleware:
    SKIP_PREFIXES = ("/charte/", "/accounts/logout/", "/cooptation/")
    SESSION_KEY = "consent_ok_for"
```

- [ ] **Step 7: Mount cooptation URLs in `alumni/urls.py`**

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("cooptation.urls")),
    path("", include("members.urls")),
    path("", include("core.urls")),
]
```

- [ ] **Step 8: Stub `cooptation/urls.py`** (real routes added in later tasks):

```python
from django.urls import path

app_name = "cooptation"

urlpatterns = []
```

- [ ] **Step 9: Document new env vars in `.env.example`**

Append:

```bash
# Resend (P3 cooptation emails). Leave blank in dev; tests use the FakeResendBackend.
RESEND_API_KEY=
# Configure your sending identity. For staging, the Resend-verified domain.
DEFAULT_FROM_EMAIL=Les Retrouvailles <noreply@villageretrouvailles.com>
```

- [ ] **Step 10: Verify Django still boots**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 11: Run the existing test suite to confirm no regression**

Run: `pytest -q`
Expected: 149+ passed (whatever the count is at start of P3, no failures).

- [ ] **Step 12: Commit**

```bash
git add pyproject.toml requirements.txt alumni/settings/base.py alumni/middleware.py alumni/urls.py .env.example cooptation/
git commit -m "chore: scaffold cooptation app and add P3 dependencies"
```

---

## Task 2: Resend email backend and `send_email` helper

**Files:**
- Create: `alumni/email.py`
- Create: `cooptation/tests/test_email_backend.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/test_email_backend.py`:

```python
import pytest
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings


@override_settings(EMAIL_BACKEND="alumni.email.FakeResendBackend")
def test_fake_backend_records_simple_message():
    from alumni.email import FakeResendBackend
    from django.core.mail import get_connection

    conn = get_connection()
    msg = EmailMultiAlternatives(
        subject="Hello",
        body="Plain text body",
        from_email="noreply@example.test",
        to=["alice@example.test"],
    )
    msg.attach_alternative("<p>HTML body</p>", "text/html")
    sent = conn.send_messages([msg])

    assert sent == 1
    assert len(conn.sent_messages) == 1
    rec = conn.sent_messages[0]
    assert rec["from"] == "noreply@example.test"
    assert rec["to"] == ["alice@example.test"]
    assert rec["subject"] == "Hello"
    assert rec["text"] == "Plain text body"
    assert rec["html"] == "<p>HTML body</p>"


@override_settings(EMAIL_BACKEND="alumni.email.FakeResendBackend")
def test_fake_backend_handles_text_only_message():
    from django.core.mail import get_connection

    conn = get_connection()
    msg = EmailMultiAlternatives(
        subject="Plain",
        body="Body only",
        from_email="x@example.test",
        to=["b@example.test"],
    )
    sent = conn.send_messages([msg])
    assert sent == 1
    assert "html" not in conn.sent_messages[0]


def test_send_email_helper_renders_text_html_subject(tmp_path, settings):
    """send_email loads <base>.txt, <base>.html, <base>.subject.txt and
    sends a multipart message via Django's email backend."""
    from alumni.email import send_email

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"

    # Use the `application_received` template that exists in cooptation app.
    # Until Task 7 lands the templates, this test is wired to a placeholder
    # template path that we will create below.
    from django.core.mail import get_connection

    conn = get_connection()
    # Confirm the helper accepts the expected args without raising;
    # template rendering is tested in test_email_templates.py once
    # the actual templates exist.
    assert callable(send_email)
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_email_backend.py -v`
Expected: ImportError on `alumni.email`.

- [ ] **Step 3: Implement `alumni/email.py`**

```python
"""Resend email integration: production backend + test fake + render helper."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class ResendBackend(BaseEmailBackend):
    """Sends each EmailMessage via Resend's REST API.

    Required settings:
        RESEND_API_KEY  — set in env.
    """

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        import resend  # imported lazily so tests don't require network

        resend.api_key = settings.RESEND_API_KEY
        sent = 0
        for msg in email_messages:
            payload: dict[str, Any] = {
                "from": msg.from_email or settings.DEFAULT_FROM_EMAIL,
                "to": list(msg.to),
                "subject": msg.subject,
                "text": msg.body,
            }
            html = next(
                (alt[0] for alt in (msg.alternatives or []) if alt[1] == "text/html"),
                None,
            )
            if html is not None:
                payload["html"] = html
            try:
                resend.Emails.send(payload)
                sent += 1
            except Exception:
                logger.exception("Resend delivery failed for to=%s", msg.to)
                if not self.fail_silently:
                    raise
        return sent


class FakeResendBackend(BaseEmailBackend):
    """Records messages in-process for tests; no network calls."""

    sent_messages: list[dict[str, Any]] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reset on each backend construction so test ordering does not bleed.
        type(self).sent_messages = []

    def send_messages(self, email_messages):
        sent = 0
        for msg in email_messages:
            rec: dict[str, Any] = {
                "from": msg.from_email or "",
                "to": list(msg.to),
                "subject": msg.subject,
                "text": msg.body,
            }
            html = next(
                (alt[0] for alt in (msg.alternatives or []) if alt[1] == "text/html"),
                None,
            )
            if html is not None:
                rec["html"] = html
            type(self).sent_messages.append(rec)
            sent += 1
        return sent


def send_email(to: str | list[str], template_base: str, context: dict[str, Any]) -> None:
    """Render `<template_base>.subject.txt`, `.txt`, and `.html` from
    `templates/emails/` and send a multipart message via Django's configured
    email backend.

    Example:
        send_email("alice@example.test",
                   "cooptation/parrain_invitation",
                   {"candidate": app, "vouch_url": url})
    """
    recipients = [to] if isinstance(to, str) else list(to)
    subject = render_to_string(f"emails/{template_base}.subject.txt", context).strip()
    text_body = render_to_string(f"emails/{template_base}.txt", context)
    html_body = render_to_string(f"emails/{template_base}.html", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()
```

- [ ] **Step 4: Run the new tests**

Run: `pytest cooptation/tests/test_email_backend.py -v`
Expected: 3 passed (the third just confirms `send_email` is callable; full template rendering is verified in Task 7).

- [ ] **Step 5: Commit**

```bash
git add alumni/email.py cooptation/tests/test_email_backend.py
git commit -m "feat(email): add ResendBackend, FakeResendBackend, and send_email helper"
```

---

## Task 3: `AdminApplication` model with state machine

**Files:**
- Modify: `cooptation/models.py`
- Create: `cooptation/migrations/0001_initial.py` (auto-generated by `makemigrations` after all models in subsequent tasks)
- Create: `cooptation/tests/test_models.py`
- Create: `cooptation/tests/conftest.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/conftest.py`:

```python
import pytest


@pytest.fixture
def make_application(db):
    from cooptation.models import AdminApplication

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "full_name": f"Candidate {counter['i']}",
            "nickname": "",
            "years_attended": [1980, 1981],
            "classes": ["6e", "5e"],
            "city": "Niamey",
            "country": "Niger",
            "profession": "",
            "email": f"candidate{counter['i']}@example.test",
            "whatsapp": "",
        }
        defaults.update(kwargs)
        return AdminApplication.objects.create(**defaults)

    return _make
```

`cooptation/tests/test_models.py`:

```python
import pytest
from django.utils import timezone


@pytest.mark.django_db
def test_application_default_status_is_cooptation_pending(make_application):
    app = make_application()
    assert app.status == "cooptation_pending"
    assert app.cooptation_outcome == "pending"


@pytest.mark.django_db
def test_application_purge_clears_all_pii(make_application):
    app = make_application(
        full_name="Real Name",
        nickname="Nick",
        email="real@example.test",
        whatsapp="+227 90 00 00 00",
        city="Zinder",
        country="Niger",
        profession="Enseignant",
        review_note="Long internal note",
    )
    app.source_ip = "192.168.1.10"
    app.save()
    app.purge()
    app.refresh_from_db()
    assert app.full_name == ""
    assert app.nickname == ""
    assert app.email == ""
    assert app.whatsapp == ""
    assert app.city == ""
    assert app.country == ""
    assert app.profession == ""
    assert app.review_note == ""
    assert app.source_ip is None
    assert app.status == "purged"
    assert app.purged_at is not None


@pytest.mark.django_db
def test_application_status_choices_validated(make_application):
    """We use a CharField with choices but no DB CHECK; Django validates
    in full_clean() and the admin form. Verify the choices are exactly
    the 5 documented states."""
    from cooptation.models import AdminApplication

    expected = {
        "cooptation_pending",
        "awaiting_admin",
        "approved",
        "rejected",
        "purged",
    }
    actual = {choice for choice, _ in AdminApplication.STATUS_CHOICES}
    assert actual == expected


@pytest.mark.django_db
def test_application_outcome_choices(make_application):
    from cooptation.models import AdminApplication

    expected = {"pending", "all_accepted", "mixed", "all_refused", "expired"}
    actual = {choice for choice, _ in AdminApplication.OUTCOME_CHOICES}
    assert actual == expected
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest cooptation/tests/test_models.py -v`
Expected: ImportError on `cooptation.models.AdminApplication`.

- [ ] **Step 3: Implement `AdminApplication` in `cooptation/models.py`**

Replace the placeholder with:

```python
"""Cooptation domain models."""

from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from members.models import GRADE_CHOICES


class AdminApplication(models.Model):
    STATUS_CHOICES = [
        ("cooptation_pending", "Cooptation en cours"),
        ("awaiting_admin", "En attente de l'admin"),
        ("approved", "Approuvé"),
        ("rejected", "Rejeté"),
        ("purged", "Purgé"),
    ]
    OUTCOME_CHOICES = [
        ("pending", "En attente"),
        ("all_accepted", "Deux accords"),
        ("mixed", "Un accord, un refus"),
        ("all_refused", "Deux refus"),
        ("expired", "Expiré (J+14)"),
    ]

    # PII — purged on retention expiry
    full_name = models.CharField(max_length=160, blank=True)
    nickname = models.CharField(max_length=60, blank=True)
    years_attended = ArrayField(models.IntegerField(), size=6, default=list)
    classes = ArrayField(models.CharField(max_length=4, choices=GRADE_CHOICES), size=4, default=list)
    city = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=80, blank=True, default="Niger")
    profession = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)

    # State
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="cooptation_pending")
    cooptation_outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES, default="pending")

    # Audit
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications",
    )
    review_note = models.TextField(blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    retention_until = models.DateTimeField(null=True, blank=True)
    purged_at = models.DateTimeField(null=True, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["email"]),
            models.Index(fields=["retention_until"]),
        ]
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.full_name or '<purged>'} ({self.status})"

    def purge(self) -> None:
        """Clear all PII fields; keep aggregate state for audit/stats."""
        self.full_name = ""
        self.nickname = ""
        self.email = ""
        self.whatsapp = ""
        self.city = ""
        self.country = ""
        self.profession = ""
        self.review_note = ""
        self.source_ip = None
        self.status = "purged"
        self.purged_at = timezone.now()
        self.save()
```

- [ ] **Step 4: Generate and apply the migration**

Run:
```bash
python manage.py makemigrations cooptation
python manage.py migrate cooptation
```

Expected: `0001_initial.py` created and applied.

- [ ] **Step 5: Run tests**

Run: `pytest cooptation/tests/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add cooptation/models.py cooptation/migrations/0001_initial.py cooptation/tests/conftest.py cooptation/tests/test_models.py
git commit -m "feat(cooptation): add AdminApplication model with 5-state machine and purge()"
```

---

## Task 4: `CooptationRequest` model

**Files:**
- Modify: `cooptation/models.py`
- Modify: `cooptation/migrations/0002_cooptationrequest.py` (auto-generated)
- Modify: `cooptation/tests/test_models.py`
- Modify: `cooptation/tests/conftest.py`

- [ ] **Step 1: Add a fixture for parrains and CooptationRequests**

Append to `cooptation/tests/conftest.py`:

```python
@pytest.fixture
def make_cooptation_request(db, make_application):
    """Create a CooptationRequest. Borrows make_member from members.tests."""
    from datetime import timedelta

    from django.utils import timezone

    from cooptation.models import CooptationRequest

    counter = {"i": 0}

    def _make(*, application=None, parrain=None, **kwargs):
        from members.tests.conftest import make_member as _members_make_member  # noqa

        counter["i"] += 1
        application = application or make_application()
        if parrain is None:
            # Build a Member directly to avoid pytest-fixture-injection inception.
            from django.contrib.auth import get_user_model

            from members.models import Member

            User = get_user_model()
            user = User.objects.create_user(
                username=f"parrain{counter['i']}@example.test",
                email=f"parrain{counter['i']}@example.test",
                password="x",
            )
            parrain = Member.objects.create(
                user=user,
                first_name=f"Parrain{counter['i']}",
                last_name="X",
                years_attended=[1980, 1981, 1982, 1983],
                classes=["6e", "5e", "4e", "3e"],
                city="Niamey",
            )
        defaults = {
            "application": application,
            "parrain": parrain,
            "expires_at": timezone.now() + timedelta(days=14),
        }
        defaults.update(kwargs)
        return CooptationRequest.objects.create(**defaults)

    return _make
```

- [ ] **Step 2: Write the failing tests**

Append to `cooptation/tests/test_models.py`:

```python
@pytest.mark.django_db
def test_cooptation_request_token_is_unique_and_urlsafe(make_cooptation_request):
    a = make_cooptation_request()
    b = make_cooptation_request()
    assert a.token != b.token
    assert len(a.token) >= 40  # token_urlsafe(32) yields ~43 chars
    # No padding chars or unsafe symbols
    for ch in a.token:
        assert ch.isalnum() or ch in "-_"


@pytest.mark.django_db
def test_cooptation_request_default_response_is_pending(make_cooptation_request):
    req = make_cooptation_request()
    assert req.response == "pending"
    assert req.responded_at is None
    assert req.reminder_sent_at is None


@pytest.mark.django_db
def test_cooptation_request_expires_at_required(make_cooptation_request):
    """expires_at has no DB default; the factory always sets it."""
    req = make_cooptation_request()
    assert req.expires_at is not None


@pytest.mark.django_db
def test_cooptation_request_application_cascade(make_cooptation_request, make_application):
    app = make_application()
    req = make_cooptation_request(application=app)
    req_pk = req.pk
    app.delete()
    from cooptation.models import CooptationRequest

    assert not CooptationRequest.objects.filter(pk=req_pk).exists()


@pytest.mark.django_db
def test_cooptation_request_parrain_protect(make_cooptation_request):
    """Deleting a Member that owns open cooptation requests must fail."""
    from django.db.models import ProtectedError

    req = make_cooptation_request()
    parrain = req.parrain
    user = parrain.user
    with pytest.raises(ProtectedError):
        user.delete()  # cascades to Member, which is PROTECT'd by CooptationRequest
```

- [ ] **Step 3: Confirm failure**

Run: `pytest cooptation/tests/test_models.py -v -k cooptation_request`
Expected: ImportError on `CooptationRequest`.

- [ ] **Step 4: Append to `cooptation/models.py`**

Add the import for `secrets` at the top, then append the model:

```python
import secrets


def _make_token() -> str:
    return secrets.token_urlsafe(32)


class CooptationRequest(models.Model):
    RESPONSE_CHOICES = [
        ("pending", "En attente"),
        ("accepted", "Accordée"),
        ("refused", "Refusée"),
    ]

    application = models.ForeignKey(
        AdminApplication,
        on_delete=models.CASCADE,
        related_name="cooptation_requests",
    )
    parrain = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        related_name="cooptation_requests",
    )
    token = models.CharField(max_length=64, unique=True, default=_make_token)
    expires_at = models.DateTimeField()
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    response = models.CharField(max_length=16, choices=RESPONSE_CHOICES, default="pending")
    responded_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["application", "response"]),
            models.Index(fields=["expires_at", "response"]),
        ]
        ordering = ["expires_at"]

    def __str__(self) -> str:
        return f"{self.parrain} → {self.application} ({self.response})"
```

- [ ] **Step 5: Migrate**

```bash
python manage.py makemigrations cooptation
python manage.py migrate cooptation
```

- [ ] **Step 6: Run tests**

Run: `pytest cooptation/tests/test_models.py -v`
Expected: 9 passed (4 from Task 3 + 5 new).

- [ ] **Step 7: Commit**

```bash
git add cooptation/models.py cooptation/migrations/0002_*.py cooptation/tests/test_models.py cooptation/tests/conftest.py
git commit -m "feat(cooptation): add CooptationRequest with token, expires_at, parrain PROTECT"
```

---

## Task 5: `KnowledgeQuestion` and `QuestionnaireResponse` models

**Files:**
- Modify: `cooptation/models.py`
- Modify: `cooptation/migrations/0003_questions.py` (auto-generated)
- Modify: `cooptation/tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `cooptation/tests/test_models.py`:

```python
@pytest.mark.django_db
def test_knowledge_question_kinds():
    from cooptation.models import KnowledgeQuestion

    expected = {"closed", "open"}
    actual = {choice for choice, _ in KnowledgeQuestion.KIND_CHOICES}
    assert actual == expected


@pytest.mark.django_db
def test_knowledge_question_ordered_by_position():
    from cooptation.models import KnowledgeQuestion

    KnowledgeQuestion.objects.create(position=2, kind="open", text="Souvenir")
    KnowledgeQuestion.objects.create(position=1, kind="closed", text="Prof", answer_keys=["x"])
    KnowledgeQuestion.objects.create(position=3, kind="closed", text="Salle", answer_keys=["y"])
    qs = list(KnowledgeQuestion.objects.all())
    assert [q.position for q in qs] == [1, 2, 3]


@pytest.mark.django_db
def test_questionnaire_response_unique_per_question_per_application(make_application):
    from django.db import IntegrityError

    from cooptation.models import KnowledgeQuestion, QuestionnaireResponse

    app = make_application()
    q = KnowledgeQuestion.objects.create(position=1, kind="open", text="t")
    QuestionnaireResponse.objects.create(application=app, question=q, candidate_answer="first")
    with pytest.raises(IntegrityError):
        QuestionnaireResponse.objects.create(application=app, question=q, candidate_answer="second")


@pytest.mark.django_db
def test_questionnaire_response_auto_grade_is_nullable(make_application):
    from cooptation.models import KnowledgeQuestion, QuestionnaireResponse

    app = make_application()
    q = KnowledgeQuestion.objects.create(position=1, kind="open", text="t")
    r = QuestionnaireResponse.objects.create(application=app, question=q, candidate_answer="x")
    assert r.auto_grade is None
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_models.py -v -k knowledge or questionnaire`
Expected: ImportError on `KnowledgeQuestion`.

- [ ] **Step 3: Append to `cooptation/models.py`**

```python
class KnowledgeQuestion(models.Model):
    KIND_CHOICES = [
        ("closed", "Réponse courte"),
        ("open", "Réponse libre"),
    ]
    position = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    text = models.CharField(max_length=500)
    answer_keys = ArrayField(
        models.CharField(max_length=80),
        default=list,
        blank=True,
        help_text="Clés de réponse acceptées (insensibles aux accents et à la casse). Vide pour les questions ouvertes.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]

    def __str__(self) -> str:
        return f"Q{self.position}: {self.text[:40]}"


class QuestionnaireResponse(models.Model):
    application = models.ForeignKey(
        AdminApplication,
        on_delete=models.CASCADE,
        related_name="questionnaire_responses",
    )
    question = models.ForeignKey(KnowledgeQuestion, on_delete=models.PROTECT)
    candidate_answer = models.TextField()
    auto_grade = models.BooleanField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("application", "question")]
        ordering = ["question__position"]

    def __str__(self) -> str:
        return f"Q{self.question.position} → {self.application}"
```

- [ ] **Step 4: Migrate**

```bash
python manage.py makemigrations cooptation
python manage.py migrate cooptation
```

- [ ] **Step 5: Run tests**

Run: `pytest cooptation/tests/test_models.py -v`
Expected: 13 passed.

- [ ] **Step 6: Commit**

```bash
git add cooptation/models.py cooptation/migrations/0003_*.py cooptation/tests/test_models.py
git commit -m "feat(cooptation): add KnowledgeQuestion and QuestionnaireResponse models"
```

---

## Task 6: `seed_questions` management command

**Files:**
- Create: `cooptation/management/__init__.py`
- Create: `cooptation/management/commands/__init__.py`
- Create: `cooptation/management/commands/seed_questions.py`
- Create: `cooptation/tests/test_seed_questions.py`

- [ ] **Step 1: Write the failing test**

`cooptation/tests/test_seed_questions.py`:

```python
import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_questions_creates_three_questions():
    call_command("seed_questions")
    from cooptation.models import KnowledgeQuestion

    qs = list(KnowledgeQuestion.objects.all())
    assert len(qs) == 3
    assert [q.position for q in qs] == [1, 2, 3]
    assert qs[0].kind == "closed"
    assert qs[1].kind == "closed"
    assert qs[2].kind == "open"
    assert qs[2].answer_keys == []  # open question has no keys


@pytest.mark.django_db
def test_seed_questions_idempotent():
    call_command("seed_questions")
    call_command("seed_questions")
    from cooptation.models import KnowledgeQuestion

    assert KnowledgeQuestion.objects.count() == 3
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_seed_questions.py -v`
Expected: `Unknown command: 'seed_questions'`.

- [ ] **Step 3: Create the command**

`cooptation/management/__init__.py`: empty.
`cooptation/management/commands/__init__.py`: empty.

`cooptation/management/commands/seed_questions.py`:

```python
"""Seed the 3 default knowledge questions. Idempotent (uses get_or_create on position)."""

from django.core.management.base import BaseCommand

from cooptation.models import KnowledgeQuestion

DEFAULT_QUESTIONS = [
    {
        "position": 1,
        "kind": "closed",
        "text": "Cite un professeur du CEG 1 entre 1980 et 1985.",
        "answer_keys": [],
    },
    {
        "position": 2,
        "kind": "closed",
        "text": "Comment s'appelait la principale autorité du CEG 1 dans ces années ?",
        "answer_keys": [],
    },
    {
        "position": 3,
        "kind": "open",
        "text": "Décris en quelques phrases un souvenir précis de ta scolarité au CEG 1.",
        "answer_keys": [],
    },
]


class Command(BaseCommand):
    help = "Seed the default knowledge questions. Admins must populate answer_keys via Django admin before launch."

    def handle(self, *args, **opts):
        for entry in DEFAULT_QUESTIONS:
            KnowledgeQuestion.objects.get_or_create(
                position=entry["position"],
                defaults={
                    "kind": entry["kind"],
                    "text": entry["text"],
                    "answer_keys": entry["answer_keys"],
                    "is_active": True,
                },
            )
        self.stdout.write(self.style.SUCCESS("3 questions seeded (or already present)."))
```

- [ ] **Step 4: Run the tests**

Run: `pytest cooptation/tests/test_seed_questions.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add cooptation/management/ cooptation/tests/test_seed_questions.py
git commit -m "feat(cooptation): add seed_questions management command"
```

---

## Task 7: 10 email templates and `emails.py` wrappers

**Files:**
- Create: `cooptation/templates/emails/cooptation/<10 templates × 3 files>` (30 files)
- Modify: `cooptation/emails.py`
- Create: `cooptation/tests/test_email_templates.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/test_email_templates.py`:

```python
import pytest
from django.test import override_settings


@pytest.fixture
def fake_backend(settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.DEFAULT_FROM_EMAIL = "Les Retrouvailles <noreply@example.test>"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    return FakeResendBackend


@pytest.mark.django_db
def test_application_received_renders_to_candidate(fake_backend, make_application):
    from cooptation.emails import send_application_received

    app = make_application(full_name="Idrissa Saidou", email="idrissa@example.test")
    send_application_received(app)
    msgs = fake_backend.sent_messages
    assert len(msgs) == 1
    m = msgs[0]
    assert m["to"] == ["idrissa@example.test"]
    assert "Idrissa Saidou" in m["text"]
    assert "<" in m["html"]  # HTML alternative attached
    assert m["subject"]
    # Sanity: subject should be a single line, no template noise
    assert "\n" not in m["subject"]


@pytest.mark.django_db
def test_parrain_invitation_includes_token_url(fake_backend, make_cooptation_request):
    from cooptation.emails import send_parrain_invitation

    req = make_cooptation_request()
    send_parrain_invitation(req)
    msg = fake_backend.sent_messages[0]
    assert msg["to"] == [req.parrain.user.email]
    assert req.token in msg["text"]
    assert req.token in msg["html"]


@pytest.mark.django_db
def test_parrain_reminder_renders(fake_backend, make_cooptation_request):
    from cooptation.emails import send_parrain_reminder

    req = make_cooptation_request()
    send_parrain_reminder(req)
    assert len(fake_backend.sent_messages) == 1


@pytest.mark.django_db
def test_cooptation_accepted_renders(fake_backend, make_cooptation_request):
    from cooptation.emails import send_cooptation_accepted

    req = make_cooptation_request()
    send_cooptation_accepted(req)
    assert len(fake_backend.sent_messages) == 1
    assert fake_backend.sent_messages[0]["to"] == [req.application.email]


@pytest.mark.django_db
def test_cooptation_refused_renders(fake_backend, make_cooptation_request):
    from cooptation.emails import send_cooptation_refused

    req = make_cooptation_request()
    send_cooptation_refused(req)
    assert len(fake_backend.sent_messages) == 1


@pytest.mark.django_db
def test_cooptation_requests_sent_renders(fake_backend, make_application):
    from cooptation.emails import send_cooptation_requests_sent

    app = make_application(email="c@example.test")
    send_cooptation_requests_sent(app, parrain_emails=["p1@example.test", "p2@example.test"])
    msg = fake_backend.sent_messages[0]
    assert "p1@example.test" in msg["text"] or "p1@example.test" in msg["html"]


@pytest.mark.django_db
def test_cooptation_expired_includes_questionnaire_url(fake_backend, make_application):
    from cooptation.emails import send_cooptation_expired

    app = make_application(email="c@example.test")
    send_cooptation_expired(app, questionnaire_url="https://example.test/questionnaire/abc/")
    msg = fake_backend.sent_messages[0]
    assert "https://example.test/questionnaire/abc/" in msg["text"]


@pytest.mark.django_db
def test_application_approved_includes_password_set_url(fake_backend, make_application):
    from cooptation.emails import send_application_approved

    app = make_application(email="c@example.test")
    send_application_approved(app, password_set_url="https://example.test/accounts/password/reset/key/abc/")
    msg = fake_backend.sent_messages[0]
    assert "https://example.test/accounts/password/reset/key/abc/" in msg["text"]


@pytest.mark.django_db
def test_application_rejected_includes_reason(fake_backend, make_application):
    from cooptation.emails import send_application_rejected

    app = make_application(email="c@example.test")
    send_application_rejected(app, reason="Promotion non éligible")
    msg = fake_backend.sent_messages[0]
    assert "Promotion non éligible" in msg["text"]


@pytest.mark.django_db
def test_admin_new_application_to_all_staff(fake_backend, make_application):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    User.objects.create_user(username="staff1", email="staff1@example.test", password="x", is_staff=True)
    User.objects.create_user(username="staff2", email="staff2@example.test", password="x", is_staff=True)
    User.objects.create_user(username="user1", email="user1@example.test", password="x")  # not staff

    from cooptation.emails import send_admin_new_application

    app = make_application()
    send_admin_new_application(app)
    msg = fake_backend.sent_messages[0]
    assert sorted(msg["to"]) == ["staff1@example.test", "staff2@example.test"]


@pytest.mark.django_db
def test_each_template_includes_french_phrase(fake_backend, make_application, make_cooptation_request):
    """Smoke test that French strings render (not raw msgid passthrough or English)."""
    from cooptation.emails import (
        send_application_received,
        send_application_approved,
        send_application_rejected,
        send_cooptation_accepted,
        send_cooptation_refused,
        send_cooptation_requests_sent,
        send_cooptation_expired,
        send_parrain_invitation,
        send_parrain_reminder,
        send_admin_new_application,
    )

    app = make_application(email="c@example.test")
    req = make_cooptation_request(application=app)

    send_application_received(app)
    send_application_approved(app, password_set_url="https://x/")
    send_application_rejected(app, reason="x")
    send_cooptation_accepted(req)
    send_cooptation_refused(req)
    send_cooptation_requests_sent(app, parrain_emails=["a@b"])
    send_cooptation_expired(app, questionnaire_url="https://x/")
    send_parrain_invitation(req)
    send_parrain_reminder(req)
    send_admin_new_application(app)

    # 10 emails sent
    assert len(fake_backend.sent_messages) == 10
    # Each must contain at least one of these French markers — accent-tolerant.
    french_markers = ["bonjour", "cher", "votre", "merci", "cooptation", "communauté", "communaute", "membre"]
    for m in fake_backend.sent_messages:
        text_lower = m["text"].lower()
        assert any(marker in text_lower for marker in french_markers), m["subject"]
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_email_templates.py -v`
Expected: ImportError on `cooptation.emails`.

- [ ] **Step 3: Implement `cooptation/emails.py`**

```python
"""Email senders — one function per template. Thin wrappers over alumni.email.send_email."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from alumni.email import send_email

from .models import AdminApplication, CooptationRequest


def send_application_received(application: AdminApplication) -> None:
    send_email(
        application.email,
        "cooptation/application_received",
        {"application": application},
    )


def send_cooptation_requests_sent(application: AdminApplication, *, parrain_emails: list[str]) -> None:
    send_email(
        application.email,
        "cooptation/cooptation_requests_sent",
        {"application": application, "parrain_emails": parrain_emails},
    )


def send_cooptation_accepted(request: CooptationRequest) -> None:
    send_email(
        request.application.email,
        "cooptation/cooptation_accepted",
        {"application": request.application, "request": request},
    )


def send_cooptation_refused(request: CooptationRequest) -> None:
    send_email(
        request.application.email,
        "cooptation/cooptation_refused",
        {"application": request.application, "request": request},
    )


def send_cooptation_expired(application: AdminApplication, *, questionnaire_url: str) -> None:
    send_email(
        application.email,
        "cooptation/cooptation_expired",
        {"application": application, "questionnaire_url": questionnaire_url},
    )


def send_application_approved(application: AdminApplication, *, password_set_url: str) -> None:
    send_email(
        application.email,
        "cooptation/application_approved",
        {"application": application, "password_set_url": password_set_url},
    )


def send_application_rejected(application: AdminApplication, *, reason: str) -> None:
    send_email(
        application.email,
        "cooptation/application_rejected",
        {"application": application, "reason": reason},
    )


def send_parrain_invitation(request: CooptationRequest) -> None:
    send_email(
        request.parrain.user.email,
        "cooptation/parrain_invitation",
        {"application": request.application, "request": request},
    )


def send_parrain_reminder(request: CooptationRequest) -> None:
    send_email(
        request.parrain.user.email,
        "cooptation/parrain_reminder",
        {"application": request.application, "request": request},
    )


def send_admin_new_application(application: AdminApplication) -> None:
    User = get_user_model()
    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True).values_list("email", flat=True)
    )
    if not staff_emails:
        return
    send_email(
        staff_emails,
        "cooptation/admin_new_application",
        {"application": application},
    )
```

- [ ] **Step 4: Create the 30 template files**

Make the directory:

```bash
mkdir -p cooptation/templates/emails/cooptation
```

For each of the 10 templates, create three files: `<name>.subject.txt`, `<name>.txt`, `<name>.html`.

`cooptation/templates/emails/cooptation/application_received.subject.txt`:
```
Votre demande d'inscription aux Retrouvailles a bien été reçue
```

`cooptation/templates/emails/cooptation/application_received.txt`:
```
Bonjour {{ application.full_name }},

Merci pour votre demande d'inscription à la communauté Les Retrouvailles. Nous avons bien reçu votre dossier le {{ application.submitted_at|date:"d F Y" }}.

Vos parrains vont recevoir une demande de cooptation par email. Dès qu'ils auront répondu, vous recevrez une nouvelle notification de notre part.

Délai indicatif : sous 14 jours.

À très bientôt,
L'équipe Les Retrouvailles
```

`cooptation/templates/emails/cooptation/application_received.html`:
```html
<!DOCTYPE html>
<html lang="fr"><body style="font-family: Inter, system-ui, sans-serif; color: #1A1C1E;">
<p>Bonjour <strong>{{ application.full_name }}</strong>,</p>
<p>Merci pour votre demande d'inscription à la communauté <strong>Les Retrouvailles</strong>. Nous avons bien reçu votre dossier le {{ application.submitted_at|date:"d F Y" }}.</p>
<p>Vos parrains vont recevoir une demande de cooptation par email. Dès qu'ils auront répondu, vous recevrez une nouvelle notification de notre part.</p>
<p style="color:#6c7278;">Délai indicatif : sous 14 jours.</p>
<p>À très bientôt,<br>L'équipe Les Retrouvailles</p>
</body></html>
```

Use the same text+html+subject pattern for the remaining 9 templates. Below are the **subject lines** and **canonical text bodies** for each (HTML versions follow the same structure as `application_received.html` — wrap paragraphs in `<p>`, bold the candidate name where appropriate):

**`cooptation_requests_sent`**
- Subject: `Vos parrains ont été contactés`
- Body:
```
Bonjour {{ application.full_name }},

Une demande de cooptation a été envoyée à :
{% for email in parrain_emails %}- {{ email }}
{% endfor %}
Vous serez notifié·e dès qu'ils auront répondu. Si vous ne recevez pas de nouvelles sous 7 jours, nous leur enverrons une relance.

L'équipe Les Retrouvailles
```

**`cooptation_accepted`**
- Subject: `{{ request.parrain.full_name }} vous a coopté !`
- Body:
```
Bonjour {{ application.full_name }},

Bonne nouvelle : {{ request.parrain.full_name }} vient d'accepter de vous coopter dans la communauté Les Retrouvailles.

Nous attendons encore la réponse de votre second parrain. Dès que tous vos parrains auront répondu, l'admin examinera votre dossier et vous recevrez une décision finale.

L'équipe Les Retrouvailles
```

**`cooptation_refused`**
- Subject: `Mise à jour sur votre cooptation`
- Body:
```
Bonjour {{ application.full_name }},

{{ request.parrain.full_name }} a indiqué ne pas être en mesure de vous coopter à ce stade. Cela ne signifie pas que votre dossier est rejeté ; l'admin examinera l'ensemble des réponses avant de décider.

Vous serez notifié·e de la décision finale.

L'équipe Les Retrouvailles
```

**`cooptation_expired`**
- Subject: `La cooptation a expiré — questionnaire à compléter`
- Body:
```
Bonjour {{ application.full_name }},

Le délai de cooptation de 14 jours a expiré sans que vos deux parrains aient pu répondre. Pour valider votre identité, merci de compléter le bref questionnaire ci-dessous :

{{ questionnaire_url }}

Le questionnaire ne prend que quelques minutes. Une fois soumis, l'admin examinera votre dossier.

L'équipe Les Retrouvailles
```

**`application_approved`**
- Subject: `Bienvenue chez Les Retrouvailles — votre compte est prêt`
- Body:
```
Bonjour {{ application.full_name }},

Votre demande a été approuvée. Bienvenue dans la communauté Les Retrouvailles !

Pour activer votre compte, choisissez votre mot de passe ici :

{{ password_set_url }}

Ce lien est valable pendant 7 jours. Passé ce délai, contactez l'administrateur pour en recevoir un nouveau.

À très bientôt,
L'équipe Les Retrouvailles
```

**`application_rejected`**
- Subject: `Mise à jour sur votre demande d'inscription`
- Body:
```
Bonjour {{ application.full_name }},

Après examen, l'admin n'a pas pu valider votre demande d'inscription pour la raison suivante :

{{ reason }}

Si vous pensez qu'il s'agit d'une erreur ou si vous souhaitez fournir des éléments supplémentaires, vous pouvez redéposer une demande dans 6 mois.

L'équipe Les Retrouvailles
```

**`parrain_invitation`**
- Subject: `Demande de cooptation pour {{ application.full_name }}`
- Body:
```
Bonjour {{ request.parrain.first_name }},

{{ application.full_name }} a déposé une demande d'inscription aux Retrouvailles et vous a nommé·e comme parrain·e.

Voulez-vous coopter cette personne ? Cliquez ci-dessous pour voir le dossier et répondre :

https://staging.villageretrouvailles.com/cooptation/{{ request.token }}/

Vous avez 14 jours pour répondre. Une relance automatique sera envoyée à J+7.

Merci pour votre temps,
L'équipe Les Retrouvailles
```

**`parrain_reminder`**
- Subject: `Rappel : cooptation de {{ application.full_name }} en attente`
- Body:
```
Bonjour {{ request.parrain.first_name }},

Nous n'avons pas encore reçu votre réponse pour la cooptation de {{ application.full_name }}. Il vous reste 7 jours pour répondre.

https://staging.villageretrouvailles.com/cooptation/{{ request.token }}/

Si vous ne pouvez pas vous prononcer, vous pouvez aussi cliquer "Refuser" — cela ne bloque pas la procédure ; l'admin réexaminera le dossier.

Merci,
L'équipe Les Retrouvailles
```

**`admin_new_application`**
- Subject: `[Admin] Nouvelle demande d'inscription`
- Body:
```
Bonjour,

Une nouvelle demande d'inscription a été soumise :

Nom : {{ application.full_name }}
Email : {{ application.email }}
Ville : {{ application.city }}, {{ application.country }}
Promotion : {{ application.years_attended|join:", " }}

Voir le dossier : https://staging.villageretrouvailles.com/admin/cooptation/adminapplication/{{ application.pk }}/change/

L'équipe Les Retrouvailles
```

Each `.html` file mirrors the `.txt` body, wrapped in the same minimal HTML shell as `application_received.html`.

- [ ] **Step 5: Configure Django to find emails templates**

In `alumni/settings/base.py`, the `TEMPLATES["DIRS"]` already includes `BASE_DIR / "templates"`. Django auto-discovers app templates dirs (`<app>/templates/`), so the `cooptation/templates/emails/cooptation/<name>.txt` paths resolve correctly via `render_to_string("emails/cooptation/<name>.txt", ...)`.

- [ ] **Step 6: Run the tests**

Run: `pytest cooptation/tests/test_email_templates.py -v`
Expected: 11 passed.

- [ ] **Step 7: Commit**

```bash
git add cooptation/emails.py cooptation/templates/emails/ cooptation/tests/test_email_templates.py
git commit -m "feat(cooptation): add 10 email templates and emails.py wrapper functions"
```

---

## Task 8: `services.py` — approve, reject, purge

**Files:**
- Modify: `cooptation/services.py`
- Create: `cooptation/tests/test_services.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/test_services.py`:

```python
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone


@pytest.fixture
def staff_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="admin@example.test",
        email="admin@example.test",
        password="x",
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_approve_creates_user_and_member(make_application, staff_user, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.services import approve_application
    from members.models import Member

    FakeResendBackend.sent_messages.clear()
    app = make_application(
        full_name="Idrissa Saidou",
        email="idrissa@example.test",
        city="Niamey",
    )
    user, member = approve_application(app, reviewed_by=staff_user)

    User = get_user_model()
    assert User.objects.filter(email="idrissa@example.test").exists()
    assert Member.objects.filter(user=user).exists()
    assert member.first_name == "Idrissa"
    assert member.last_name == "Saidou"
    assert member.status == "active"

    app.refresh_from_db()
    assert app.status == "approved"
    assert app.reviewed_by == staff_user

    # Email was sent with a password-set link
    assert len(FakeResendBackend.sent_messages) == 1
    assert "/accounts/password/reset/key/" in FakeResendBackend.sent_messages[0]["text"]


@pytest.mark.django_db
def test_approve_handles_full_name_with_one_token(make_application, staff_user):
    """A candidate who put only a single name in full_name still gets a Member;
    last_name becomes empty string rather than crashing."""
    from cooptation.services import approve_application

    app = make_application(full_name="Mononyme", email="m@example.test")
    user, member = approve_application(app, reviewed_by=staff_user)
    assert member.first_name == "Mononyme"
    assert member.last_name == ""


@pytest.mark.django_db
def test_approve_idempotent_on_email(make_application, staff_user):
    """Re-approving the same email (perhaps via a duplicate application)
    does not error and updates the existing Member."""
    from cooptation.services import approve_application

    app1 = make_application(full_name="Same Person", email="same@example.test")
    approve_application(app1, reviewed_by=staff_user)

    app2 = make_application(full_name="Same Person", email="same@example.test", city="Paris")
    user2, member2 = approve_application(app2, reviewed_by=staff_user)
    assert member2.city == "Paris"


@pytest.mark.django_db
def test_reject_sets_retention_until_six_months(make_application, staff_user, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.services import reject_application

    app = make_application(email="r@example.test")
    reject_application(app, reviewed_by=staff_user, note="Promotion non éligible")

    app.refresh_from_db()
    assert app.status == "rejected"
    assert app.review_note == "Promotion non éligible"
    assert app.rejected_at is not None
    assert app.retention_until is not None
    delta = app.retention_until - app.rejected_at
    assert timedelta(days=179) <= delta <= timedelta(days=181)  # ~6 months


@pytest.mark.django_db
def test_reject_emails_candidate_with_reason(make_application, staff_user, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.services import reject_application

    FakeResendBackend.sent_messages.clear()
    app = make_application(email="r@example.test")
    reject_application(app, reviewed_by=staff_user, note="Manque de précisions")
    assert "Manque de précisions" in FakeResendBackend.sent_messages[0]["text"]


@pytest.mark.django_db
def test_purge_clears_pii_and_sets_status(make_application):
    from cooptation.services import purge_application

    app = make_application(full_name="X Y", email="x@example.test", whatsapp="+227")
    app.source_ip = "1.2.3.4"
    app.save()
    purge_application(app)
    app.refresh_from_db()
    assert app.status == "purged"
    assert app.full_name == ""
    assert app.email == ""
    assert app.whatsapp == ""
    assert app.source_ip is None
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_services.py -v`
Expected: ImportError on `cooptation.services`.

- [ ] **Step 3: Implement `cooptation/services.py`**

```python
"""Application lifecycle services. Called from admin actions; never from a Django signal."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from members.models import Member

from . import emails
from .models import AdminApplication


@transaction.atomic
def approve_application(application: AdminApplication, *, reviewed_by) -> tuple:
    """Create User+Member, mark application approved, send password-set email.

    Idempotent on `application.email` — if a User already exists with that
    email, we update its associated Member rather than crashing.
    Returns (user, member).
    """
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        email=application.email,
        defaults={"username": application.email},
    )
    user.set_unusable_password()
    user.is_active = True
    user.save()

    parts = application.full_name.split(maxsplit=1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    member, _ = Member.objects.update_or_create(
        user=user,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "nickname": application.nickname,
            "years_attended": application.years_attended,
            "classes": application.classes,
            "city": application.city,
            "country": application.country,
            "profession": application.profession,
            "status": "active",
        },
    )

    application.status = "approved"
    application.reviewed_by = reviewed_by
    application.save()

    # Allauth-compatible password-set URL (same machinery as forgot-password).
    password_set_url = _build_password_set_url(user)
    emails.send_application_approved(application, password_set_url=password_set_url)

    return user, member


def _build_password_set_url(user) -> str:
    """Generate an Allauth-compatible password-reset URL for `user`.

    Allauth uses the same token machinery as Django's contrib.auth, so a
    Django default_token_generator token + uidb64 works. The URL pattern
    is `accounts/password/reset/key/<uidb64>-<token>/` per allauth.urls.
    """
    from django.conf import settings as django_settings

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    site_url = getattr(django_settings, "SITE_URL", "https://staging.villageretrouvailles.com")
    return f"{site_url}/accounts/password/reset/key/{uidb64}-{token}/"


@transaction.atomic
def reject_application(application: AdminApplication, *, reviewed_by, note: str) -> None:
    application.status = "rejected"
    application.review_note = note
    application.reviewed_by = reviewed_by
    application.rejected_at = timezone.now()
    application.retention_until = application.rejected_at + timedelta(days=180)
    application.save()
    emails.send_application_rejected(application, reason=note)


def purge_application(application: AdminApplication) -> None:
    application.purge()
```

- [ ] **Step 4: Run the tests**

Run: `pytest cooptation/tests/test_services.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add cooptation/services.py cooptation/tests/test_services.py
git commit -m "feat(cooptation): add approve/reject/purge services with Allauth password-set URL"
```

---

## Task 9: Public signup form and view

**Files:**
- Modify: `cooptation/forms.py`
- Modify: `cooptation/views.py`
- Modify: `cooptation/urls.py`
- Create: `cooptation/templates/cooptation/signup.html`
- Create: `cooptation/templates/cooptation/signup_success.html`
- Create: `cooptation/tests/test_signup_view.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/test_signup_view.py`:

```python
import pytest
from django.test import Client


@pytest.fixture
def active_member(db):
    """A pre-existing active Member to use as a parrain."""
    from django.contrib.auth import get_user_model

    from members.models import Member

    User = get_user_model()
    user = User.objects.create_user(
        username="parrain1@example.test",
        email="parrain1@example.test",
        password="x",
    )
    return Member.objects.create(
        user=user,
        first_name="Parrain",
        last_name="One",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e", "5e", "4e", "3e"],
        city="Niamey",
    )


@pytest.fixture
def second_active_member(db):
    from django.contrib.auth import get_user_model

    from members.models import Member

    User = get_user_model()
    user = User.objects.create_user(
        username="parrain2@example.test",
        email="parrain2@example.test",
        password="x",
    )
    return Member.objects.create(
        user=user,
        first_name="Parrain",
        last_name="Two",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e", "5e", "4e", "3e"],
        city="Cotonou",
    )


def _form_payload(parrain1, parrain2, **overrides):
    payload = {
        "full_name": "Idrissa Saidou",
        "nickname": "",
        "years_attended": "1980,1981,1982,1983",
        "classes": "6e,5e,4e,3e",
        "city": "Niamey",
        "country": "Niger",
        "profession": "",
        "email": "candidate@example.test",
        "whatsapp": "",
        "parrain1_email": parrain1.user.email,
        "parrain2_email": parrain2.user.email,
        "website_url": "",  # honeypot — must remain empty
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_signup_get_renders_form(client):
    response = client.get("/inscription/")
    assert response.status_code == 200
    assert b"full_name" in response.content
    assert b"parrain1_email" in response.content
    assert b"parrain2_email" in response.content


@pytest.mark.django_db
def test_signup_post_creates_application_and_two_requests(client, active_member, second_active_member, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.models import AdminApplication, CooptationRequest

    FakeResendBackend.sent_messages.clear()
    response = client.post("/inscription/", _form_payload(active_member, second_active_member))
    assert response.status_code == 302
    assert AdminApplication.objects.count() == 1
    assert CooptationRequest.objects.count() == 2


@pytest.mark.django_db
def test_signup_post_sends_4_emails_candidate_2parrains_admin(client, active_member, second_active_member, settings):
    """1 to candidate (received) + 1 to candidate (requests sent) + 2 to parrains
    + 1 to admins (only if any staff exist). Without staff users, total is 4."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    client.post("/inscription/", _form_payload(active_member, second_active_member))
    assert len(FakeResendBackend.sent_messages) == 4


@pytest.mark.django_db
def test_signup_rejects_self_cooptation(client, active_member, second_active_member):
    payload = _form_payload(active_member, second_active_member, email=active_member.user.email)
    response = client.post("/inscription/", payload)
    assert response.status_code == 200  # form re-rendered with errors
    assert b"vous parrainer" in response.content


@pytest.mark.django_db
def test_signup_rejects_duplicate_parrains(client, active_member):
    payload = _form_payload(active_member, active_member)
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"deux parrains diff" in response.content


@pytest.mark.django_db
def test_signup_rejects_unknown_parrain(client, active_member):
    payload = _form_payload(active_member, active_member, parrain2_email="ghost@example.test")
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"inconnu" in response.content


@pytest.mark.django_db
def test_signup_rejects_inactive_parrain(client, active_member, second_active_member):
    second_active_member.status = "suspended"
    second_active_member.save()
    payload = _form_payload(active_member, second_active_member)
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"inactif" in response.content or b"inconnu" in response.content


@pytest.mark.django_db
def test_signup_honeypot_silently_rejects(client, active_member, second_active_member):
    """Honeypot field non-empty → render success page but do not create application."""
    from cooptation.models import AdminApplication

    payload = _form_payload(active_member, second_active_member, website_url="http://spam")
    response = client.post("/inscription/", payload)
    assert response.status_code == 302
    assert AdminApplication.objects.count() == 0


@pytest.mark.django_db
def test_signup_records_source_ip(client, active_member, second_active_member):
    from cooptation.models import AdminApplication

    client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member),
        REMOTE_ADDR="203.0.113.5",
    )
    app = AdminApplication.objects.get()
    assert app.source_ip == "203.0.113.5"
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_signup_view.py -v`
Expected: 404 / unbound URL / form not implemented.

- [ ] **Step 3: Implement `cooptation/forms.py`**

```python
"""Forms for the cooptation app."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from members.models import GRADE_CHOICES, VALID_YEARS, Member


class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=160, label="Nom complet")
    nickname = forms.CharField(max_length=60, required=False, label="Surnom")
    years_attended = forms.CharField(
        max_length=80,
        label="Années au CEG 1 (séparées par virgule)",
        help_text="Ex. 1980,1981,1982,1983",
    )
    classes = forms.CharField(
        max_length=40,
        label="Classes (séparées par virgule)",
        help_text="Parmi : 6e, 5e, 4e, 3e",
    )
    city = forms.CharField(max_length=80, label="Ville actuelle")
    country = forms.CharField(max_length=80, initial="Niger", label="Pays")
    profession = forms.CharField(max_length=120, required=False, label="Profession")
    email = forms.EmailField(label="Votre email")
    whatsapp = forms.CharField(max_length=30, required=False, label="WhatsApp (optionnel)")
    parrain1_email = forms.EmailField(label="Email du parrain n°1")
    parrain2_email = forms.EmailField(label="Email du parrain n°2")
    website_url = forms.CharField(required=False, widget=forms.HiddenInput())  # honeypot

    def clean_years_attended(self):
        raw = self.cleaned_data["years_attended"]
        try:
            years = [int(p.strip()) for p in raw.split(",") if p.strip()]
        except ValueError:
            raise ValidationError("Format invalide (entiers séparés par virgules).")
        if any(y not in VALID_YEARS for y in years):
            raise ValidationError("Années hors plage 1980-1985.")
        return years

    def clean_classes(self):
        raw = self.cleaned_data["classes"]
        items = [p.strip() for p in raw.split(",") if p.strip()]
        valid = {key for key, _ in GRADE_CHOICES}
        if any(c not in valid for c in items):
            raise ValidationError("Classe inconnue. Utilisez 6e, 5e, 4e, ou 3e.")
        return items

    def clean(self):
        data = super().clean()
        email = data.get("email")
        p1 = data.get("parrain1_email")
        p2 = data.get("parrain2_email")
        if email and p1 and email == p1:
            raise ValidationError("Vous ne pouvez pas vous parrainer (parrain n°1).")
        if email and p2 and email == p2:
            raise ValidationError("Vous ne pouvez pas vous parrainer (parrain n°2).")
        if p1 and p2 and p1 == p2:
            raise ValidationError("Veuillez nommer deux parrains différents.")
        if p1 and not Member.objects.filter(user__email=p1, status="active").exists():
            raise ValidationError(f"Email parrain inconnu ou inactif : {p1}")
        if p2 and not Member.objects.filter(user__email=p2, status="active").exists():
            raise ValidationError(f"Email parrain inconnu ou inactif : {p2}")
        return data
```

- [ ] **Step 4: Implement `cooptation/views.py`**

```python
"""Public + token-gated views for the cooptation flow."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from members.models import Member

from . import emails
from .forms import SignupForm
from .models import AdminApplication, CooptationRequest


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            # Honeypot check — render success without creating anything.
            if form.cleaned_data.get("website_url"):
                return HttpResponseRedirect("/inscription/merci/")

            with transaction.atomic():
                app = AdminApplication.objects.create(
                    full_name=form.cleaned_data["full_name"],
                    nickname=form.cleaned_data["nickname"],
                    years_attended=form.cleaned_data["years_attended"],
                    classes=form.cleaned_data["classes"],
                    city=form.cleaned_data["city"],
                    country=form.cleaned_data["country"],
                    profession=form.cleaned_data["profession"],
                    email=form.cleaned_data["email"],
                    whatsapp=form.cleaned_data["whatsapp"],
                    source_ip=_client_ip(request),
                )
                p1 = Member.objects.get(user__email=form.cleaned_data["parrain1_email"], status="active")
                p2 = Member.objects.get(user__email=form.cleaned_data["parrain2_email"], status="active")
                expires = timezone.now() + timedelta(days=14)
                req1 = CooptationRequest.objects.create(application=app, parrain=p1, expires_at=expires)
                req2 = CooptationRequest.objects.create(application=app, parrain=p2, expires_at=expires)

            emails.send_application_received(app)
            emails.send_cooptation_requests_sent(
                app, parrain_emails=[p1.user.email, p2.user.email]
            )
            emails.send_parrain_invitation(req1)
            emails.send_parrain_invitation(req2)
            emails.send_admin_new_application(app)

            return HttpResponseRedirect("/inscription/merci/")
    else:
        form = SignupForm()
    return render(request, "cooptation/signup.html", {"form": form})


@require_http_methods(["GET"])
def signup_success_view(request):
    return render(request, "cooptation/signup_success.html")
```

- [ ] **Step 5: Wire URLs** in `cooptation/urls.py`:

```python
from django.urls import path

from . import views

app_name = "cooptation"

urlpatterns = [
    path("inscription/", views.signup_view, name="signup"),
    path("inscription/merci/", views.signup_success_view, name="signup_success"),
]
```

- [ ] **Step 6: Create `cooptation/templates/cooptation/signup.html`**

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Demande d'inscription" %}{% endblock %}
{% block content %}
<div class="mx-auto max-w-2xl">
    <header class="mb-8">
        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">{% trans "Rejoindre la communauté" %}</p>
        <h1 class="mt-2 font-display text-4xl font-semibold tracking-tight hero-rule">
            {% trans "Demande d'inscription" %}
        </h1>
        <p class="mt-4 text-base text-secondary leading-relaxed">
            {% trans "Réservée aux ancien·nes du CEG 1 Birni, promotions 1980 à 1985. Nommez deux parrains parmi les membres existants pour valider votre candidature." %}
        </p>
    </header>

    {% if form.non_field_errors %}
        <div role="alert" class="mb-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
            {{ form.non_field_errors }}
        </div>
    {% endif %}

    <form method="post" class="rounded-2xl bg-base-200 border border-secondary/15 p-6 shadow-sm space-y-4">
        {% csrf_token %}
        {% for field in form %}
            {% if field.name != "website_url" %}
                <label class="block">
                    <span class="block text-sm font-medium mb-1.5">{{ field.label }}</span>
                    {{ field }}
                    {% if field.help_text %}<p class="mt-1 text-xs text-secondary">{{ field.help_text }}</p>{% endif %}
                    {% if field.errors %}<p class="mt-1 text-sm text-red-700">{{ field.errors|join:" " }}</p>{% endif %}
                </label>
            {% else %}
                {{ field }}
            {% endif %}
        {% endfor %}
        <button type="submit" class="rounded-lg bg-tertiary px-6 py-2.5 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 min-h-tap">
            {% trans "Soumettre ma candidature" %}
        </button>
    </form>
</div>
{% endblock %}
```

Add field-level Tailwind via `forms.Form` widget attrs in the form's `__init__`:

```python
# Append to SignupForm.__init__:
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    INPUT_CLASS = "block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2 text-base shadow-sm focus:border-tertiary focus:outline-none focus:ring-2 focus:ring-tertiary/30"
    for name, field in self.fields.items():
        if name == "website_url":
            continue
        field.widget.attrs.setdefault("class", INPUT_CLASS)
```

- [ ] **Step 7: Create `cooptation/templates/cooptation/signup_success.html`**

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Demande reçue" %}{% endblock %}
{% block content %}
<div class="mx-auto max-w-2xl text-center">
    <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">{% trans "Merci !" %}</p>
    <h1 class="mt-2 font-display text-4xl font-semibold tracking-tight hero-rule mx-auto">
        {% trans "Votre demande a été reçue." %}
    </h1>
    <p class="mt-6 text-base text-secondary leading-relaxed">
        {% trans "Vous allez recevoir un email de confirmation. Vos parrains seront contactés dans la foulée. Vous serez notifié·e dès qu'ils auront répondu." %}
    </p>
</div>
{% endblock %}
```

- [ ] **Step 8: Run tests**

Run: `pytest cooptation/tests/test_signup_view.py -v`
Expected: 9 passed.

- [ ] **Step 9: Commit**

```bash
git add cooptation/forms.py cooptation/views.py cooptation/urls.py cooptation/templates/ cooptation/tests/test_signup_view.py
git commit -m "feat(cooptation): add public signup form, view, and success page"
```

---

## Task 10: Parrain vouch view (token + identity check + 410 pages)

**Files:**
- Modify: `cooptation/forms.py`
- Modify: `cooptation/views.py`
- Modify: `cooptation/urls.py`
- Create: `cooptation/templates/cooptation/parrain_vouch.html`
- Create: `cooptation/templates/cooptation/parrain_vouch_done.html`
- Create: `cooptation/templates/cooptation/parrain_vouch_expired.html`
- Create: `cooptation/tests/test_parrain_vouch_view.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/test_parrain_vouch_view.py`:

```python
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def parrain_client(make_cooptation_request):
    """A logged-in client whose user IS the parrain on the request."""
    req = make_cooptation_request()
    parrain = req.parrain
    user = parrain.user
    user.set_password("x")
    user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    c.request = req
    return c


@pytest.mark.django_db
def test_vouch_get_renders_form_for_correct_parrain(parrain_client):
    response = parrain_client.get(f"/cooptation/{parrain_client.request.token}/")
    assert response.status_code == 200
    assert parrain_client.request.application.full_name.encode() in response.content


@pytest.mark.django_db
def test_vouch_unauthenticated_redirects_to_login(make_cooptation_request):
    req = make_cooptation_request()
    response = Client().get(f"/cooptation/{req.token}/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_vouch_403_for_wrong_user(make_cooptation_request, make_member, make_user):
    """A logged-in member who isn't the named parrain gets 403."""
    req = make_cooptation_request()
    other_user = make_user(password="other")
    make_member(user=other_user)
    ConsentRecord.objects.create(
        member=other_user.member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    c = Client()
    c.login(username=other_user.username, password="other")
    response = c.get(f"/cooptation/{req.token}/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_vouch_410_when_expired(parrain_client):
    parrain_client.request.expires_at = timezone.now() - timedelta(days=1)
    parrain_client.request.save()
    response = parrain_client.get(f"/cooptation/{parrain_client.request.token}/")
    assert response.status_code == 410
    assert b"expir" in response.content.lower()


@pytest.mark.django_db
def test_vouch_410_when_already_responded(parrain_client):
    parrain_client.request.response = "accepted"
    parrain_client.request.responded_at = timezone.now()
    parrain_client.request.save()
    response = parrain_client.get(f"/cooptation/{parrain_client.request.token}/")
    assert response.status_code == 410
    assert b"d" in response.content  # any French response


@pytest.mark.django_db
def test_vouch_post_accept_transitions_request(parrain_client, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    response = parrain_client.post(
        f"/cooptation/{parrain_client.request.token}/",
        {"response": "accepted", "comment": "Je le connais bien."},
    )
    assert response.status_code == 302
    parrain_client.request.refresh_from_db()
    assert parrain_client.request.response == "accepted"
    assert parrain_client.request.responded_at is not None
    assert parrain_client.request.comment == "Je le connais bien."
    # Email to candidate
    assert any("accepted" in (m.get("subject") or "").lower() or "coopt" in (m.get("subject") or "").lower()
               for m in FakeResendBackend.sent_messages)


@pytest.mark.django_db
def test_vouch_eager_transition_to_awaiting_admin_when_all_responded(make_cooptation_request, settings):
    """Both parrains accept → application transitions to awaiting_admin
    immediately in the second view's POST, NOT waiting for cron."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication

    req1 = make_cooptation_request()
    app = req1.application
    req2 = make_cooptation_request(application=app)

    # Bring both parrains in as logged-in
    for req in [req1, req2]:
        req.parrain.user.set_password("x")
        req.parrain.user.save()
        ConsentRecord.objects.create(
            member=req.parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
        )

    for req in [req1, req2]:
        c = Client()
        c.login(username=req.parrain.user.username, password="x")
        c.post(f"/cooptation/{req.token}/", {"response": "accepted", "comment": ""})

    app.refresh_from_db()
    assert app.status == "awaiting_admin"
    assert app.cooptation_outcome == "all_accepted"
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_parrain_vouch_view.py -v`
Expected: ~404 because URL not registered.

- [ ] **Step 3: Add `ParrainVouchForm` to `cooptation/forms.py`**

Append:

```python
class ParrainVouchForm(forms.Form):
    response = forms.ChoiceField(
        choices=[("accepted", "J'accepte de coopter"), ("refused", "Je refuse")],
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Commentaire (optionnel)",
    )
```

- [ ] **Step 4: Add the view to `cooptation/views.py`**

```python
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404


def _resolve_outcome(application: AdminApplication) -> str:
    """Compute cooptation_outcome from current responses."""
    requests = list(application.cooptation_requests.all())
    responses = [r.response for r in requests]
    if any(r == "pending" for r in responses):
        return "pending"
    accepted = sum(1 for r in responses if r == "accepted")
    refused = sum(1 for r in responses if r == "refused")
    if accepted == len(responses):
        return "all_accepted"
    if refused == len(responses):
        return "all_refused"
    return "mixed"


@login_required
@require_http_methods(["GET", "POST"])
def parrain_vouch_view(request, token: str):
    cooptation_request = get_object_or_404(CooptationRequest, token=token)

    member = getattr(request.user, "member", None)
    if member is None or member.pk != cooptation_request.parrain_id:
        raise PermissionDenied("Cette invitation ne vous est pas adressée.")

    if cooptation_request.response != "pending":
        return render(
            request,
            "cooptation/parrain_vouch_done.html",
            {"request_obj": cooptation_request},
            status=410,
        )

    if cooptation_request.expires_at <= timezone.now():
        return render(
            request,
            "cooptation/parrain_vouch_expired.html",
            {"request_obj": cooptation_request},
            status=410,
        )

    if request.method == "POST":
        form = ParrainVouchForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                cooptation_request.response = form.cleaned_data["response"]
                cooptation_request.comment = form.cleaned_data["comment"]
                cooptation_request.responded_at = timezone.now()
                cooptation_request.save()

                # Notify the candidate
                if cooptation_request.response == "accepted":
                    emails.send_cooptation_accepted(cooptation_request)
                else:
                    emails.send_cooptation_refused(cooptation_request)

                # Eager outcome: if all parrains have responded, transition immediately.
                outcome = _resolve_outcome(cooptation_request.application)
                if outcome != "pending":
                    app = cooptation_request.application
                    app.cooptation_outcome = outcome
                    app.status = "awaiting_admin"
                    app.save()

            return HttpResponseRedirect(f"/cooptation/{token}/")
    else:
        form = ParrainVouchForm()

    return render(
        request,
        "cooptation/parrain_vouch.html",
        {"form": form, "request_obj": cooptation_request, "application": cooptation_request.application},
    )
```

- [ ] **Step 5: Wire URL** — append to `cooptation/urls.py`:

```python
path("cooptation/<str:token>/", views.parrain_vouch_view, name="parrain_vouch"),
```

- [ ] **Step 6: Create the three templates**

`cooptation/templates/cooptation/parrain_vouch.html`:

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Cooptation" %}{% endblock %}
{% block content %}
<div class="mx-auto max-w-2xl">
    <header class="mb-6">
        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">{% trans "Demande de cooptation" %}</p>
        <h1 class="mt-2 font-display text-3xl font-semibold tracking-tight">{{ application.full_name }}</h1>
        <p class="mt-2 text-sm text-secondary">{{ application.years_attended|join:", " }} · {{ application.city }}, {{ application.country }}</p>
        {% if application.profession %}<p class="text-sm">{{ application.profession }}</p>{% endif %}
    </header>
    <form method="post" class="rounded-2xl bg-base-200 border border-secondary/15 p-6 shadow-sm space-y-4">
        {% csrf_token %}
        <fieldset class="space-y-2">
            <legend class="text-sm font-medium uppercase tracking-wider text-secondary">{% trans "Votre réponse" %}</legend>
            {% for radio in form.response %}
                <label class="flex items-center gap-2.5">{{ radio.tag }} {{ radio.choice_label }}</label>
            {% endfor %}
        </fieldset>
        <label class="block">
            <span class="block text-sm font-medium mb-1.5">{% trans "Commentaire (optionnel)" %}</span>
            {{ form.comment }}
        </label>
        <button type="submit" class="rounded-lg bg-tertiary px-6 py-2.5 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 min-h-tap">{% trans "Envoyer ma réponse" %}</button>
    </form>
</div>
{% endblock %}
```

`cooptation/templates/cooptation/parrain_vouch_done.html`:

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Cooptation déjà répondue" %}{% endblock %}
{% block content %}
<div class="mx-auto max-w-md text-center py-16">
    <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">{% trans "Cooptation" %}</p>
    <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight">{% trans "Vous avez déjà répondu." %}</h1>
    <p class="mt-4 text-secondary">
        {% blocktrans with date=request_obj.responded_at|date:"d F Y" %}
        Réponse enregistrée le {{ date }}.
        {% endblocktrans %}
    </p>
</div>
{% endblock %}
```

`cooptation/templates/cooptation/parrain_vouch_expired.html`:

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Lien expiré" %}{% endblock %}
{% block content %}
<div class="mx-auto max-w-md text-center py-16">
    <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">{% trans "Cooptation" %}</p>
    <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight">{% trans "Cette demande a expiré." %}</h1>
    <p class="mt-4 text-secondary">
        {% blocktrans with date=request_obj.expires_at|date:"d F Y" %}
        Le délai de 14 jours a été atteint le {{ date }}. Le candidat sera contacté par d'autres voies.
        {% endblocktrans %}
    </p>
</div>
{% endblock %}
```

- [ ] **Step 7: Run tests**

Run: `pytest cooptation/tests/test_parrain_vouch_view.py -v`
Expected: 7 passed.

- [ ] **Step 8: Commit**

```bash
git add cooptation/forms.py cooptation/views.py cooptation/urls.py cooptation/templates/cooptation/ cooptation/tests/test_parrain_vouch_view.py
git commit -m "feat(cooptation): add parrain_vouch_view with identity check, 410 pages, eager transition"
```

---

## Task 11: Questionnaire view with auto-grading

**Files:**
- Modify: `cooptation/forms.py`
- Modify: `cooptation/views.py`
- Modify: `cooptation/urls.py`
- Create: `cooptation/templates/cooptation/questionnaire.html`
- Create: `cooptation/templates/cooptation/questionnaire_done.html`
- Create: `cooptation/tests/test_questionnaire_view.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/test_questionnaire_view.py`:

```python
import pytest
from django.test import Client


@pytest.fixture
def expired_application_with_token(make_application):
    """An application in cooptation_pending whose cooptation expired and that
    received a questionnaire token (stored in our minimal model as the
    application's pk-derived token — to keep model simple, we'll pass through
    the application token field added in this task)."""
    from cooptation.models import AdminApplication, KnowledgeQuestion

    app = make_application(email="c@example.test", status="cooptation_pending")
    app.cooptation_outcome = "expired"
    # Generate a questionnaire token on the application — see implementation step.
    app.questionnaire_token = "abc123"
    app.save()
    KnowledgeQuestion.objects.create(position=1, kind="closed", text="Q1", answer_keys=["alpha", "beta"])
    KnowledgeQuestion.objects.create(position=2, kind="closed", text="Q2", answer_keys=["gamma"])
    KnowledgeQuestion.objects.create(position=3, kind="open", text="Souvenir")
    return app


@pytest.mark.django_db
def test_questionnaire_get_renders_three_questions(expired_application_with_token):
    response = Client().get("/questionnaire/abc123/")
    assert response.status_code == 200
    assert response.content.count(b"<textarea") + response.content.count(b'type="text"') >= 3


@pytest.mark.django_db
def test_questionnaire_410_for_unknown_token():
    response = Client().get("/questionnaire/nope/")
    assert response.status_code == 410


@pytest.mark.django_db
def test_questionnaire_post_grades_closed_correctly(expired_application_with_token):
    """A correct closed answer (any answer_key as substring, accent-insensitive)
    is auto_graded True; a wrong one is False; open is None."""
    from cooptation.models import QuestionnaireResponse

    response = Client().post(
        "/questionnaire/abc123/",
        {
            "q1": "j'ai connu Mr Alpha",  # contains 'alpha' — match
            "q2": "Je sais pas",            # no match
            "q3": "C'était il y a 40 ans...",
        },
    )
    assert response.status_code == 302
    by_position = {r.question.position: r for r in QuestionnaireResponse.objects.all()}
    assert by_position[1].auto_grade is True
    assert by_position[2].auto_grade is False
    assert by_position[3].auto_grade is None


@pytest.mark.django_db
def test_questionnaire_accent_insensitive_match():
    """answer_keys=['Idrïssa'] matches a candidate answer 'IDRISSA'."""
    from cooptation.models import AdminApplication, KnowledgeQuestion, QuestionnaireResponse

    app = AdminApplication.objects.create(
        full_name="X", email="x@example.test", status="cooptation_pending",
        cooptation_outcome="expired",
    )
    app.questionnaire_token = "tok"
    app.save()
    KnowledgeQuestion.objects.create(position=1, kind="closed", text="Q", answer_keys=["Idrïssa"])

    Client().post("/questionnaire/tok/", {"q1": "le prof IDRISSA"})
    r = QuestionnaireResponse.objects.get(question__position=1)
    assert r.auto_grade is True


@pytest.mark.django_db
def test_questionnaire_post_transitions_application_to_awaiting_admin(expired_application_with_token):
    Client().post(
        "/questionnaire/abc123/",
        {"q1": "alpha", "q2": "gamma", "q3": "souvenir"},
    )
    expired_application_with_token.refresh_from_db()
    assert expired_application_with_token.status == "awaiting_admin"


@pytest.mark.django_db
def test_questionnaire_410_after_already_submitted(expired_application_with_token):
    Client().post(
        "/questionnaire/abc123/",
        {"q1": "alpha", "q2": "gamma", "q3": "souvenir"},
    )
    response = Client().get("/questionnaire/abc123/")
    assert response.status_code == 410
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_questionnaire_view.py -v`
Expected: ImportError on `questionnaire_token` or 404.

- [ ] **Step 3: Add `questionnaire_token` field to `AdminApplication`**

In `cooptation/models.py`, add to the model:

```python
questionnaire_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
```

Generate migration:
```bash
python manage.py makemigrations cooptation
python manage.py migrate cooptation
```

- [ ] **Step 4: Implement `cooptation/views.py::questionnaire_view`**

Append:

```python
import unicodedata


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _grade_closed(answer: str, keys: list[str]) -> bool:
    haystack = _strip_accents(answer.lower())
    return any(_strip_accents(key.lower()) in haystack for key in keys if key)


@require_http_methods(["GET", "POST"])
def questionnaire_view(request, token: str):
    try:
        application = AdminApplication.objects.get(questionnaire_token=token)
    except AdminApplication.DoesNotExist:
        return render(request, "cooptation/questionnaire_done.html", {"unknown": True}, status=410)

    if application.questionnaire_responses.exists():
        return render(request, "cooptation/questionnaire_done.html", {"unknown": False}, status=410)

    from .models import KnowledgeQuestion, QuestionnaireResponse

    questions = list(KnowledgeQuestion.objects.filter(is_active=True))

    if request.method == "POST":
        with transaction.atomic():
            for q in questions:
                answer = (request.POST.get(f"q{q.position}") or "").strip()
                grade = _grade_closed(answer, q.answer_keys) if q.kind == "closed" else None
                QuestionnaireResponse.objects.create(
                    application=application, question=q, candidate_answer=answer, auto_grade=grade
                )
            application.status = "awaiting_admin"
            application.save()
        return HttpResponseRedirect(f"/questionnaire/{token}/")

    return render(request, "cooptation/questionnaire.html", {"questions": questions, "application": application})
```

- [ ] **Step 5: Wire URL** in `cooptation/urls.py`:

```python
path("questionnaire/<str:token>/", views.questionnaire_view, name="questionnaire"),
```

- [ ] **Step 6: Create templates**

`cooptation/templates/cooptation/questionnaire.html`:

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Questionnaire de connaissance" %}{% endblock %}
{% block content %}
<div class="mx-auto max-w-2xl">
    <header class="mb-6">
        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">{% trans "Vérification" %}</p>
        <h1 class="mt-2 font-display text-3xl font-semibold tracking-tight hero-rule">
            {% trans "Questionnaire de connaissance" %}
        </h1>
        <p class="mt-4 text-secondary">{% trans "Cooptation expirée — quelques questions pour valider votre identité." %}</p>
    </header>
    <form method="post" class="rounded-2xl bg-base-200 border border-secondary/15 p-6 shadow-sm space-y-5">
        {% csrf_token %}
        {% for q in questions %}
            <label class="block">
                <span class="block text-sm font-medium mb-1.5">{{ q.position }}. {{ q.text }}</span>
                {% if q.kind == "closed" %}
                    <input type="text" name="q{{ q.position }}" required class="block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2 text-base shadow-sm focus:border-tertiary focus:outline-none focus:ring-2 focus:ring-tertiary/30">
                {% else %}
                    <textarea name="q{{ q.position }}" rows="4" required class="block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2 text-base shadow-sm focus:border-tertiary focus:outline-none focus:ring-2 focus:ring-tertiary/30"></textarea>
                {% endif %}
            </label>
        {% endfor %}
        <button type="submit" class="rounded-lg bg-tertiary px-6 py-2.5 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 min-h-tap">{% trans "Envoyer mes réponses" %}</button>
    </form>
</div>
{% endblock %}
```

`cooptation/templates/cooptation/questionnaire_done.html`:

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Questionnaire envoyé" %}{% endblock %}
{% block content %}
<div class="mx-auto max-w-md text-center py-16">
    <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">{% trans "Questionnaire" %}</p>
    {% if unknown %}
        <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight">{% trans "Lien invalide ou expiré." %}</h1>
    {% else %}
        <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight">{% trans "Vos réponses ont déjà été soumises." %}</h1>
        <p class="mt-4 text-secondary">{% trans "L'admin examinera votre dossier prochainement." %}</p>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 7: Run tests**

Run: `pytest cooptation/tests/test_questionnaire_view.py -v`
Expected: 6 passed.

- [ ] **Step 8: Commit**

```bash
git add cooptation/models.py cooptation/migrations/000*_*.py cooptation/views.py cooptation/urls.py cooptation/templates/cooptation/questionnaire*.html cooptation/tests/test_questionnaire_view.py
git commit -m "feat(cooptation): add questionnaire view with accent-insensitive auto-grading"
```

---

## Task 12: Admin moderation UI

**Files:**
- Modify: `cooptation/admin.py`
- Create: `cooptation/tests/test_admin_actions.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/test_admin_actions.py`:

```python
import pytest
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def superuser(db):
    return get_user_model().objects.create_superuser(
        username="root@example.test",
        email="root@example.test",
        password="x",
    )


@pytest.mark.django_db
def test_application_admin_registered():
    from cooptation.models import AdminApplication, CooptationRequest, KnowledgeQuestion, QuestionnaireResponse

    assert site.is_registered(AdminApplication)
    assert site.is_registered(CooptationRequest)
    assert site.is_registered(KnowledgeQuestion)
    assert site.is_registered(QuestionnaireResponse)


@pytest.mark.django_db
def test_admin_approve_action_creates_member(superuser, make_application, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication
    from members.models import Member

    app = make_application(full_name="Idrissa Saidou", email="i@example.test")
    admin = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser

    admin.approve_action(FakeReq(), AdminApplication.objects.filter(pk=app.pk))
    app.refresh_from_db()
    assert app.status == "approved"
    assert Member.objects.filter(user__email="i@example.test").exists()


@pytest.mark.django_db
def test_admin_reject_action_sets_retention(superuser, make_application, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication

    app = make_application(email="r@example.test")
    admin = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser
        POST = {"reason": "Promotion non éligible"}

    admin.reject_action(FakeReq(), AdminApplication.objects.filter(pk=app.pk))
    app.refresh_from_db()
    assert app.status == "rejected"
    assert app.retention_until is not None


@pytest.mark.django_db
def test_admin_resend_password_link_action(superuser, make_application, settings):
    """After approval, admin can re-send the password-set email."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication
    from cooptation.services import approve_application

    app = make_application(email="i@example.test")
    approve_application(app, reviewed_by=superuser)
    FakeResendBackend.sent_messages.clear()

    admin = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser

    admin.resend_password_link_action(FakeReq(), AdminApplication.objects.filter(pk=app.pk))
    assert len(FakeResendBackend.sent_messages) == 1
    assert "/accounts/password/reset/key/" in FakeResendBackend.sent_messages[0]["text"]
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_admin_actions.py -v`
Expected: cooptation admin not registered.

- [ ] **Step 3: Implement `cooptation/admin.py`**

```python
from django.contrib import admin, messages
from django.utils.html import format_html

from . import services
from .emails import send_application_approved
from .models import AdminApplication, CooptationRequest, KnowledgeQuestion, QuestionnaireResponse


class CooptationRequestInline(admin.TabularInline):
    model = CooptationRequest
    extra = 0
    readonly_fields = ("parrain", "response", "responded_at", "comment", "expires_at", "reminder_sent_at")
    can_delete = False


class QuestionnaireResponseInline(admin.TabularInline):
    model = QuestionnaireResponse
    extra = 0
    readonly_fields = ("question", "candidate_answer", "auto_grade", "submitted_at")
    can_delete = False


@admin.register(AdminApplication)
class AdminApplicationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "city", "status", "cooptation_outcome", "submitted_at", "ip_badge")
    list_filter = ("status", "cooptation_outcome", "country")
    search_fields = ("full_name", "email", "nickname")
    readonly_fields = (
        "submitted_at", "reviewed_by", "rejected_at", "retention_until", "purged_at",
        "source_ip", "questionnaire_token",
    )
    inlines = [CooptationRequestInline, QuestionnaireResponseInline]
    actions = ["approve_action", "reject_action", "resend_password_link_action"]

    @admin.display(description="IP")
    def ip_badge(self, obj):
        if not obj.source_ip:
            return ""
        # Count submissions from same IP in last 24h
        from datetime import timedelta
        from django.utils import timezone
        recent = AdminApplication.objects.filter(
            source_ip=obj.source_ip,
            submitted_at__gte=timezone.now() - timedelta(hours=24),
        ).count()
        if recent >= 3:
            return format_html('<span title="{} demandes en 24h">🚩 {}</span>', recent, obj.source_ip)
        return obj.source_ip

    @admin.action(description="Approuver les candidatures sélectionnées")
    def approve_action(self, request, queryset):
        for app in queryset:
            services.approve_application(app, reviewed_by=request.user)
        self.message_user(request, f"{queryset.count()} candidature(s) approuvée(s).", messages.SUCCESS)

    @admin.action(description="Rejeter les candidatures sélectionnées")
    def reject_action(self, request, queryset):
        reason = (request.POST.get("reason") or "Demande non éligible").strip()
        for app in queryset:
            services.reject_application(app, reviewed_by=request.user, note=reason)
        self.message_user(request, f"{queryset.count()} candidature(s) rejetée(s).", messages.WARNING)

    @admin.action(description="Renvoyer le lien de mot de passe (candidats déjà approuvés)")
    def resend_password_link_action(self, request, queryset):
        sent = 0
        for app in queryset.filter(status="approved"):
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(email=app.email).first()
            if not user:
                continue
            from .services import _build_password_set_url
            send_application_approved(app, password_set_url=_build_password_set_url(user))
            sent += 1
        self.message_user(request, f"{sent} email(s) renvoyé(s).", messages.SUCCESS)


@admin.register(CooptationRequest)
class CooptationRequestAdmin(admin.ModelAdmin):
    list_display = ("application", "parrain", "response", "responded_at", "expires_at")
    list_filter = ("response",)
    readonly_fields = ("application", "parrain", "token", "expires_at", "reminder_sent_at",
                       "response", "responded_at", "comment")


@admin.register(KnowledgeQuestion)
class KnowledgeQuestionAdmin(admin.ModelAdmin):
    list_display = ("position", "kind", "text", "is_active")
    list_filter = ("kind", "is_active")


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(admin.ModelAdmin):
    list_display = ("application", "question", "auto_grade", "submitted_at")
    readonly_fields = ("application", "question", "candidate_answer", "auto_grade", "submitted_at")
    list_filter = ("auto_grade",)
```

- [ ] **Step 4: Run tests**

Run: `pytest cooptation/tests/test_admin_actions.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add cooptation/admin.py cooptation/tests/test_admin_actions.py
git commit -m "feat(cooptation): admin moderation UI with approve/reject/resend actions"
```

---

## Task 13: `process_cooptation_deadlines` cron command

**Files:**
- Create: `cooptation/management/commands/process_cooptation_deadlines.py`
- Create: `cooptation/tests/test_process_deadlines.py`

- [ ] **Step 1: Write the failing tests**

`cooptation/tests/test_process_deadlines.py`:

```python
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time


@pytest.mark.django_db
def test_j7_reminder_sends_once(make_cooptation_request, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    req = make_cooptation_request(
        expires_at=timezone.now() + timedelta(days=7) - timedelta(hours=1),  # ~6.96 days out
    )
    FakeResendBackend.sent_messages.clear()

    call_command("process_cooptation_deadlines")
    req.refresh_from_db()
    assert req.reminder_sent_at is not None
    assert len(FakeResendBackend.sent_messages) == 1

    # Re-run is idempotent — no second reminder
    FakeResendBackend.sent_messages.clear()
    call_command("process_cooptation_deadlines")
    assert len(FakeResendBackend.sent_messages) == 0


@pytest.mark.django_db
def test_j14_expiry_transitions_application(make_cooptation_request, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication

    req = make_cooptation_request(expires_at=timezone.now() - timedelta(hours=1))
    app = req.application

    call_command("process_cooptation_deadlines")
    app.refresh_from_db()
    assert app.cooptation_outcome == "expired"
    assert app.questionnaire_token  # auto-generated for the fallback


@pytest.mark.django_db
def test_retention_purge_runs_after_six_months(make_application, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from datetime import timedelta as td

    app = make_application(
        full_name="Should Be Purged",
        email="purge@example.test",
        status="rejected",
    )
    app.rejected_at = timezone.now() - td(days=200)
    app.retention_until = timezone.now() - td(days=20)
    app.save()

    call_command("process_cooptation_deadlines")
    app.refresh_from_db()
    assert app.status == "purged"
    assert app.full_name == ""
    assert app.email == ""


@pytest.mark.django_db
def test_email_pacing_sleeps_between_sends(make_cooptation_request, settings, monkeypatch):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    sleeps = []
    import time as time_mod

    monkeypatch.setattr(time_mod, "sleep", lambda s: sleeps.append(s))

    # Two reminders firing in one run
    req1 = make_cooptation_request(expires_at=timezone.now() + timedelta(days=7) - timedelta(hours=1))
    req2 = make_cooptation_request(expires_at=timezone.now() + timedelta(days=7) - timedelta(hours=1))

    call_command("process_cooptation_deadlines")
    # At least 1 sleep call between sends (could be more if expiry path also fires)
    assert any(s == 0.5 for s in sleeps)
```

- [ ] **Step 2: Confirm failure**

Run: `pytest cooptation/tests/test_process_deadlines.py -v`
Expected: `Unknown command: 'process_cooptation_deadlines'`.

- [ ] **Step 3: Implement the command**

`cooptation/management/commands/process_cooptation_deadlines.py`:

```python
"""Daily idempotent cron: J+7 reminders, J+14 expiry transitions, 6-month retention purge.

Run via Railway cron service; sharing the app's image and env."""

from __future__ import annotations

import secrets
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from cooptation import emails, services
from cooptation.models import AdminApplication, CooptationRequest


PACING_SECONDS = 0.5


class Command(BaseCommand):
    help = "Daily processor for cooptation deadlines (J+7, J+14, retention purge)."

    def handle(self, *args, **opts):
        now = timezone.now()
        sent_reminders = self._send_j7_reminders(now)
        expired_apps = self._expire_j14(now)
        purged_apps = self._purge_old_rejections(now)
        self.stdout.write(self.style.SUCCESS(
            f"Done. Reminders: {sent_reminders}, expired: {expired_apps}, purged: {purged_apps}."
        ))

    def _send_j7_reminders(self, now) -> int:
        """For each pending CooptationRequest where now is within 7 days of expires_at
        and no reminder has been sent, send one and stamp reminder_sent_at."""
        threshold_low = now
        threshold_high = now + timedelta(days=7)
        qs = CooptationRequest.objects.filter(
            response="pending",
            reminder_sent_at__isnull=True,
            expires_at__gt=threshold_low,
            expires_at__lte=threshold_high,
        )
        count = 0
        for req in qs:
            emails.send_parrain_reminder(req)
            req.reminder_sent_at = now
            req.save()
            count += 1
            time.sleep(PACING_SECONDS)
        return count

    def _expire_j14(self, now) -> int:
        """For each AdminApplication in cooptation_pending whose all requests are
        either non-pending or past expires_at, transition to awaiting_admin (or
        questionnaire_pending via questionnaire_token if any timed out)."""
        apps = AdminApplication.objects.filter(status="cooptation_pending").distinct()
        count = 0
        for app in apps:
            requests = list(app.cooptation_requests.all())
            still_open = [r for r in requests if r.response == "pending" and r.expires_at > now]
            if still_open:
                continue
            timed_out = [r for r in requests if r.response == "pending" and r.expires_at <= now]
            if timed_out:
                # At least one expired without a response — fallback to questionnaire.
                app.cooptation_outcome = "expired"
                if not app.questionnaire_token:
                    app.questionnaire_token = secrets.token_urlsafe(32)
                app.save()
                site_url = getattr(settings, "SITE_URL", "https://staging.villageretrouvailles.com")
                qurl = f"{site_url}/questionnaire/{app.questionnaire_token}/"
                emails.send_cooptation_expired(app, questionnaire_url=qurl)
                count += 1
                time.sleep(PACING_SECONDS)
            else:
                # All responded — derive outcome and move to awaiting_admin
                app.cooptation_outcome = self._derive_outcome(requests)
                app.status = "awaiting_admin"
                app.save()
                count += 1
        return count

    @staticmethod
    def _derive_outcome(requests) -> str:
        responses = [r.response for r in requests]
        if all(r == "accepted" for r in responses):
            return "all_accepted"
        if all(r == "refused" for r in responses):
            return "all_refused"
        return "mixed"

    def _purge_old_rejections(self, now) -> int:
        qs = AdminApplication.objects.filter(status="rejected", retention_until__lte=now)
        count = 0
        for app in qs:
            services.purge_application(app)
            count += 1
        return count
```

- [ ] **Step 4: Run tests**

Run: `pytest cooptation/tests/test_process_deadlines.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add cooptation/management/commands/process_cooptation_deadlines.py cooptation/tests/test_process_deadlines.py
git commit -m "feat(cooptation): add process_cooptation_deadlines cron command (J+7/J+14/purge)"
```

---

## Task 14: a11y tests for public forms + end-to-end happy path

**Files:**
- Create: `cooptation/tests/test_a11y.py`
- Create: `cooptation/tests/test_e2e_happy_path.py`

- [ ] **Step 1: Write the tests**

`cooptation/tests/test_a11y.py`:

```python
import pytest
from bs4 import BeautifulSoup
from django.test import Client


@pytest.mark.django_db
def test_signup_form_inputs_have_labels():
    response = Client().get("/inscription/")
    soup = BeautifulSoup(response.content, "html.parser")
    # Each form input should be wrapped in a <label> (which the template does).
    inputs = soup.select("form input[type='text'], form input[type='email']")
    for inp in inputs:
        assert inp.find_parent("label") is not None, f"Input {inp.get('name')} has no parent label"


@pytest.mark.django_db
def test_signup_includes_noindex_implicitly():
    """Public form pages don't need to be noindex (the home page IS the
    public surface eventually) — but for now, until P4, we noindex."""
    response = Client().get("/inscription/")
    # Template extends base.html which has block robots = noindex by default.
    assert b'name="robots"' in response.content
```

`cooptation/tests/test_e2e_happy_path.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord, Member


@pytest.fixture
def two_active_parrains(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    parrains = []
    for i in (1, 2):
        u = User.objects.create_user(
            username=f"parrain{i}@example.test",
            email=f"parrain{i}@example.test",
            password="x",
        )
        m = Member.objects.create(
            user=u,
            first_name=f"Parrain{i}",
            last_name="X",
            years_attended=[1980, 1981, 1982, 1983],
            classes=["6e", "5e", "4e", "3e"],
            city="Niamey",
        )
        ConsentRecord.objects.create(
            member=m, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
        )
        parrains.append((u, m))
    return parrains


@pytest.mark.django_db
def test_full_happy_path(two_active_parrains, settings):
    """Visitor signs up → both parrains accept → admin approves → user can set password."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.models import AdminApplication, CooptationRequest
    from cooptation.services import approve_application
    from django.contrib.auth import get_user_model

    p1_user, p1_member = two_active_parrains[0]
    p2_user, p2_member = two_active_parrains[1]

    # 1. Visitor submits inscription
    FakeResendBackend.sent_messages.clear()
    response = Client().post(
        "/inscription/",
        {
            "full_name": "Idrissa Saidou",
            "nickname": "",
            "years_attended": "1980,1981,1982,1983",
            "classes": "6e,5e,4e,3e",
            "city": "Niamey",
            "country": "Niger",
            "profession": "Enseignant",
            "email": "idrissa@example.test",
            "whatsapp": "",
            "parrain1_email": "parrain1@example.test",
            "parrain2_email": "parrain2@example.test",
            "website_url": "",
        },
    )
    assert response.status_code == 302
    app = AdminApplication.objects.get(email="idrissa@example.test")
    assert app.status == "cooptation_pending"
    assert CooptationRequest.objects.filter(application=app).count() == 2

    # 2. Both parrains accept via their tokens
    for parrain_user, parrain_member in two_active_parrains:
        req = CooptationRequest.objects.get(application=app, parrain=parrain_member)
        c = Client()
        c.login(username=parrain_user.username, password="x")
        c.post(f"/cooptation/{req.token}/", {"response": "accepted", "comment": ""})

    # 3. Eager transition fired → application is awaiting_admin
    app.refresh_from_db()
    assert app.status == "awaiting_admin"
    assert app.cooptation_outcome == "all_accepted"

    # 4. Admin approves via service (admin action wraps this)
    User = get_user_model()
    admin = User.objects.create_superuser(
        username="root", email="root@example.test", password="x"
    )
    user, member = approve_application(app, reviewed_by=admin)
    app.refresh_from_db()
    assert app.status == "approved"
    assert Member.objects.filter(user__email="idrissa@example.test").exists()
    assert member.first_name == "Idrissa"
    assert member.status == "active"
```

- [ ] **Step 2: Run tests**

Run: `pytest cooptation/tests/test_a11y.py cooptation/tests/test_e2e_happy_path.py -v`
Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add cooptation/tests/test_a11y.py cooptation/tests/test_e2e_happy_path.py
git commit -m "test(cooptation): a11y on public forms + end-to-end happy path"
```

---

## Task 15: Settings, runbook, STATUS.md, Railway cron service, tag

**Files:**
- Modify: `alumni/settings/staging.py`, `alumni/settings/prod.py`
- Modify: `docs/runbooks/staging-deploy.md`
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Set EMAIL_BACKEND and PASSWORD_RESET_TIMEOUT in staging**

Append to `alumni/settings/staging.py`:

```python
EMAIL_BACKEND = "alumni.email.ResendBackend"
PASSWORD_RESET_TIMEOUT = 7 * 24 * 60 * 60  # 7 days for the post-approval password-set link
```

Mirror in `alumni/settings/prod.py` (same lines).

- [ ] **Step 2: Run full test suite**

```bash
make check
make lint
make test
```

Expected: all green.

- [ ] **Step 3: Update the runbook with Resend + Railway cron service**

Edit `docs/runbooks/staging-deploy.md` to add (after the existing Cloudinary section):

```markdown
## Email — Resend

Mandatory env vars on the app service:
- `RESEND_API_KEY` — from Resend dashboard, "Sending access" scope
- `DEFAULT_FROM_EMAIL` — `Les Retrouvailles <noreply@villageretrouvailles.com>`

DNS records (one-time, on Cloudflare for villageretrouvailles.com):
- DKIM: TXT `resend._domainkey` with the value from Resend
- SPF: TXT `send` with `v=spf1 include:amazonses.com ~all`
- SPF MX: MX `send` with `feedback-smtp.us-east-1.amazonses.com` priority 10
- DMARC: TXT `_dmarc` with `v=DMARC1; p=none;`

Verify in Resend dashboard before first deploy.

## Cron — process_cooptation_deadlines

Create a second Railway service in the same project named `cooptation-cron`:
- Build mode: same Dockerfile (shares image)
- Start command override: `python manage.py process_cooptation_deadlines`
- Schedule: `0 6 * * *` (daily 06:00 UTC)
- Env: shares DATABASE_URL, RESEND_API_KEY, SECRET_KEY, DJANGO_SETTINGS_MODULE from app service

Cap warning: Resend free tier 100 emails/day. With ~5 emails per cooptation, do not batch more than 50 candidates in a single onboarding session.
```

- [ ] **Step 4: Update `docs/superpowers/STATUS.md`**

In the Phase Index, add P3 row:

```markdown
| P3 | Cooptation | Complete (tag `v0.3.0-cooptation`, 2026-MM-DD) | [plan](plans/2026-05-02-cooptation.md) |
```

After the P2 section, add a P3 section listing all 15 tasks with their commit SHAs.

- [ ] **Step 5: Commit STATUS + settings + runbook**

```bash
git add alumni/settings/staging.py alumni/settings/prod.py docs/runbooks/staging-deploy.md docs/superpowers/STATUS.md
git commit -m "docs+config: P3 staging email backend, runbook, STATUS update"
```

- [ ] **Step 6: Create the Railway cron service** (dashboard work)

In Railway → P2 project → **+ New** → **Empty Service** → name `cooptation-cron`:

1. Settings → Source → connect to the same GitHub repo, same branch (`main`)
2. Settings → Build → Builder = Dockerfile (same as app service)
3. Settings → Deploy → Start Command = `python manage.py process_cooptation_deadlines`
4. Settings → Cron Schedule = `0 6 * * *`
5. Variables → click **Reference** for each of: `DATABASE_URL`, `SECRET_KEY`, `DJANGO_SETTINGS_MODULE`, `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `BASIC_AUTH_REQUIRED=false` (cron doesn't go through web — set to `false`)
6. Trigger first manual run and verify logs show `Done. Reminders: 0, expired: 0, purged: 0.`

- [ ] **Step 7: Tag the milestone**

```bash
git tag -a v0.3.0-cooptation -m "Cooptation milestone: signup, parrain vouching, J+7/J+14 cron, knowledge questionnaire, admin moderation, Resend email integration"
```

> *Tag push happens when the user is ready (`git push origin main && git push origin v0.3.0-cooptation`).*

---

## Out of scope (handed off to subsequent plans)

- **P4 (Public surface):** public landing page replacing the placeholder; `PublicSearchEntry` "we're also looking for…" list with collegial validation; public removal flow without auth; `noindex` differentiation between public and private pages.
- **P5 (Mémoire seed):** `Memory` model; Mur des souvenirs admin gallery; `InMemoriamEntry`; PhotoTag with M2M to `Member` already supported.
- **P6 (Ops & RGPD):** Cloudinary→B2 backup workflow; `purge_user_from_backups.py`; RGPD deletion flow (user-initiated); `AuditLog` model + decorator; DMARC monitoring dashboards; Cloudinary orphan reconciliation cron.
- **P7 (Soft launch):** seed content prep; pilot rollout; CAPTCHA / form-fill timing checks if abuse appears; production launch checklist.
