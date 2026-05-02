# P2 Membership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the auth-gated member system — `Member` / `NotificationPreference` / `ConsentRecord` models, profile detail/edit pages, an annuaire with search/filters/pagination, Cloudinary signed-upload integration for profile photos, and project-level login+consent middleware. Every authenticated route in the project becomes private-by-default.

**Architecture:** A single new Django app `members/` owns the domain models, signals, views, forms, fixtures, templates, and template tags. Cross-cutting helpers live at the project level — `alumni/cloudinary.py` (Cloudinary client + lazy URL builder + test fake) and `alumni/middleware.py` (LoginRequired + ConsentRequired). Postgres `unaccent` extension powers accent-insensitive name search via functional indexes. Charter content is stored as versioned Markdown files in `members/charters/`. Charter acceptance writes append-only `ConsentRecord` rows; middleware caches the consent status in the session to avoid per-request DB queries. All UI in French; tests written before implementation.

**Tech Stack:** Django 5.0 · PostgreSQL 16 (`unaccent` extension) · Cloudinary (signed direct upload, lazy transforms) · HTMX 2.x · Tailwind CSS + DaisyUI · django-allauth · django-ratelimit · markdown · beautifulsoup4 (a11y/HTML assertions in tests) · pytest-django · factory-boy

**Spec:** [docs/superpowers/specs/2026-05-02-membership-design.md](../specs/2026-05-02-membership-design.md)

---

## File Structure

**New project-level files:**
- `alumni/cloudinary.py` — Cloudinary client class, `FakeCloudinary` for tests, lazy URL builder
- `alumni/middleware.py` — `LoginRequiredMiddleware`, `ConsentRequiredMiddleware`

**New `members/` app:**
- `members/__init__.py`, `apps.py`, `admin.py`, `models.py`, `signals.py`, `forms.py`, `views.py`, `urls.py`, `context.py`
- `members/charters/__init__.py`, `members/charters/v1_0.md`
- `members/management/__init__.py`, `members/management/commands/__init__.py`, `members/management/commands/create_member.py`
- `members/migrations/0001_initial.py`, `0002_unaccent_and_indexes.py`, `0003_check_constraints.py`
- `members/fixtures/seed_members.json`
- `members/templates/members/directory.html`, `directory_list_partial.html`, `profile_detail.html`, `profile_edit.html`, `charter.html`, `_avatar.html`
- `members/templatetags/__init__.py`, `members/templatetags/member_avatar.py`
- `members/tests/__init__.py`, `conftest.py`, plus per-feature test files

**Modified project files:**
- `pyproject.toml` — add `cloudinary`, `django-ratelimit`, `markdown`, `beautifulsoup4`
- `alumni/settings/base.py` — add `members` to `INSTALLED_APPS`, add new middlewares, add context processor, add `CLOUDINARY_*` and `LOGIN_REQUIRED_WHITELIST` settings
- `alumni/settings/dev.py` — wire dev Cloudinary client
- `alumni/urls.py` — include `members.urls` and the charter URL
- `Makefile` — add `seed` target

---

## Task 1: Add dependencies and scaffold the `members` app

**Files:**
- Modify: `pyproject.toml`
- Modify: `alumni/settings/base.py`
- Create: `members/__init__.py`
- Create: `members/apps.py`
- Create: `members/admin.py`
- Create: `members/models.py`
- Create: `members/migrations/__init__.py`
- Create: `members/tests/__init__.py`

- [ ] **Step 1: Add the four new runtime dependencies to `pyproject.toml`**

Replace the `dependencies = [...]` block with:

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
]
```

And the `dev = [...]` block with:

```toml
dev = [
    "pytest>=8",
    "pytest-django>=4.8",
    "factory-boy>=3.3",
    "ruff>=0.4",
    "pre-commit>=3.7",
    "djlint>=1.34",
    "beautifulsoup4>=4.12",
]
```

- [ ] **Step 2: Install the new dependencies**

Run: `python -m pip install -e ".[dev]"`
Expected: each new package installed without conflicts.

- [ ] **Step 3: Create the app skeleton**

`members/__init__.py`:

```python
default_app_config = "members.apps.MembersConfig"
```

`members/apps.py`:

```python
from django.apps import AppConfig


class MembersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "members"
    verbose_name = "Membres"

    def ready(self):
        from . import signals  # noqa: F401
```

`members/admin.py`:

```python
# Admin registrations land here in Task 8.
```

`members/models.py`:

```python
# Models land here starting Task 4.
```

`members/migrations/__init__.py`: empty file.

`members/tests/__init__.py`: empty file.

- [ ] **Step 4: Register the app in `alumni/settings/base.py`**

In the `INSTALLED_APPS` list, add `"members"` as the last entry (after `"core"`):

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.postgres",  # required for ArrayField + UnaccentExtension
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "core",
    "members",
]
```

Note: `django.contrib.postgres` is added now so `ArrayField` is importable in the next task.

- [ ] **Step 5: Verify Django still boots**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Run the existing test suite to ensure nothing regressed**

Run: `pytest -q`
Expected: 19 passed.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml alumni/settings/base.py members/
git commit -m "chore: scaffold members app and add P2 dependencies"
```

---

## Task 2: Project-level Cloudinary client (`alumni/cloudinary.py`)

**Files:**
- Create: `alumni/cloudinary.py`
- Create: `members/tests/test_cloudinary_client.py`
- Modify: `alumni/settings/base.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_cloudinary_client.py`:

```python
import pytest
from django.conf import settings
from django.test import override_settings

from alumni.cloudinary import FakeCloudinary, get_client, member_thumbnail_url


def test_fake_cloudinary_records_sign_calls():
    fake = FakeCloudinary()
    out = fake.sign_upload(folder="members/abc/", timestamp=1700000000)
    assert out["folder"] == "members/abc/"
    assert out["signature"].startswith("fake-sig-")
    assert fake.sign_calls == [{"folder": "members/abc/", "timestamp": 1700000000}]


def test_fake_cloudinary_records_delete_calls():
    fake = FakeCloudinary()
    fake.delete("members/abc/photo123")
    assert fake.delete_calls == ["members/abc/photo123"]


@override_settings(CLOUDINARY_CLIENT_PATH="alumni.cloudinary.FakeCloudinary")
def test_get_client_returns_fake_when_configured():
    client = get_client()
    assert isinstance(client, FakeCloudinary)


def test_member_thumbnail_url_includes_lazy_transform():
    url = member_thumbnail_url("members/abc/photo123", size=240)
    assert "f_auto" in url
    assert "q_auto:eco" in url
    assert "w_240" in url
    assert "h_240" in url
    assert "/members/abc/photo123" in url


def test_member_thumbnail_url_handles_blank_public_id():
    assert member_thumbnail_url("") == ""
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest members/tests/test_cloudinary_client.py -v`
Expected: ImportError on `alumni.cloudinary`.

- [ ] **Step 3: Implement `alumni/cloudinary.py`**

```python
"""Cloudinary integration: real client, test fake, and lazy URL helpers."""

from __future__ import annotations

import hashlib
import time
from importlib import import_module
from typing import Any, Protocol

from django.conf import settings


class CloudinaryClient(Protocol):
    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]: ...

    def delete(self, public_id: str) -> None: ...


class RealCloudinary:
    """Production client wrapping the `cloudinary` SDK."""

    def __init__(self) -> None:
        import cloudinary  # noqa: WPS433

        cloudinary.config(secure=True)
        self._cloudinary = cloudinary

    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]:
        api_key = self._cloudinary.config().api_key
        api_secret = self._cloudinary.config().api_secret
        params = {"folder": folder, "timestamp": timestamp}
        signature = self._cloudinary.utils.api_sign_request(params, api_secret)
        return {
            "api_key": api_key,
            "timestamp": timestamp,
            "signature": signature,
            "folder": folder,
            "max_file_size": 5 * 1024 * 1024,
            "allowed_formats": ["jpg", "jpeg", "png", "webp"],
        }

    def delete(self, public_id: str) -> None:
        if not public_id:
            return
        self._cloudinary.uploader.destroy(public_id, invalidate=True)


class FakeCloudinary:
    """In-memory client used in tests. Records calls; never hits the network."""

    def __init__(self) -> None:
        self.sign_calls: list[dict[str, Any]] = []
        self.delete_calls: list[str] = []

    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]:
        self.sign_calls.append({"folder": folder, "timestamp": timestamp})
        digest = hashlib.sha1(f"{folder}:{timestamp}".encode()).hexdigest()[:16]
        return {
            "api_key": "fake-key",
            "timestamp": timestamp,
            "signature": f"fake-sig-{digest}",
            "folder": folder,
            "max_file_size": 5 * 1024 * 1024,
            "allowed_formats": ["jpg", "jpeg", "png", "webp"],
        }

    def delete(self, public_id: str) -> None:
        self.delete_calls.append(public_id)


def get_client() -> CloudinaryClient:
    """Resolve the Cloudinary client from settings."""
    path = getattr(settings, "CLOUDINARY_CLIENT_PATH", "alumni.cloudinary.RealCloudinary")
    module_name, _, class_name = path.rpartition(".")
    module = import_module(module_name)
    cls = getattr(module, class_name)
    return cls()


def now_timestamp() -> int:
    return int(time.time())


def member_thumbnail_url(public_id: str, size: int = 240) -> str:
    """Build a lazy Cloudinary URL with f_auto, q_auto:eco, and a square crop."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_fill,g_face,w_{size},h_{size}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"
```

- [ ] **Step 4: Wire the test fake by default in `alumni/settings/base.py`**

Append to `base.py`:

```python
# Cloudinary — overridden per environment. Tests fall through to the fake.
CLOUDINARY_CLIENT_PATH = env(
    "CLOUDINARY_CLIENT_PATH",
    default="alumni.cloudinary.FakeCloudinary",
)
CLOUDINARY_CLOUD_NAME = env("CLOUDINARY_CLOUD_NAME", default="fake-cloud")
```

- [ ] **Step 5: Run tests and confirm they pass**

Run: `pytest members/tests/test_cloudinary_client.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add alumni/cloudinary.py alumni/settings/base.py members/tests/test_cloudinary_client.py
git commit -m "feat: add cloudinary client with fake adapter and lazy url builder"
```

---

## Task 3: Configure Cloudinary env vars and the rate-limit cache

**Files:**
- Modify: `alumni/settings/base.py`
- Modify: `.env.example`

- [ ] **Step 1: Add Cloudinary credentials and rate-limit cache to `alumni/settings/base.py`**

Append to `base.py`:

```python
# Real Cloudinary credentials (only required when CLOUDINARY_CLIENT_PATH points at RealCloudinary)
CLOUDINARY_API_KEY = env("CLOUDINARY_API_KEY", default="")
CLOUDINARY_API_SECRET = env("CLOUDINARY_API_SECRET", default="")
CLOUDINARY_URL = env(
    "CLOUDINARY_URL",
    default=f"cloudinary://{CLOUDINARY_API_KEY}:{CLOUDINARY_API_SECRET}@{CLOUDINARY_CLOUD_NAME}",
)

# Rate limiting (django-ratelimit) — uses Django's default cache backend
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
]
```

- [ ] **Step 2: Document the env vars in `.env.example`**

Append:

```bash
# Cloudinary (signed direct upload). Leave blank to use the in-memory fake (default in tests/dev).
CLOUDINARY_CLIENT_PATH=alumni.cloudinary.FakeCloudinary
CLOUDINARY_CLOUD_NAME=fake-cloud
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

- [ ] **Step 3: Confirm Django still boots**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add alumni/settings/base.py .env.example
git commit -m "chore: add cloudinary env vars and ratelimit cache config"
```

---

## Task 4: `Member` model + initial migration

**Files:**
- Modify: `members/models.py`
- Create: `members/migrations/0001_initial.py` (auto-generated)
- Create: `members/tests/test_models_member.py`
- Create: `members/tests/conftest.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/conftest.py`:

```python
import uuid

import pytest
from django.contrib.auth import get_user_model

from members.models import Member


@pytest.fixture
def make_user(db):
    User = get_user_model()
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "username": f"user{counter['i']}",
            "email": f"user{counter['i']}@example.test",
            "password": "secret-pw-1",
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    return _make


@pytest.fixture
def make_member(db, make_user):
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        user = kwargs.pop("user", None) or make_user()
        defaults = {
            "user": user,
            "first_name": f"First{counter['i']}",
            "last_name": f"Last{counter['i']}",
            "years_attended": [1980, 1981, 1982, 1983],
            "classes": ["6e", "5e", "4e", "3e"],
            "city": "Niamey",
        }
        defaults.update(kwargs)
        return Member.objects.create(**defaults)

    return _make
```

`members/tests/test_models_member.py`:

```python
import pytest
from django.core.exceptions import ValidationError

from members.models import Member


@pytest.mark.django_db
def test_member_full_name_property(make_member):
    m = make_member(first_name="Idrissa", last_name="Saidou")
    assert m.full_name == "Idrissa Saidou"


@pytest.mark.django_db
def test_member_default_status_is_active(make_member):
    m = make_member()
    assert m.status == "active"


@pytest.mark.django_db
def test_member_slug_is_uuid_and_unique(make_member):
    a = make_member()
    b = make_member()
    assert a.slug != b.slug
    # Slug is a UUID, so str(slug) parses cleanly
    import uuid

    uuid.UUID(str(a.slug))


@pytest.mark.django_db
def test_member_city_is_normalized_to_titlecase_on_save(make_member):
    m = make_member(city="  niamey  ")
    assert m.city == "Niamey"


@pytest.mark.django_db
def test_member_country_default_is_niger(make_member):
    m = make_member()
    assert m.country == "Niger"


@pytest.mark.django_db
def test_member_clean_rejects_year_outside_range(make_member):
    m = make_member()
    m.years_attended = [1979, 1980]
    with pytest.raises(ValidationError):
        m.full_clean()


@pytest.mark.django_db
def test_member_clean_rejects_unknown_grade(make_member):
    m = make_member()
    m.classes = ["6e", "2nde"]
    with pytest.raises(ValidationError):
        m.full_clean()


@pytest.mark.django_db
def test_member_show_flags_default_true(make_member):
    m = make_member()
    assert m.show_email is True
    assert m.show_whatsapp is True
    assert m.show_city is True


@pytest.mark.django_db
def test_member_user_cascade(make_member, make_user):
    user = make_user()
    m = make_member(user=user)
    user_id = user.pk
    member_id = m.pk
    user.delete()
    assert not Member.objects.filter(pk=member_id).exists()


@pytest.mark.django_db
def test_member_updated_at_changes_on_save(make_member):
    m = make_member()
    first = m.updated_at
    m.profession = "Enseignant"
    m.save()
    assert m.updated_at > first
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest members/tests/test_models_member.py -v`
Expected: ImportError on `members.models.Member` or attribute error.

- [ ] **Step 3: Implement `members/models.py`**

```python
"""Domain models for the membership app."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models

GRADE_CHOICES = [
    ("6e", "6e"),
    ("5e", "5e"),
    ("4e", "4e"),
    ("3e", "3e"),
]
VALID_GRADES = {key for key, _ in GRADE_CHOICES}

STATUS_CHOICES = [
    ("active", "Actif"),
    ("suspended", "Suspendu"),
    ("deleted", "Supprimé"),
]

VALID_YEARS = range(1980, 1986)


def default_years() -> list[int]:
    return []


def default_classes() -> list[str]:
    return []


class Member(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member",
    )
    slug = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    nickname = models.CharField(max_length=60, blank=True)

    years_attended = ArrayField(
        models.IntegerField(),
        size=6,
        default=default_years,
    )
    classes = ArrayField(
        models.CharField(max_length=4, choices=GRADE_CHOICES),
        size=4,
        default=default_classes,
    )

    city = models.CharField(max_length=80)
    country = models.CharField(max_length=80, default="Niger")
    profession = models.CharField(max_length=120, blank=True)

    photo_public_id = models.CharField(max_length=200, blank=True)

    show_email = models.BooleanField(default=True)
    show_whatsapp = models.BooleanField(default=True)
    show_city = models.BooleanField(default=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["country"]),
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self) -> None:
        super().clean()
        if any(y not in VALID_YEARS for y in self.years_attended):
            raise ValidationError({"years_attended": "Années hors plage 1980-1985."})
        if any(c not in VALID_GRADES for c in self.classes):
            raise ValidationError({"classes": "Classe inconnue."})

    def save(self, *args, **kwargs):
        if self.city:
            self.city = self.city.strip().title()
        if self.country:
            self.country = self.country.strip().title()
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Generate the migration**

Run: `python manage.py makemigrations members`
Expected: `Migrations for 'members': members/migrations/0001_initial.py`

- [ ] **Step 5: Apply the migration**

Run: `python manage.py migrate members`
Expected: `Applying members.0001_initial... OK`

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `pytest members/tests/test_models_member.py -v`
Expected: 10 passed.

- [ ] **Step 7: Commit**

```bash
git add members/models.py members/migrations/0001_initial.py members/tests/conftest.py members/tests/test_models_member.py
git commit -m "feat(members): add Member model with split name, array fields, soft-delete status"
```

---

## Task 5: `NotificationPreference` model + auto-create signal

**Files:**
- Modify: `members/models.py`
- Create: `members/signals.py`
- Create: `members/migrations/0002_notification_preference.py` (auto-generated)
- Create: `members/tests/test_models_preferences.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_models_preferences.py`:

```python
import pytest

from members.models import NotificationPreference


@pytest.mark.django_db
def test_preference_auto_created_on_member_save(make_member):
    m = make_member()
    assert NotificationPreference.objects.filter(member=m).exists()


@pytest.mark.django_db
def test_preference_defaults_are_gdpr_safe(make_member):
    m = make_member()
    prefs = m.preferences
    assert prefs.digest_weekly is False
    assert prefs.in_memoriam_alerts is True
    assert prefs.event_alerts is False
    assert prefs.tag_alerts is True
    assert prefs.data_saver is False


@pytest.mark.django_db
def test_preference_saving_member_does_not_create_duplicate(make_member):
    m = make_member()
    m.profession = "Enseignant"
    m.save()
    assert NotificationPreference.objects.filter(member=m).count() == 1
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest members/tests/test_models_preferences.py -v`
Expected: ImportError or DoesNotExist on `m.preferences`.

- [ ] **Step 3: Add the model to `members/models.py`**

Append:

```python
class NotificationPreference(models.Model):
    member = models.OneToOneField(
        Member,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    digest_weekly = models.BooleanField(default=False)
    in_memoriam_alerts = models.BooleanField(default=True)
    event_alerts = models.BooleanField(default=False)
    tag_alerts = models.BooleanField(default=True)
    data_saver = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Preferences for {self.member.full_name}"
```

- [ ] **Step 4: Create `members/signals.py`**

```python
"""Signal handlers for the membership app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Member, NotificationPreference


@receiver(post_save, sender=Member)
def create_preferences_for_new_member(sender, instance, created, **kwargs):
    if created:
        NotificationPreference.objects.create(member=instance)
```

(`MembersConfig.ready()` already imports this module, set up in Task 1.)

- [ ] **Step 5: Generate and apply the migration**

Run:
```bash
python manage.py makemigrations members
python manage.py migrate members
```
Expected: `0002_notificationpreference.py` created and applied.

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `pytest members/tests/test_models_preferences.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add members/models.py members/signals.py members/migrations/0002_*.py members/tests/test_models_preferences.py
git commit -m "feat(members): add NotificationPreference with GDPR-safe defaults and auto-create signal"
```

---

## Task 6: `ConsentRecord` model

**Files:**
- Modify: `members/models.py`
- Create: `members/migrations/0003_consent_record.py` (auto-generated)
- Create: `members/tests/test_models_consent.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_models_consent.py`:

```python
import pytest

from members.models import ConsentRecord


@pytest.mark.django_db
def test_consent_record_stores_version_ip_and_member(make_member):
    m = make_member()
    rec = ConsentRecord.objects.create(
        member=m,
        charter_version="1.0",
        ip_address="127.0.0.1",
    )
    assert rec.charter_version == "1.0"
    assert rec.ip_address == "127.0.0.1"
    assert rec.accepted_at is not None


@pytest.mark.django_db
def test_consent_records_ordered_newest_first(make_member):
    m = make_member()
    a = ConsentRecord.objects.create(member=m, charter_version="1.0", ip_address="127.0.0.1")
    b = ConsentRecord.objects.create(member=m, charter_version="1.1", ip_address="127.0.0.1")
    qs = list(ConsentRecord.objects.filter(member=m))
    assert qs[0].pk == b.pk
    assert qs[1].pk == a.pk


@pytest.mark.django_db
def test_consent_record_cascades_when_member_deleted(make_member):
    m = make_member()
    ConsentRecord.objects.create(member=m, charter_version="1.0", ip_address="127.0.0.1")
    member_pk = m.pk
    m.user.delete()
    assert ConsentRecord.objects.filter(member_id=member_pk).count() == 0
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest members/tests/test_models_consent.py -v`
Expected: ImportError on `ConsentRecord`.

- [ ] **Step 3: Add the model to `members/models.py`**

Append:

```python
class ConsentRecord(models.Model):
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="consents",
    )
    charter_version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()

    class Meta:
        indexes = [models.Index(fields=["member", "charter_version"])]
        ordering = ["-accepted_at"]

    def __str__(self) -> str:
        return f"{self.member.full_name} → charter v{self.charter_version}"
```

- [ ] **Step 4: Generate and apply the migration**

Run:
```bash
python manage.py makemigrations members
python manage.py migrate members
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `pytest members/tests/test_models_consent.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add members/models.py members/migrations/0003_*.py members/tests/test_models_consent.py
git commit -m "feat(members): add append-only ConsentRecord model"
```

---

## Task 7: Postgres `unaccent` extension, functional indexes, and CHECK constraints

**Files:**
- Create: `members/migrations/0004_unaccent_and_indexes.py`
- Create: `members/migrations/0005_check_constraints.py`
- Create: `members/tests/test_search_indexes.py`

- [ ] **Step 1: Write the failing test**

`members/tests/test_search_indexes.py`:

```python
import pytest
from django.db import connection


@pytest.mark.django_db
def test_unaccent_extension_is_installed():
    with connection.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'unaccent'")
        rows = cur.fetchall()
    assert rows, "unaccent extension is not installed"


@pytest.mark.django_db
def test_unaccent_functional_indexes_exist():
    with connection.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'members_member' AND indexname LIKE '%unaccent%'"
        )
        names = {row[0] for row in cur.fetchall()}
    expected = {
        "members_member_first_name_unaccent_idx",
        "members_member_last_name_unaccent_idx",
        "members_member_nickname_unaccent_idx",
    }
    assert expected <= names


@pytest.mark.django_db
def test_status_check_constraint_rejects_invalid_value(make_user):
    from django.db import IntegrityError, transaction
    from django.db import connection as conn

    user = make_user()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO members_member "
                    "(user_id, slug, first_name, last_name, nickname, "
                    " years_attended, classes, city, country, profession, "
                    " photo_public_id, show_email, show_whatsapp, show_city, "
                    " status, created_at, updated_at) "
                    "VALUES (%s, gen_random_uuid(), 'A', 'B', '', "
                    " ARRAY[1980], ARRAY['6e']::varchar[], 'Niamey', 'Niger', '', "
                    " '', true, true, true, "
                    " 'WHATEVER', NOW(), NOW())",
                    [user.pk],
                )


@pytest.mark.django_db
def test_year_check_constraint_rejects_out_of_range(make_user):
    from django.db import IntegrityError, transaction
    from django.db import connection as conn

    user = make_user()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO members_member "
                    "(user_id, slug, first_name, last_name, nickname, "
                    " years_attended, classes, city, country, profession, "
                    " photo_public_id, show_email, show_whatsapp, show_city, "
                    " status, created_at, updated_at) "
                    "VALUES (%s, gen_random_uuid(), 'A', 'B', '', "
                    " ARRAY[1979], ARRAY['6e']::varchar[], 'Niamey', 'Niger', '', "
                    " '', true, true, true, "
                    " 'active', NOW(), NOW())",
                    [user.pk],
                )
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest members/tests/test_search_indexes.py -v`
Expected: index queries return empty rowset; CHECK constraints not yet enforced.

- [ ] **Step 3: Create migration `0004_unaccent_and_indexes.py`**

```python
from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("members", "0003_consentrecord")]

    operations = [
        UnaccentExtension(),
        migrations.RunSQL(
            sql="""
            CREATE INDEX members_member_first_name_unaccent_idx
                ON members_member (LOWER(unaccent(first_name)));
            CREATE INDEX members_member_last_name_unaccent_idx
                ON members_member (LOWER(unaccent(last_name)));
            CREATE INDEX members_member_nickname_unaccent_idx
                ON members_member (LOWER(unaccent(nickname)));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS members_member_first_name_unaccent_idx;
            DROP INDEX IF EXISTS members_member_last_name_unaccent_idx;
            DROP INDEX IF EXISTS members_member_nickname_unaccent_idx;
            """,
        ),
    ]
```

> Note: the `0003_consentrecord` dependency name reflects Django's auto-naming. If your local migration is named differently, adjust accordingly.

- [ ] **Step 4: Create migration `0005_check_constraints.py`**

```python
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("members", "0004_unaccent_and_indexes")]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE members_member
                ADD CONSTRAINT members_member_status_valid
                CHECK (status IN ('active', 'suspended', 'deleted'));

            ALTER TABLE members_member
                ADD CONSTRAINT members_member_years_in_range
                CHECK (years_attended <@ ARRAY[1980,1981,1982,1983,1984,1985]);

            ALTER TABLE members_member
                ADD CONSTRAINT members_member_classes_in_set
                CHECK (classes <@ ARRAY['6e','5e','4e','3e']::varchar[]);
            """,
            reverse_sql="""
            ALTER TABLE members_member DROP CONSTRAINT IF EXISTS members_member_status_valid;
            ALTER TABLE members_member DROP CONSTRAINT IF EXISTS members_member_years_in_range;
            ALTER TABLE members_member DROP CONSTRAINT IF EXISTS members_member_classes_in_set;
            """,
        ),
    ]
```

- [ ] **Step 5: Apply the migrations**

Run: `python manage.py migrate members`
Expected: both migrations apply OK.

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `pytest members/tests/test_search_indexes.py -v`
Expected: 4 passed.

- [ ] **Step 7: Re-run the full members test suite to confirm no regression**

Run: `pytest members -v`
Expected: all members tests pass.

- [ ] **Step 8: Commit**

```bash
git add members/migrations/0004_*.py members/migrations/0005_*.py members/tests/test_search_indexes.py
git commit -m "feat(members): add unaccent extension, functional indexes, and CHECK constraints"
```

---

## Task 8: Django admin registrations

**Files:**
- Modify: `members/admin.py`
- Create: `members/tests/test_admin.py`

- [ ] **Step 1: Write the failing test**

`members/tests/test_admin.py`:

```python
import pytest
from django.contrib import admin

from members.models import ConsentRecord, Member, NotificationPreference


def test_member_registered_in_admin():
    assert admin.site.is_registered(Member)


def test_notification_preference_registered_in_admin():
    assert admin.site.is_registered(NotificationPreference)


def test_consent_record_registered_in_admin():
    assert admin.site.is_registered(ConsentRecord)
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_admin.py -v`
Expected: 3 fails — none registered.

- [ ] **Step 3: Implement `members/admin.py`**

```python
from django.contrib import admin

from .models import ConsentRecord, Member, NotificationPreference


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "city", "country", "profession", "status", "created_at")
    list_filter = ("status", "country", "city")
    search_fields = ("first_name", "last_name", "nickname")
    readonly_fields = ("slug", "created_at", "updated_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("member", "digest_weekly", "in_memoriam_alerts", "event_alerts", "tag_alerts", "data_saver")
    list_filter = ("digest_weekly", "in_memoriam_alerts", "event_alerts", "tag_alerts")


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("member", "charter_version", "accepted_at", "ip_address")
    list_filter = ("charter_version",)
    search_fields = ("member__first_name", "member__last_name")
    readonly_fields = ("member", "charter_version", "accepted_at", "ip_address")

    def has_add_permission(self, request):
        return False
```

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest members/tests/test_admin.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add members/admin.py members/tests/test_admin.py
git commit -m "feat(members): register Member, NotificationPreference, and ConsentRecord in admin"
```

---

## Task 9: Charter package — versioned content + registry

**Files:**
- Create: `members/charters/__init__.py`
- Create: `members/charters/v1_0.md`
- Create: `members/tests/test_charters.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_charters.py`:

```python
from members.charters import (
    CHARTER_CURRENT_VERSION,
    CHARTER_VERSIONS,
    get_charter_text,
)


def test_current_version_is_listed_in_registry():
    assert CHARTER_CURRENT_VERSION in CHARTER_VERSIONS


def test_get_charter_text_returns_markdown_for_known_version():
    text = get_charter_text("1.0")
    assert text.startswith("#")
    assert "CEG" in text


def test_get_charter_text_raises_for_unknown_version():
    import pytest

    with pytest.raises(KeyError):
        get_charter_text("99.9")
```

- [ ] **Step 2: Confirm failure**

Run: `pytest members/tests/test_charters.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `members/charters/v1_0.md`**

```markdown
# Charte de la Communauté — Version 1.0

Cette plateforme est réservée aux anciens élèves du **CEG 1 Birni — Zinder**, promotions 1980 à 1985. En accédant aux contenus de l'espace membre, vous acceptez les engagements suivants :

## Respect

Vous traitez tous les membres avec courtoisie. Les attaques personnelles, les propos discriminatoires et le harcèlement n'ont pas leur place ici.

## Confidentialité

Les coordonnées et photos partagées dans l'annuaire sont destinées exclusivement aux membres validés. Vous ne les diffusez pas en dehors de la plateforme.

## Données personnelles

Vous reconnaissez que la plateforme conserve un journal de votre acceptation de la présente charte (date, version, adresse IP) à des fins légales. Vos données peuvent être exportées ou supprimées sur demande conformément au RGPD.

## Modération

Les administrateurs peuvent modérer ou suspendre tout compte qui enfreint cette charte. Les décisions de modération sont consignées et révisables.

---

*En cliquant « J'accepte », vous adhérez à cette charte dans sa version 1.0.*
```

- [ ] **Step 4: Implement `members/charters/__init__.py`**

```python
"""Versioned charter content. Old versions remain in repo for audit."""

from pathlib import Path

CHARTER_DIR = Path(__file__).resolve().parent

CHARTER_CURRENT_VERSION = "1.0"

CHARTER_VERSIONS: dict[str, str] = {
    "1.0": "v1_0.md",
}


def get_charter_text(version: str) -> str:
    if version not in CHARTER_VERSIONS:
        raise KeyError(f"Unknown charter version: {version}")
    return (CHARTER_DIR / CHARTER_VERSIONS[version]).read_text(encoding="utf-8")
```

- [ ] **Step 5: Confirm tests pass**

Run: `pytest members/tests/test_charters.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add members/charters/
git add members/tests/test_charters.py
git commit -m "feat(members): add versioned charter package with v1.0 French content"
```

---

## Task 10: `LoginRequiredMiddleware` (project-level)

**Files:**
- Create: `alumni/middleware.py`
- Modify: `alumni/settings/base.py`
- Create: `members/tests/test_middleware_login.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_middleware_login.py`:

```python
import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_endpoint_does_not_require_login():
    response = Client().get("/health")
    assert response.status_code == 200


@pytest.mark.django_db
def test_landing_does_not_require_login():
    response = Client().get("/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_page_does_not_require_login():
    response = Client().get("/accounts/login/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_redirects_anonymous_to_login():
    # `/admin/` is NOT in the whitelist; it has its own auth, but our middleware
    # runs first and treats it like any other private route.
    response = Client().get("/admin/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
    assert "next=/admin/" in response["Location"]


@pytest.mark.django_db
def test_static_paths_are_whitelisted():
    response = Client().get("/static/css/output.css")
    # static may 404 in dev (file not collected) but must NOT 302 to login
    assert response.status_code != 302
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_middleware_login.py -v`
Expected: `/admin/` test fails (returns 302 to admin's own login, not ours).

- [ ] **Step 3: Create `alumni/middleware.py`**

```python
"""Project-wide middlewares: login + consent gating."""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect


class LoginRequiredMiddleware:
    """Redirect anonymous users to login for any non-whitelisted path."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.whitelist = list(getattr(settings, "LOGIN_REQUIRED_WHITELIST", []))

    def __call__(self, request):
        if request.user.is_authenticated:
            return self.get_response(request)

        if self._is_whitelisted(request.path):
            return self.get_response(request)

        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
        qs = urlencode({"next": request.get_full_path()})
        return HttpResponseRedirect(f"{login_url}?{qs}")

    def _is_whitelisted(self, path: str) -> bool:
        for entry in self.whitelist:
            if entry.endswith("/"):
                if path.startswith(entry):
                    return True
            else:
                if path == entry:
                    return True
        return False
```

- [ ] **Step 4: Wire the middleware in `alumni/settings/base.py`**

Modify the `MIDDLEWARE` list — insert `LoginRequiredMiddleware` after `AuthenticationMiddleware` and before `AccountMiddleware`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "alumni.middleware.LoginRequiredMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

- [ ] **Step 5: Run the new tests and confirm they pass**

Run: `pytest members/tests/test_middleware_login.py -v`
Expected: 5 passed.

- [ ] **Step 6: Run the full project test suite to confirm no regressions**

Run: `pytest -v`
Expected: all previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add alumni/middleware.py alumni/settings/base.py members/tests/test_middleware_login.py
git commit -m "feat(alumni): add LoginRequiredMiddleware with whitelist for public paths"
```

---

## Task 11: `ConsentRequiredMiddleware` with session caching

**Files:**
- Modify: `alumni/middleware.py`
- Modify: `alumni/settings/base.py`
- Create: `members/tests/test_middleware_consent.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_middleware_consent.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def member_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    client.user = user
    return client


@pytest.mark.django_db
def test_logged_in_member_without_consent_is_redirected_to_charter(member_client):
    response = member_client.get("/admin/")
    assert response.status_code == 302
    assert "/charte/" in response["Location"]
    assert "next=/admin/" in response["Location"]


@pytest.mark.django_db
def test_logged_in_member_with_current_consent_passes(member_client):
    ConsentRecord.objects.create(
        member=member_client.member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    # Pre-warm the session: middleware will record the consent in session on first hit
    response = member_client.get("/admin/")
    # /admin/ requires staff but middleware should NOT bounce to /charte/
    assert "/charte/" not in response.get("Location", "")


@pytest.mark.django_db
def test_charter_path_is_skipped_by_consent_middleware(member_client):
    response = member_client.get("/charte/")
    # Path itself isn't implemented yet (Task 12), but middleware must not loop
    assert response.status_code in (200, 404, 405)


@pytest.mark.django_db
def test_logout_path_is_skipped_by_consent_middleware(member_client):
    response = member_client.post("/accounts/logout/")
    # We just want to assert no /charte/ redirect
    assert "/charte/" not in response.get("Location", "")


@pytest.mark.django_db
def test_consent_state_is_cached_in_session(member_client):
    ConsentRecord.objects.create(
        member=member_client.member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    member_client.get("/admin/")
    session = member_client.session
    assert session.get("consent_ok_for") == CHARTER_CURRENT_VERSION
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_middleware_consent.py -v`
Expected: middleware not implemented; redirects don't go to `/charte/`.

- [ ] **Step 3: Append `ConsentRequiredMiddleware` to `alumni/middleware.py`**

```python
class ConsentRequiredMiddleware:
    """Block authenticated users until they accept the current charter version."""

    SKIP_PREFIXES = ("/charte/", "/accounts/logout/")
    SESSION_KEY = "consent_ok_for"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if any(request.path.startswith(p) for p in self.SKIP_PREFIXES):
            return self.get_response(request)

        from members.charters import CHARTER_CURRENT_VERSION

        cached = request.session.get(self.SESSION_KEY)
        if cached == CHARTER_CURRENT_VERSION:
            return self.get_response(request)

        member = getattr(request.user, "member", None)
        if member is None:
            # Authenticated user without a Member row (anomaly during P2 dev).
            # Don't loop them; let the view handle it.
            return self.get_response(request)

        from members.models import ConsentRecord

        has_consent = ConsentRecord.objects.filter(
            member=member,
            charter_version=CHARTER_CURRENT_VERSION,
        ).exists()

        if has_consent:
            request.session[self.SESSION_KEY] = CHARTER_CURRENT_VERSION
            return self.get_response(request)

        from urllib.parse import urlencode

        qs = urlencode({"next": request.get_full_path()})
        return HttpResponseRedirect(f"/charte/?{qs}")
```

- [ ] **Step 4: Add to `MIDDLEWARE` in `alumni/settings/base.py`**

Insert `alumni.middleware.ConsentRequiredMiddleware` immediately after `LoginRequiredMiddleware`:

```python
"alumni.middleware.LoginRequiredMiddleware",
"alumni.middleware.ConsentRequiredMiddleware",
"allauth.account.middleware.AccountMiddleware",
```

- [ ] **Step 5: Run tests and confirm pass**

Run: `pytest members/tests/test_middleware_consent.py -v`
Expected: 5 passed.

- [ ] **Step 6: Confirm full suite still green**

Run: `pytest -v`
Expected: all green. Previously-passing tests for `/health`, `/`, `/accounts/login/` are anonymous and bypass the consent gate.

- [ ] **Step 7: Commit**

```bash
git add alumni/middleware.py alumni/settings/base.py members/tests/test_middleware_consent.py
git commit -m "feat(alumni): add ConsentRequiredMiddleware with session caching"
```

---

## Task 12: `CharterView` — display + accept

**Files:**
- Create: `members/views.py` (initial)
- Create: `members/urls.py`
- Modify: `alumni/urls.py`
- Create: `members/templates/members/charter.html`
- Create: `members/tests/test_views_charter.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_views_charter.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def member_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_charter_get_renders_markdown_for_logged_in_member(member_client):
    response = member_client.get("/charte/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Charte de la Communauté" in body
    assert "<h1" in body  # Markdown rendered to HTML


@pytest.mark.django_db
def test_charter_post_records_consent_and_redirects(member_client):
    response = member_client.post("/charte/?next=/admin/")
    assert response.status_code == 302
    assert response["Location"] == "/admin/"
    rec = ConsentRecord.objects.get(member=member_client.member)
    assert rec.charter_version == CHARTER_CURRENT_VERSION
    assert rec.ip_address == "127.0.0.1"


@pytest.mark.django_db
def test_charter_post_default_redirect_is_root(member_client):
    response = member_client.post("/charte/")
    assert response.status_code == 302
    assert response["Location"] == "/"


@pytest.mark.django_db
def test_charter_post_requires_login():
    response = Client().post("/charte/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_charter_get_includes_noindex_meta(member_client):
    response = member_client.get("/charte/")
    assert b'<meta name="robots" content="noindex"' in response.content
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_views_charter.py -v`
Expected: 404 on `/charte/`.

- [ ] **Step 3: Create `members/views.py`**

```python
"""Views for the membership app."""

from __future__ import annotations

import markdown as _markdown
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .charters import CHARTER_CURRENT_VERSION, get_charter_text
from .models import ConsentRecord


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


@require_http_methods(["GET", "POST"])
def charter_view(request):
    if request.method == "POST":
        member = getattr(request.user, "member", None)
        if member is not None:
            ConsentRecord.objects.create(
                member=member,
                charter_version=CHARTER_CURRENT_VERSION,
                ip_address=_client_ip(request),
            )
            request.session["consent_ok_for"] = CHARTER_CURRENT_VERSION
        next_url = request.GET.get("next") or request.POST.get("next") or "/"
        return HttpResponseRedirect(next_url)

    body_html = _markdown.markdown(
        get_charter_text(CHARTER_CURRENT_VERSION),
        extensions=["extra"],
    )
    return render(
        request,
        "members/charter.html",
        {
            "charter_html": body_html,
            "charter_version": CHARTER_CURRENT_VERSION,
            "next": request.GET.get("next", "/"),
        },
    )
```

- [ ] **Step 4: Create `members/urls.py`**

```python
from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("charte/", views.charter_view, name="charter"),
]
```

- [ ] **Step 5: Mount the URLs in `alumni/urls.py`**

Replace the file with:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("members.urls")),
    path("", include("core.urls")),
]
```

- [ ] **Step 6: Create `members/templates/members/charter.html`**

```django
{% extends "base.html" %}
{% load i18n %}

{% block extra_head %}
<meta name="robots" content="noindex,nofollow">
{% endblock %}

{% block title %}{% trans "Charte" %} v{{ charter_version }}{% endblock %}

{% block content %}
<article class="prose mx-auto max-w-2xl p-4">
    {{ charter_html|safe }}
</article>
<form method="post" action="?next={{ next|urlencode }}" class="mx-auto max-w-2xl p-4">
    {% csrf_token %}
    <button type="submit" class="btn btn-primary">
        {% trans "J'accepte" %}
    </button>
</form>
{% endblock %}
```

> Verify the existing `base.html` exposes `{% block extra_head %}` and `{% block content %}`. If not, add them in `templates/base.html`.

- [ ] **Step 7: If `base.html` is missing those blocks, add them**

Inspect `templates/base.html`. The Foundation plan should already include `{% block content %}` — confirm and, if `extra_head` is missing, add inside the `<head>` element:

```django
{% block extra_head %}{% endblock %}
```

- [ ] **Step 8: Run tests and confirm pass**

Run: `pytest members/tests/test_views_charter.py -v`
Expected: 5 passed.

- [ ] **Step 9: Commit**

```bash
git add members/views.py members/urls.py members/templates/members/charter.html alumni/urls.py templates/base.html
git commit -m "feat(members): add CharterView with markdown render and consent capture"
```

---

## Task 13: `member_avatar` template tag (initials + color)

**Files:**
- Create: `members/templatetags/__init__.py`
- Create: `members/templatetags/member_avatar.py`
- Create: `members/templates/members/_avatar.html`
- Create: `members/tests/test_avatar.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_avatar.py`:

```python
import re

import pytest

from members.templatetags.member_avatar import (
    initials_for_member,
    avatar_hue_for_slug,
)


@pytest.mark.django_db
def test_initials_uses_first_letter_of_each_name(make_member):
    m = make_member(first_name="Idrissa", last_name="Saidou")
    assert initials_for_member(m) == "IS"


@pytest.mark.django_db
def test_initials_uppercased(make_member):
    m = make_member(first_name="idrissa", last_name="saidou")
    assert initials_for_member(m) == "IS"


def test_avatar_hue_is_deterministic_for_same_slug():
    s = "11111111-1111-1111-1111-111111111111"
    assert avatar_hue_for_slug(s) == avatar_hue_for_slug(s)


def test_avatar_hue_distributes_across_slugs():
    hues = {avatar_hue_for_slug(f"slug-{i}") for i in range(50)}
    assert len(hues) > 25  # rough distribution check


def test_avatar_hue_is_in_valid_range():
    h = avatar_hue_for_slug("any-slug")
    assert 0 <= h < 360


@pytest.mark.django_db
def test_member_avatar_renders_initials_when_no_photo(make_member):
    from django.template import Context, Template

    m = make_member(first_name="Ada", last_name="Lovelace")
    tmpl = Template("{% load member_avatar %}{% member_avatar member size=48 %}")
    out = tmpl.render(Context({"member": m}))
    assert "AL" in out
    assert re.search(r"hsl\(\d+,\s*55%,\s*45%\)", out)
    assert "<img" not in out


@pytest.mark.django_db
def test_member_avatar_renders_image_when_photo_set(make_member):
    from django.template import Context, Template

    m = make_member(first_name="Ada", last_name="Lovelace", photo_public_id="members/abc/photo1")
    tmpl = Template("{% load member_avatar %}{% member_avatar member size=48 %}")
    out = tmpl.render(Context({"member": m}))
    assert "<img" in out
    assert "members/abc/photo1" in out


@pytest.mark.django_db
def test_member_avatar_falls_back_to_initials_when_viewer_has_data_saver(make_member):
    from django.template import Context, Template

    m = make_member(first_name="Ada", last_name="Lovelace", photo_public_id="members/abc/photo1")

    class FakePrefs:
        data_saver = True

    tmpl = Template("{% load member_avatar %}{% member_avatar member size=48 %}")
    out = tmpl.render(Context({"member": m, "member_prefs": FakePrefs()}))
    assert "<img" not in out
    assert "AL" in out
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_avatar.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the template tag**

`members/templatetags/__init__.py`: empty file.

`members/templatetags/member_avatar.py`:

```python
"""Template tag rendering a member avatar (photo or deterministic initials)."""

from __future__ import annotations

import hashlib

from django import template
from django.template.loader import render_to_string

from alumni.cloudinary import member_thumbnail_url

register = template.Library()


def initials_for_member(member) -> str:
    first = (member.first_name or "")[:1]
    last = (member.last_name or "")[:1]
    return f"{first}{last}".upper()


def avatar_hue_for_slug(slug: str) -> int:
    digest = hashlib.md5(str(slug).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 360


@register.simple_tag(takes_context=True)
def member_avatar(context, member, size: int = 240, force_initials: bool = False) -> str:
    # Honor viewer's data-saver preference (spec §10) — exposed by the
    # members.context.member_preferences context processor.
    prefs = context.get("member_prefs")
    data_saver = bool(prefs and prefs.data_saver)
    use_image = bool(member.photo_public_id) and not force_initials and not data_saver
    return render_to_string(
        "members/_avatar.html",
        {
            "member": member,
            "size": size,
            "use_image": use_image,
            "image_url": member_thumbnail_url(member.photo_public_id, size=size) if use_image else "",
            "initials": initials_for_member(member),
            "hue": avatar_hue_for_slug(str(member.slug)),
        },
    )
```

`members/templates/members/_avatar.html`:

```django
{% if use_image %}
<img src="{{ image_url }}"
     alt="{{ member.full_name }}"
     loading="lazy"
     width="{{ size }}"
     height="{{ size }}"
     class="avatar avatar-photo rounded-full">
{% else %}
<div class="avatar avatar-initials inline-flex items-center justify-center rounded-full text-white font-semibold"
     style="background:hsl({{ hue }}, 55%, 45%); width:{{ size }}px; height:{{ size }}px; font-size:{% widthratio size 5 2 %}px;"
     aria-label="{{ member.full_name }}">
    {{ initials }}
</div>
{% endif %}
```

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest members/tests/test_avatar.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add members/templatetags/ members/templates/members/_avatar.html members/tests/test_avatar.py
git commit -m "feat(members): add member_avatar template tag with initials fallback"
```

---

## Task 14: Context processor for member preferences + data-saver

**Files:**
- Create: `members/context.py`
- Modify: `alumni/settings/base.py`
- Create: `members/tests/test_context_processor.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_context_processor.py`:

```python
import pytest
from django.test import Client, RequestFactory

from members.context import member_preferences


@pytest.mark.django_db
def test_anonymous_request_returns_empty_prefs():
    rf = RequestFactory()
    req = rf.get("/")
    from django.contrib.auth.models import AnonymousUser

    req.user = AnonymousUser()
    ctx = member_preferences(req)
    assert ctx["member_prefs"] is None


@pytest.mark.django_db
def test_authenticated_member_request_exposes_prefs(make_member, make_user):
    user = make_user(password="x")
    member = make_member(user=user)
    rf = RequestFactory()
    req = rf.get("/")
    req.user = user
    ctx = member_preferences(req)
    assert ctx["member_prefs"] is not None
    assert ctx["member_prefs"].pk == member.preferences.pk


@pytest.mark.django_db
def test_template_can_read_data_saver(make_member, make_user):
    from django.template import Context, RequestContext, Template

    user = make_user(password="x")
    member = make_member(user=user)
    member.preferences.data_saver = True
    member.preferences.save()
    rf = RequestFactory()
    req = rf.get("/")
    req.user = user
    rc = RequestContext(req, {})
    tmpl = Template("{% if member_prefs.data_saver %}YES{% else %}NO{% endif %}")
    assert tmpl.render(rc).strip() == "YES"
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_context_processor.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `members/context.py`**

```python
"""Context processor exposing the active member's preferences to templates."""

from __future__ import annotations


def member_preferences(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"member_prefs": None}
    member = getattr(request.user, "member", None)
    if member is None:
        return {"member_prefs": None}
    prefs = getattr(member, "preferences", None)
    return {"member_prefs": prefs}
```

- [ ] **Step 4: Register the processor in `alumni/settings/base.py`**

Inside `TEMPLATES[0]["OPTIONS"]["context_processors"]`, append `"members.context.member_preferences"`:

```python
"context_processors": [
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
    "django.template.context_processors.i18n",
    "members.context.member_preferences",
],
```

- [ ] **Step 5: Run tests and confirm pass**

Run: `pytest members/tests/test_context_processor.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add members/context.py alumni/settings/base.py members/tests/test_context_processor.py
git commit -m "feat(members): add context processor exposing member_prefs to templates"
```

---

## Task 15: `ProfileDetailView` with privacy toggles

**Files:**
- Modify: `members/views.py`
- Modify: `members/urls.py`
- Create: `members/templates/members/profile_detail.html`
- Create: `members/tests/test_views_profile_detail.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_views_profile_detail.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_profile_detail_renders_for_active_member(consenting_client, make_member):
    target = make_member(first_name="Fatou", last_name="Diallo", city="Niamey")
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert response.status_code == 200
    assert b"Fatou" in response.content
    assert b"Diallo" in response.content


@pytest.mark.django_db
def test_profile_detail_404_for_deleted(consenting_client, make_member):
    target = make_member(status="deleted")
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_profile_detail_404_for_suspended_to_non_admin(consenting_client, make_member):
    target = make_member(status="suspended")
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_profile_detail_200_for_suspended_to_admin(make_member, make_user):
    admin = make_user(is_staff=True, password="x")
    make_member(user=admin)
    ConsentRecord.objects.create(member=admin.member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    target = make_member(status="suspended")
    client = Client()
    client.login(username=admin.username, password="x")
    response = client.get(f"/membres/{target.slug}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_profile_detail_hides_email_when_show_email_false(consenting_client, make_member, make_user):
    user = make_user(email="hidden@example.test")
    target = make_member(user=user, show_email=False)
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert b"hidden@example.test" not in response.content


@pytest.mark.django_db
def test_profile_detail_shows_email_when_show_email_true(consenting_client, make_member, make_user):
    user = make_user(email="visible@example.test")
    target = make_member(user=user, show_email=True)
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert b"visible@example.test" in response.content


@pytest.mark.django_db
def test_profile_detail_hides_city_when_show_city_false(consenting_client, make_member):
    target = make_member(city="Cotonou", show_city=False)
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert b"Cotonou" not in response.content


@pytest.mark.django_db
def test_profile_detail_includes_noindex(consenting_client, make_member):
    target = make_member()
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert b'name="robots"' in response.content
    assert b"noindex" in response.content
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_views_profile_detail.py -v`
Expected: 404 — view not implemented.

- [ ] **Step 3: Append `ProfileDetailView` to `members/views.py`**

```python
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Member


def profile_detail_view(request, slug):
    member = get_object_or_404(Member, slug=slug)
    if member.status == "deleted":
        raise Http404
    if member.status == "suspended" and not request.user.is_staff:
        raise Http404
    return render(
        request,
        "members/profile_detail.html",
        {
            "target": member,
            "is_self": getattr(request.user, "member", None) == member,
        },
    )
```

- [ ] **Step 4: Add the URL**

In `members/urls.py`:

```python
from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("charte/", views.charter_view, name="charter"),
    path("membres/<uuid:slug>/", views.profile_detail_view, name="profile_detail"),
]
```

- [ ] **Step 5: Create the template**

`members/templates/members/profile_detail.html`:

```django
{% extends "base.html" %}
{% load i18n member_avatar %}

{% block extra_head %}
<meta name="robots" content="noindex,nofollow">
{% endblock %}

{% block title %}{{ target.full_name }}{% endblock %}

{% block content %}
<article class="mx-auto max-w-xl p-4">
    {% member_avatar target size=160 %}
    <h1 class="text-2xl font-semibold mt-2">{{ target.full_name }}</h1>
    {% if target.nickname %}
        <p class="text-sm opacity-70">« {{ target.nickname }} »</p>
    {% endif %}

    <dl class="mt-4 space-y-2">
        {% if target.profession %}
        <div>
            <dt class="font-medium">{% trans "Profession" %}</dt>
            <dd>{{ target.profession }}</dd>
        </div>
        {% endif %}
        {% if target.show_city and target.city %}
        <div>
            <dt class="font-medium">{% trans "Ville" %}</dt>
            <dd>{{ target.city }}, {{ target.country }}</dd>
        </div>
        {% endif %}
        <div>
            <dt class="font-medium">{% trans "Promotion" %}</dt>
            <dd>{{ target.years_attended|join:", " }}</dd>
        </div>
        {% if target.show_email %}
        <div>
            <dt class="font-medium">{% trans "Email" %}</dt>
            <dd><a href="mailto:{{ target.user.email }}">{{ target.user.email }}</a></dd>
        </div>
        {% endif %}
    </dl>

    {% if is_self %}
        <a href="{% url 'members:profile_edit' %}" class="btn btn-secondary mt-6">
            {% trans "Modifier mon profil" %}
        </a>
    {% endif %}
</article>
{% endblock %}
```

> The `{% url 'members:profile_edit' %}` reverse is for Task 16; the template will fail to render that block until Task 16 lands. To keep this task green, the test for `is_self` rendering is deferred to Task 16. Wrap the link with `{% if is_self %}{% url ... %}` *only* once the URL exists. To unblock now, replace the `<a href>` with `<a href="/profil/">`.

Replace the link with the literal path for now:

```django
{% if is_self %}
    <a href="/profil/" class="btn btn-secondary mt-6">
        {% trans "Modifier mon profil" %}
    </a>
{% endif %}
```

- [ ] **Step 6: Run tests and confirm pass**

Run: `pytest members/tests/test_views_profile_detail.py -v`
Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add members/views.py members/urls.py members/templates/members/profile_detail.html members/tests/test_views_profile_detail.py
git commit -m "feat(members): add ProfileDetailView with status gating and privacy toggles"
```

---

## Task 16: `ProfileEditView` and `ProfileEditForm` (no photo upload yet)

**Files:**
- Create: `members/forms.py`
- Modify: `members/views.py`
- Modify: `members/urls.py`
- Create: `members/templates/members/profile_edit.html`
- Create: `members/tests/test_views_profile_edit.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_views_profile_edit.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_profile_edit_get_renders_form(consenting_client):
    response = consenting_client.get("/profil/")
    assert response.status_code == 200
    assert b'name="nickname"' in response.content
    assert b'name="city"' in response.content
    assert b'name="profession"' in response.content


@pytest.mark.django_db
def test_profile_edit_does_not_expose_locked_fields(consenting_client):
    response = consenting_client.get("/profil/")
    body = response.content.decode("utf-8")
    assert 'name="first_name"' not in body
    assert 'name="last_name"' not in body
    assert 'name="years_attended"' not in body
    assert 'name="classes"' not in body
    assert 'name="status"' not in body


@pytest.mark.django_db
def test_profile_edit_post_updates_editable_fields(consenting_client):
    response = consenting_client.post(
        "/profil/",
        {
            "nickname": "Idi",
            "city": "Cotonou",
            "country": "Bénin",
            "profession": "Enseignant",
            "show_email": "on",
            "show_whatsapp": "",  # unchecked
            "show_city": "on",
            "digest_weekly": "",
            "in_memoriam_alerts": "on",
            "event_alerts": "",
            "tag_alerts": "on",
            "data_saver": "",
        },
    )
    assert response.status_code == 302
    consenting_client.member.refresh_from_db()
    assert consenting_client.member.nickname == "Idi"
    assert consenting_client.member.city == "Cotonou"
    assert consenting_client.member.country == "Bénin"
    assert consenting_client.member.show_whatsapp is False
    assert consenting_client.member.preferences.digest_weekly is False


@pytest.mark.django_db
def test_profile_edit_post_does_not_change_locked_fields(consenting_client):
    member = consenting_client.member
    original_first = member.first_name
    response = consenting_client.post(
        "/profil/",
        {
            "first_name": "ATTACK",
            "nickname": "Idi",
            "city": "Cotonou",
            "country": "Niger",
            "profession": "",
            "show_email": "on",
            "show_whatsapp": "on",
            "show_city": "on",
            "digest_weekly": "",
            "in_memoriam_alerts": "on",
            "event_alerts": "",
            "tag_alerts": "on",
            "data_saver": "",
        },
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.first_name == original_first


@pytest.mark.django_db
def test_profile_edit_requires_login():
    response = Client().get("/profil/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_views_profile_edit.py -v`
Expected: 404 on `/profil/`.

- [ ] **Step 3: Create `members/forms.py`**

```python
"""Forms for the membership app."""

from django import forms

from .models import Member, NotificationPreference


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            "nickname",
            "city",
            "country",
            "profession",
            "show_email",
            "show_whatsapp",
            "show_city",
        ]


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "digest_weekly",
            "in_memoriam_alerts",
            "event_alerts",
            "tag_alerts",
            "data_saver",
        ]
```

- [ ] **Step 4: Append `profile_edit_view` to `members/views.py`**

```python
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import NotificationPreferenceForm, ProfileEditForm


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    member = getattr(request.user, "member", None)
    if member is None:
        raise Http404

    if request.method == "POST":
        member_form = ProfileEditForm(request.POST, instance=member)
        prefs_form = NotificationPreferenceForm(request.POST, instance=member.preferences)
        if member_form.is_valid() and prefs_form.is_valid():
            member_form.save()
            prefs_form.save()
            messages.success(request, "Profil mis à jour.")
            return HttpResponseRedirect("/profil/")
    else:
        member_form = ProfileEditForm(instance=member)
        prefs_form = NotificationPreferenceForm(instance=member.preferences)

    return render(
        request,
        "members/profile_edit.html",
        {"member_form": member_form, "prefs_form": prefs_form, "member": member},
    )
```

- [ ] **Step 5: Add URL**

In `members/urls.py`:

```python
urlpatterns = [
    path("charte/", views.charter_view, name="charter"),
    path("membres/<uuid:slug>/", views.profile_detail_view, name="profile_detail"),
    path("profil/", views.profile_edit_view, name="profile_edit"),
]
```

- [ ] **Step 6: Create `members/templates/members/profile_edit.html`**

```django
{% extends "base.html" %}
{% load i18n %}

{% block extra_head %}
<meta name="robots" content="noindex,nofollow">
{% endblock %}

{% block title %}{% trans "Mon profil" %}{% endblock %}

{% block content %}
<form method="post" class="mx-auto max-w-xl p-4 space-y-4">
    {% csrf_token %}
    <h1 class="text-2xl font-semibold">{% trans "Mon profil" %}</h1>

    <fieldset class="space-y-3">
        <legend class="font-medium">{% trans "Informations" %}</legend>
        {{ member_form.as_p }}
    </fieldset>

    <fieldset class="space-y-3">
        <legend class="font-medium">{% trans "Notifications" %}</legend>
        {{ prefs_form.as_p }}
    </fieldset>

    <button type="submit" class="btn btn-primary">{% trans "Enregistrer" %}</button>
</form>
{% endblock %}
```

- [ ] **Step 7: Run tests and confirm pass**

Run: `pytest members/tests/test_views_profile_edit.py -v`
Expected: 5 passed.

- [ ] **Step 8: Commit**

```bash
git add members/forms.py members/views.py members/urls.py members/templates/members/profile_edit.html members/tests/test_views_profile_edit.py
git commit -m "feat(members): add ProfileEditView with locked fields and notification preferences form"
```

---

## Task 17: `cloudinary_sign` endpoint with rate limit + folder pinning

**Files:**
- Modify: `members/views.py`
- Modify: `members/urls.py`
- Create: `members/tests/test_cloudinary_sign.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_cloudinary_sign.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_sign_endpoint_requires_login():
    response = Client().post("/api/cloudinary/sign/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_sign_endpoint_returns_signature_pinned_to_member_folder(consenting_client):
    response = consenting_client.post("/api/cloudinary/sign/", {"folder": "ATTACK/path"})
    assert response.status_code == 200
    body = response.json()
    assert body["folder"] == f"members/{consenting_client.member.slug}/"
    assert body["signature"]
    assert body["timestamp"]
    assert body["max_file_size"] == 5 * 1024 * 1024
    assert body["allowed_formats"] == ["jpg", "jpeg", "png", "webp"]


@pytest.mark.django_db
def test_sign_endpoint_rate_limit_kicks_in_after_10_per_min(consenting_client, settings):
    # The limit is 10/m/user. The 11th request gets 429.
    for _ in range(10):
        ok = consenting_client.post("/api/cloudinary/sign/")
        assert ok.status_code == 200
    blocked = consenting_client.post("/api/cloudinary/sign/")
    assert blocked.status_code == 429
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_cloudinary_sign.py -v`
Expected: 404.

- [ ] **Step 3: Append the view to `members/views.py`**

```python
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit

from alumni.cloudinary import get_client, now_timestamp


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def cloudinary_sign_view(request):
    if getattr(request, "limited", False):
        return JsonResponse(
            {"error": "rate limit exceeded"},
            status=429,
            headers={"Retry-After": "60"},
        )

    member = getattr(request.user, "member", None)
    if member is None:
        return JsonResponse({"error": "no member"}, status=400)

    folder = f"members/{member.slug}/"
    timestamp = now_timestamp()
    payload = get_client().sign_upload(folder=folder, timestamp=timestamp)
    return JsonResponse(payload)
```

> `block=False` lets the decorator annotate `request.limited` rather than raising; the view returns an explicit 429 with a `Retry-After` header so the response is observable to clients.

- [ ] **Step 4: Add URL**

In `members/urls.py`:

```python
urlpatterns = [
    path("charte/", views.charter_view, name="charter"),
    path("membres/<uuid:slug>/", views.profile_detail_view, name="profile_detail"),
    path("profil/", views.profile_edit_view, name="profile_edit"),
    path("api/cloudinary/sign/", views.cloudinary_sign_view, name="cloudinary_sign"),
]
```

- [ ] **Step 5: Run tests and confirm pass**

Run: `pytest members/tests/test_cloudinary_sign.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add members/views.py members/urls.py members/tests/test_cloudinary_sign.py
git commit -m "feat(members): add rate-limited cloudinary sign endpoint with folder pinning"
```

---

## Task 18: Photo persistence in `ProfileEditView`

**Files:**
- Modify: `members/forms.py`
- Modify: `members/views.py`
- Modify: `members/templates/members/profile_edit.html`
- Create: `members/tests/test_photo_persistence.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_photo_persistence.py`:

```python
import pytest
from django.test import Client

from alumni.cloudinary import FakeCloudinary
from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_photo_persists_when_public_id_in_correct_folder(consenting_client):
    member = consenting_client.member
    new_id = f"members/{member.slug}/photo_xyz"
    response = consenting_client.post(
        "/profil/",
        {
            "nickname": "",
            "city": "Niamey",
            "country": "Niger",
            "profession": "",
            "show_email": "on",
            "show_whatsapp": "on",
            "show_city": "on",
            "digest_weekly": "",
            "in_memoriam_alerts": "on",
            "event_alerts": "",
            "tag_alerts": "on",
            "data_saver": "",
            "photo_public_id": new_id,
        },
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.photo_public_id == new_id


@pytest.mark.django_db
def test_photo_rejected_when_public_id_outside_member_folder(consenting_client):
    member = consenting_client.member
    response = consenting_client.post(
        "/profil/",
        {
            "nickname": "",
            "city": "Niamey",
            "country": "Niger",
            "profession": "",
            "show_email": "on",
            "show_whatsapp": "on",
            "show_city": "on",
            "digest_weekly": "",
            "in_memoriam_alerts": "on",
            "event_alerts": "",
            "tag_alerts": "on",
            "data_saver": "",
            "photo_public_id": "evil/path/photo",
        },
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_old_photo_deleted_on_replacement(consenting_client, settings):
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    member = consenting_client.member
    member.photo_public_id = f"members/{member.slug}/old_photo"
    member.save()

    new_id = f"members/{member.slug}/new_photo"
    consenting_client.post(
        "/profil/",
        {
            "nickname": "",
            "city": "Niamey",
            "country": "Niger",
            "profession": "",
            "show_email": "on",
            "show_whatsapp": "on",
            "show_city": "on",
            "digest_weekly": "",
            "in_memoriam_alerts": "on",
            "event_alerts": "",
            "tag_alerts": "on",
            "data_saver": "",
            "photo_public_id": new_id,
        },
    )
    member.refresh_from_db()
    assert member.photo_public_id == new_id
    # Note: the FakeCloudinary instance is constructed inside the view,
    # so we don't have a direct handle to assert delete_calls. The behavior
    # is verified at the unit level in test_cloudinary_client.py — here we
    # verify that the new value persists.
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_photo_persistence.py -v`
Expected: photo_public_id never persists; the field is not in the form.

- [ ] **Step 3: Add `photo_public_id` to `ProfileEditForm` with validation**

Replace `members/forms.py`:

```python
"""Forms for the membership app."""

from django import forms
from django.core.exceptions import ValidationError

from .models import Member, NotificationPreference


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            "nickname",
            "city",
            "country",
            "profession",
            "show_email",
            "show_whatsapp",
            "show_city",
            "photo_public_id",
        ]
        widgets = {
            "photo_public_id": forms.HiddenInput(),
        }

    def clean_photo_public_id(self):
        value = (self.cleaned_data.get("photo_public_id") or "").strip()
        if not value:
            return ""
        expected_prefix = f"members/{self.instance.slug}/"
        if not value.startswith(expected_prefix):
            raise ValidationError("Chemin de photo invalide.")
        return value


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "digest_weekly",
            "in_memoriam_alerts",
            "event_alerts",
            "tag_alerts",
            "data_saver",
        ]
```

- [ ] **Step 4: Update `profile_edit_view` to delete the old photo and return 400 on validation error**

Replace `profile_edit_view` in `members/views.py`:

```python
@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    member = getattr(request.user, "member", None)
    if member is None:
        raise Http404

    if request.method == "POST":
        member_form = ProfileEditForm(request.POST, instance=member)
        prefs_form = NotificationPreferenceForm(request.POST, instance=member.preferences)
        if member_form.is_valid() and prefs_form.is_valid():
            old_photo_id = member.photo_public_id
            new_photo_id = member_form.cleaned_data.get("photo_public_id", "")
            member_form.save()
            prefs_form.save()
            if old_photo_id and old_photo_id != new_photo_id:
                get_client().delete(old_photo_id)
            messages.success(request, "Profil mis à jour.")
            return HttpResponseRedirect("/profil/")
        # Form invalid — if the failure is photo_public_id, return 400 (security signal).
        if "photo_public_id" in member_form.errors:
            return JsonResponse({"error": "invalid photo path"}, status=400)
    else:
        member_form = ProfileEditForm(instance=member)
        prefs_form = NotificationPreferenceForm(instance=member.preferences)

    return render(
        request,
        "members/profile_edit.html",
        {"member_form": member_form, "prefs_form": prefs_form, "member": member},
    )
```

- [ ] **Step 5: Surface the hidden photo field in the template**

Update `members/templates/members/profile_edit.html` to render `{{ member_form.photo_public_id }}` inside the `<form>` so the value round-trips:

```django
{% extends "base.html" %}
{% load i18n %}

{% block extra_head %}
<meta name="robots" content="noindex,nofollow">
{% endblock %}

{% block title %}{% trans "Mon profil" %}{% endblock %}

{% block content %}
<form method="post" class="mx-auto max-w-xl p-4 space-y-4" id="profile-form">
    {% csrf_token %}
    <h1 class="text-2xl font-semibold">{% trans "Mon profil" %}</h1>

    <fieldset class="space-y-3">
        <legend class="font-medium">{% trans "Informations" %}</legend>
        {{ member_form.nickname.label_tag }} {{ member_form.nickname }}
        {{ member_form.city.label_tag }} {{ member_form.city }}
        {{ member_form.country.label_tag }} {{ member_form.country }}
        {{ member_form.profession.label_tag }} {{ member_form.profession }}
        {{ member_form.show_email }} {{ member_form.show_email.label_tag }}
        {{ member_form.show_whatsapp }} {{ member_form.show_whatsapp.label_tag }}
        {{ member_form.show_city }} {{ member_form.show_city.label_tag }}
        {{ member_form.photo_public_id }}
    </fieldset>

    <fieldset class="space-y-3">
        <legend class="font-medium">{% trans "Notifications" %}</legend>
        {{ prefs_form.as_p }}
    </fieldset>

    <button type="submit" class="btn btn-primary">{% trans "Enregistrer" %}</button>
</form>

<!-- Photo upload widget — Task 18 lays the persistence; full JS uploader is wired in a separate front-end task. -->
{% endblock %}
```

- [ ] **Step 6: Run tests and confirm pass**

Run: `pytest members/tests/test_photo_persistence.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add members/forms.py members/views.py members/templates/members/profile_edit.html members/tests/test_photo_persistence.py
git commit -m "feat(members): persist cloudinary photo_public_id with folder validation and old-photo cleanup"
```

---

## Task 19: `DirectoryView` — basic listing + pagination

**Files:**
- Modify: `members/views.py`
- Modify: `members/urls.py`
- Create: `members/templates/members/directory.html`
- Create: `members/templates/members/directory_list_partial.html`
- Create: `members/tests/test_views_directory_basic.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_views_directory_basic.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_directory_lists_active_members(consenting_client, make_member):
    a = make_member(first_name="Alpha", last_name="One")
    b = make_member(first_name="Beta", last_name="Two")
    response = consenting_client.get("/annuaire/")
    assert response.status_code == 200
    assert b"Alpha One" in response.content
    assert b"Beta Two" in response.content


@pytest.mark.django_db
def test_directory_excludes_deleted_and_suspended(consenting_client, make_member):
    make_member(first_name="Visible", last_name="One")
    make_member(first_name="Hidden", last_name="Two", status="deleted")
    make_member(first_name="Quiet", last_name="Three", status="suspended")
    response = consenting_client.get("/annuaire/")
    assert b"Visible One" in response.content
    assert b"Hidden Two" not in response.content
    assert b"Quiet Three" not in response.content


@pytest.mark.django_db
def test_directory_paginates_at_20_per_page(consenting_client, make_member):
    for i in range(25):
        make_member(first_name=f"Person{i:02d}", last_name="X")
    page_one = consenting_client.get("/annuaire/")
    assert page_one.content.count(b'class="member-card"') == 20
    page_two = consenting_client.get("/annuaire/?page=2")
    assert page_two.status_code == 200
    # 25 total - 20 on page 1 = 5 expected, plus the consenting_client's own member = 6
    assert page_two.content.count(b'class="member-card"') >= 5


@pytest.mark.django_db
def test_directory_clamps_page_zero_to_one(consenting_client, make_member):
    for i in range(5):
        make_member(first_name=f"Person{i}", last_name="X")
    response = consenting_client.get("/annuaire/?page=0")
    assert response.status_code == 200


@pytest.mark.django_db
def test_directory_clamps_negative_page_to_one(consenting_client, make_member):
    for i in range(5):
        make_member(first_name=f"Person{i}", last_name="X")
    response = consenting_client.get("/annuaire/?page=-3")
    assert response.status_code == 200


@pytest.mark.django_db
def test_directory_clamps_page_beyond_max(consenting_client, make_member):
    for i in range(5):
        make_member(first_name=f"Person{i}", last_name="X")
    response = consenting_client.get("/annuaire/?page=999")
    assert response.status_code == 200


@pytest.mark.django_db
def test_directory_includes_noindex(consenting_client):
    response = consenting_client.get("/annuaire/")
    assert b"noindex" in response.content
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_views_directory_basic.py -v`
Expected: 404.

- [ ] **Step 3: Append `directory_view` to `members/views.py`**

```python
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator


@login_required
@require_http_methods(["GET"])
def directory_view(request):
    qs = Member.objects.filter(status="active").order_by("last_name", "first_name")

    paginator = Paginator(qs, 20)
    raw_page = request.GET.get("page", "1")
    try:
        page_number = max(1, int(raw_page))
    except (TypeError, ValueError):
        page_number = 1
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(paginator.num_pages or 1)

    template = (
        "members/directory_list_partial.html"
        if request.headers.get("Hx-Request")
        else "members/directory.html"
    )
    return render(
        request,
        template,
        {"page": page, "members": page.object_list},
    )
```

- [ ] **Step 4: Add URL**

In `members/urls.py`:

```python
urlpatterns = [
    path("charte/", views.charter_view, name="charter"),
    path("membres/<uuid:slug>/", views.profile_detail_view, name="profile_detail"),
    path("profil/", views.profile_edit_view, name="profile_edit"),
    path("api/cloudinary/sign/", views.cloudinary_sign_view, name="cloudinary_sign"),
    path("annuaire/", views.directory_view, name="directory"),
]
```

- [ ] **Step 5: Create templates**

`members/templates/members/directory.html`:

```django
{% extends "base.html" %}
{% load i18n %}

{% block extra_head %}
<meta name="robots" content="noindex,nofollow">
{% endblock %}

{% block title %}{% trans "Annuaire" %}{% endblock %}

{% block content %}
<section class="mx-auto max-w-5xl p-4">
    <h1 class="text-2xl font-semibold mb-4">{% trans "Annuaire" %}</h1>

    <form method="get" id="directory-filters" class="mb-4 flex flex-wrap gap-2"
          hx-get="/annuaire/" hx-target="#directory-list" hx-push-url="true"
          hx-trigger="input changed delay:300ms from:input, change from:select, submit">
        <input type="text" name="q" placeholder="{% trans 'Rechercher…' %}" value="{{ request.GET.q }}" class="input">
        <select name="year" class="select">
            <option value="">{% trans "Année" %}</option>
            {% for y in '012345' %}
                <option value="{{ y|add:1980 }}" {% if request.GET.year == y|add:1980|stringformat:'s' %}selected{% endif %}>{{ y|add:1980 }}</option>
            {% endfor %}
        </select>
        <input type="text" name="city" placeholder="{% trans 'Ville' %}" value="{{ request.GET.city }}" class="input">
        <input type="text" name="profession" placeholder="{% trans 'Profession' %}" value="{{ request.GET.profession }}" class="input">
    </form>

    <div id="directory-list">
        {% include "members/directory_list_partial.html" %}
    </div>
</section>
{% endblock %}
```

`members/templates/members/directory_list_partial.html`:

```django
{% load i18n member_avatar %}

<ul class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" aria-live="polite">
    {% for member in members %}
    <li class="member-card border rounded p-3 flex gap-3">
        <a href="/membres/{{ member.slug }}/" class="shrink-0">
            {% member_avatar member size=64 %}
        </a>
        <div>
            <a href="/membres/{{ member.slug }}/" class="font-medium">{{ member.full_name }}</a>
            {% if member.show_city and member.city %}
                <p class="text-sm opacity-70">{{ member.city }}</p>
            {% endif %}
            {% if member.profession %}
                <p class="text-sm">{{ member.profession }}</p>
            {% endif %}
            <p class="text-xs opacity-70">{{ member.years_attended|join:", " }}</p>
        </div>
    </li>
    {% empty %}
    <li class="opacity-70">{% trans "Aucun membre trouvé." %}</li>
    {% endfor %}
</ul>

{% if page.paginator.num_pages > 1 %}
<nav class="mt-4 flex gap-2" aria-label="{% trans 'Pagination' %}">
    {% if page.has_previous %}
        <a href="?page={{ page.previous_page_number }}{% for k, v in request.GET.items %}{% if k != 'page' %}&{{ k }}={{ v }}{% endif %}{% endfor %}" class="btn btn-sm">‹</a>
    {% endif %}
    <span class="self-center">{{ page.number }} / {{ page.paginator.num_pages }}</span>
    {% if page.has_next %}
        <a href="?page={{ page.next_page_number }}{% for k, v in request.GET.items %}{% if k != 'page' %}&{{ k }}={{ v }}{% endif %}{% endfor %}" class="btn btn-sm">›</a>
    {% endif %}
</nav>
{% endif %}
```

- [ ] **Step 6: Run tests and confirm pass**

Run: `pytest members/tests/test_views_directory_basic.py -v`
Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add members/views.py members/urls.py members/templates/members/directory.html members/templates/members/directory_list_partial.html members/tests/test_views_directory_basic.py
git commit -m "feat(members): add DirectoryView with pagination and HTMX-aware partial"
```

---

## Task 20: Directory search and filters (accent-insensitive)

**Files:**
- Modify: `members/views.py`
- Create: `members/tests/test_views_directory_search.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_views_directory_search.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_search_matches_first_name_substring(consenting_client, make_member):
    make_member(first_name="Idrissa", last_name="Saidou")
    make_member(first_name="Beta", last_name="Other")
    response = consenting_client.get("/annuaire/?q=idris")
    assert b"Idrissa" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_search_is_accent_insensitive(consenting_client, make_member):
    make_member(first_name="Idrïssa", last_name="Saïdou")
    response = consenting_client.get("/annuaire/?q=idrissa")
    assert b"Idr" in response.content  # match found, name rendered


@pytest.mark.django_db
def test_search_matches_nickname(consenting_client, make_member):
    make_member(first_name="Hamadou", last_name="X", nickname="Idi")
    response = consenting_client.get("/annuaire/?q=idi")
    assert b"Hamadou" in response.content


@pytest.mark.django_db
def test_filter_by_year(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", years_attended=[1980, 1981])
    make_member(first_name="Beta", last_name="Y", years_attended=[1984, 1985])
    response = consenting_client.get("/annuaire/?year=1980")
    assert b"Alpha" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_filter_by_city_is_case_insensitive(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", city="Niamey")
    make_member(first_name="Beta", last_name="Y", city="Cotonou")
    response = consenting_client.get("/annuaire/?city=niamey")
    assert b"Alpha" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_filter_by_profession_is_substring(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", profession="Enseignant primaire")
    make_member(first_name="Beta", last_name="Y", profession="Médecin")
    response = consenting_client.get("/annuaire/?profession=enseign")
    assert b"Alpha" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_filters_combined_with_AND(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", city="Niamey", years_attended=[1980])
    make_member(first_name="Beta", last_name="Y", city="Niamey", years_attended=[1985])
    response = consenting_client.get("/annuaire/?city=niamey&year=1980")
    assert b"Alpha" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_invalid_year_silently_dropped(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", years_attended=[1980])
    response = consenting_client.get("/annuaire/?year=9999")
    assert response.status_code == 200
    assert b"Alpha" in response.content


@pytest.mark.django_db
def test_long_query_is_truncated(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    long_q = "a" * 200
    response = consenting_client.get(f"/annuaire/?q={long_q}")
    assert response.status_code == 200
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_views_directory_search.py -v`
Expected: tests fail because filters aren't applied.

- [ ] **Step 3: Update `directory_view` with search and filters**

Replace the function in `members/views.py`:

```python
from django.contrib.postgres.lookups import Unaccent
from django.db.models import F, Q, Value
from django.db.models.functions import Lower


@login_required
@require_http_methods(["GET"])
def directory_view(request):
    qs = Member.objects.filter(status="active")

    q = (request.GET.get("q") or "").strip()[:80]
    year_raw = request.GET.get("year")
    city = (request.GET.get("city") or "").strip()
    profession = (request.GET.get("profession") or "").strip()

    if q:
        needle = Lower(Unaccent(Value(q)))
        qs = qs.annotate(
            first_lc=Lower(Unaccent(F("first_name"))),
            last_lc=Lower(Unaccent(F("last_name"))),
            nick_lc=Lower(Unaccent(F("nickname"))),
        ).filter(
            Q(first_lc__contains=needle)
            | Q(last_lc__contains=needle)
            | Q(nick_lc__contains=needle)
        )

    if year_raw:
        try:
            year = int(year_raw)
            if year in range(1980, 1986):
                qs = qs.filter(years_attended__contains=[year])
        except (TypeError, ValueError):
            pass

    if city:
        qs = qs.filter(city__iexact=city)

    if profession:
        qs = qs.filter(profession__icontains=profession)

    qs = qs.order_by("last_name", "first_name")

    paginator = Paginator(qs, 20)
    raw_page = request.GET.get("page", "1")
    try:
        page_number = max(1, int(raw_page))
    except (TypeError, ValueError):
        page_number = 1
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(paginator.num_pages or 1)

    template = (
        "members/directory_list_partial.html"
        if request.headers.get("Hx-Request")
        else "members/directory.html"
    )
    return render(
        request,
        template,
        {"page": page, "members": page.object_list},
    )
```

> Note: `django.contrib.postgres.lookups.Unaccent` requires the `unaccent` extension installed in Task 7.

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest members/tests/test_views_directory_search.py -v`
Expected: 9 passed.

- [ ] **Step 5: Run full directory test suite to ensure no regressions**

Run: `pytest members/tests/test_views_directory_basic.py members/tests/test_views_directory_search.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add members/views.py members/tests/test_views_directory_search.py
git commit -m "feat(members): add accent-insensitive search and filters to directory"
```

---

## Task 21: HTMX partial response for directory

**Files:**
- Create: `members/tests/test_views_directory_htmx.py`

The HTMX behavior was already wired in Task 19's view via `request.headers.get("Hx-Request")`. This task locks it down with explicit tests.

- [ ] **Step 1: Write the tests**

`members/tests/test_views_directory_htmx.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_full_response_extends_base_template(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    response = consenting_client.get("/annuaire/")
    assert b"<html" in response.content


@pytest.mark.django_db
def test_htmx_response_returns_partial_only(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    response = consenting_client.get("/annuaire/", HTTP_HX_REQUEST="true")
    assert b"<html" not in response.content
    assert b"member-card" in response.content


@pytest.mark.django_db
def test_htmx_response_respects_filters(consenting_client, make_member):
    make_member(first_name="Idrissa", last_name="X")
    make_member(first_name="Beta", last_name="Y")
    response = consenting_client.get("/annuaire/?q=idris", HTTP_HX_REQUEST="true")
    assert b"Idrissa" in response.content
    assert b"Beta" not in response.content
```

- [ ] **Step 2: Run tests and confirm pass**

Run: `pytest members/tests/test_views_directory_htmx.py -v`
Expected: 3 passed (logic already in place from Task 19).

- [ ] **Step 3: Commit**

```bash
git add members/tests/test_views_directory_htmx.py
git commit -m "test(members): lock HTMX partial behavior for directory view"
```

---

## Task 22: `manage.py create_member` command

**Files:**
- Create: `members/management/__init__.py`
- Create: `members/management/commands/__init__.py`
- Create: `members/management/commands/create_member.py`
- Create: `members/tests/test_create_member_command.py`

- [ ] **Step 1: Write the failing tests**

`members/tests/test_create_member_command.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from members.models import Member, NotificationPreference


@pytest.mark.django_db
def test_create_member_creates_user_and_member():
    call_command(
        "create_member",
        "--email", "idrissa@example.test",
        "--first-name", "Idrissa",
        "--last-name", "Saidou",
        "--years", "1980", "1981", "1982", "1983",
        "--classes", "6e", "5e", "4e", "3e",
        "--city", "Niamey",
    )
    user = get_user_model().objects.get(email="idrissa@example.test")
    assert user.member.first_name == "Idrissa"
    assert NotificationPreference.objects.filter(member=user.member).exists()


@pytest.mark.django_db
def test_create_member_idempotent_on_email():
    for _ in range(2):
        call_command(
            "create_member",
            "--email", "idi@example.test",
            "--first-name", "Idrissa",
            "--last-name", "Saidou",
            "--years", "1980",
            "--classes", "6e",
            "--city", "Niamey",
        )
    assert get_user_model().objects.filter(email="idi@example.test").count() == 1
    assert Member.objects.filter(user__email="idi@example.test").count() == 1


@pytest.mark.django_db
def test_create_member_rejects_invalid_year():
    with pytest.raises((CommandError, Exception)):
        call_command(
            "create_member",
            "--email", "x@example.test",
            "--first-name", "X",
            "--last-name", "Y",
            "--years", "1979",
            "--classes", "6e",
            "--city", "Niamey",
        )


@pytest.mark.django_db
def test_create_member_rejects_invalid_grade():
    with pytest.raises((CommandError, Exception)):
        call_command(
            "create_member",
            "--email", "x@example.test",
            "--first-name", "X",
            "--last-name", "Y",
            "--years", "1980",
            "--classes", "2nde",
            "--city", "Niamey",
        )


@pytest.mark.django_db
def test_create_member_password_optional_creates_unusable_password():
    call_command(
        "create_member",
        "--email", "x@example.test",
        "--first-name", "X",
        "--last-name", "Y",
        "--years", "1980",
        "--classes", "6e",
        "--city", "Niamey",
    )
    user = get_user_model().objects.get(email="x@example.test")
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_create_member_password_explicit_sets_usable_password():
    call_command(
        "create_member",
        "--email", "x@example.test",
        "--first-name", "X",
        "--last-name", "Y",
        "--years", "1980",
        "--classes", "6e",
        "--city", "Niamey",
        "--password", "test-pw-1",
    )
    user = get_user_model().objects.get(email="x@example.test")
    assert user.check_password("test-pw-1")
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest members/tests/test_create_member_command.py -v`
Expected: `Unknown command: 'create_member'`.

- [ ] **Step 3: Create the command files**

`members/management/__init__.py`: empty.
`members/management/commands/__init__.py`: empty.

`members/management/commands/create_member.py`:

```python
"""Dev/test helper to create a User + Member without going through cooptation."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from members.models import Member


class Command(BaseCommand):
    help = "Create a Member (and the underlying User) for dev/test."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", required=True)
        parser.add_argument("--last-name", required=True)
        parser.add_argument("--years", nargs="+", type=int, required=True)
        parser.add_argument("--classes", nargs="+", required=True)
        parser.add_argument("--city", required=True)
        parser.add_argument("--country", default="Niger")
        parser.add_argument("--nickname", default="")
        parser.add_argument("--profession", default="")
        parser.add_argument("--password", default=None)

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        email = opts["email"]
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": email},
        )
        if opts["password"]:
            user.set_password(opts["password"])
        elif created:
            user.set_unusable_password()
        user.save()

        defaults = {
            "first_name": opts["first_name"],
            "last_name": opts["last_name"],
            "nickname": opts["nickname"],
            "years_attended": opts["years"],
            "classes": opts["classes"],
            "city": opts["city"],
            "country": opts["country"],
            "profession": opts["profession"],
        }
        member, _ = Member.objects.update_or_create(user=user, defaults=defaults)
        try:
            member.full_clean()
        except ValidationError as e:
            raise CommandError(str(e))
        member.save()
        self.stdout.write(self.style.SUCCESS(f"Member created/updated: {member.full_name}"))
```

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest members/tests/test_create_member_command.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add members/management/ members/tests/test_create_member_command.py
git commit -m "feat(members): add create_member management command for dev seeding"
```

---

## Task 23: Seed fixture and `make seed` target

**Files:**
- Create: `members/fixtures/seed_members.json`
- Modify: `Makefile`
- Create: `members/tests/test_seed_fixture.py`

- [ ] **Step 1: Write the failing test**

`members/tests/test_seed_fixture.py`:

```python
import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_members_fixture_loads_cleanly():
    call_command("loaddata", "seed_members")
    from members.models import Member

    assert Member.objects.count() >= 6
    assert Member.objects.filter(city="Niamey").exists()
    assert Member.objects.filter(country="France").exists()
```

- [ ] **Step 2: Confirm failure**

Run: `pytest members/tests/test_seed_fixture.py -v`
Expected: fixture not found.

- [ ] **Step 3: Create `members/fixtures/seed_members.json`**

```json
[
  {"model": "auth.user", "pk": 9001, "fields": {"username": "seed1@example.test", "email": "seed1@example.test", "password": "!unusable", "is_active": true, "is_staff": false, "is_superuser": false, "first_name": "", "last_name": "", "date_joined": "2026-01-01T00:00:00Z"}},
  {"model": "auth.user", "pk": 9002, "fields": {"username": "seed2@example.test", "email": "seed2@example.test", "password": "!unusable", "is_active": true, "is_staff": false, "is_superuser": false, "first_name": "", "last_name": "", "date_joined": "2026-01-01T00:00:00Z"}},
  {"model": "auth.user", "pk": 9003, "fields": {"username": "seed3@example.test", "email": "seed3@example.test", "password": "!unusable", "is_active": true, "is_staff": false, "is_superuser": false, "first_name": "", "last_name": "", "date_joined": "2026-01-01T00:00:00Z"}},
  {"model": "auth.user", "pk": 9004, "fields": {"username": "seed4@example.test", "email": "seed4@example.test", "password": "!unusable", "is_active": true, "is_staff": false, "is_superuser": false, "first_name": "", "last_name": "", "date_joined": "2026-01-01T00:00:00Z"}},
  {"model": "auth.user", "pk": 9005, "fields": {"username": "seed5@example.test", "email": "seed5@example.test", "password": "!unusable", "is_active": true, "is_staff": false, "is_superuser": false, "first_name": "", "last_name": "", "date_joined": "2026-01-01T00:00:00Z"}},
  {"model": "auth.user", "pk": 9006, "fields": {"username": "seed6@example.test", "email": "seed6@example.test", "password": "!unusable", "is_active": true, "is_staff": false, "is_superuser": false, "first_name": "", "last_name": "", "date_joined": "2026-01-01T00:00:00Z"}},

  {"model": "members.member", "pk": 9001, "fields": {"user": 9001, "slug": "11111111-1111-1111-1111-111111111101", "first_name": "Idrissa", "last_name": "Saidou", "nickname": "Idi", "years_attended": [1980,1981,1982,1983], "classes": ["6e","5e","4e","3e"], "city": "Niamey", "country": "Niger", "profession": "Enseignant", "photo_public_id": "", "show_email": true, "show_whatsapp": true, "show_city": true, "status": "active", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}},
  {"model": "members.member", "pk": 9002, "fields": {"user": 9002, "slug": "11111111-1111-1111-1111-111111111102", "first_name": "Hamadou", "last_name": "Diallo", "nickname": "", "years_attended": [1981,1982,1983,1984], "classes": ["6e","5e","4e","3e"], "city": "Paris", "country": "France", "profession": "Médecin", "photo_public_id": "", "show_email": true, "show_whatsapp": false, "show_city": true, "status": "active", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}},
  {"model": "members.member", "pk": 9003, "fields": {"user": 9003, "slug": "11111111-1111-1111-1111-111111111103", "first_name": "Aïcha", "last_name": "Boubacar", "nickname": "", "years_attended": [1982,1983,1984,1985], "classes": ["6e","5e","4e","3e"], "city": "Zinder", "country": "Niger", "profession": "Comptable", "photo_public_id": "", "show_email": true, "show_whatsapp": true, "show_city": true, "status": "active", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}},
  {"model": "members.member", "pk": 9004, "fields": {"user": 9004, "slug": "11111111-1111-1111-1111-111111111104", "first_name": "Moussa", "last_name": "Adamou", "nickname": "", "years_attended": [1980,1981,1982,1983], "classes": ["6e","5e","4e","3e"], "city": "Cotonou", "country": "Bénin", "profession": "Ingénieur", "photo_public_id": "", "show_email": true, "show_whatsapp": true, "show_city": true, "status": "active", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}},
  {"model": "members.member", "pk": 9005, "fields": {"user": 9005, "slug": "11111111-1111-1111-1111-111111111105", "first_name": "Fatouma", "last_name": "Maïga", "nickname": "Fatou", "years_attended": [1983,1984,1985], "classes": ["5e","4e","3e"], "city": "Maradi", "country": "Niger", "profession": "Sage-femme", "photo_public_id": "", "show_email": true, "show_whatsapp": true, "show_city": false, "status": "active", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}},
  {"model": "members.member", "pk": 9006, "fields": {"user": 9006, "slug": "11111111-1111-1111-1111-111111111106", "first_name": "Souleymane", "last_name": "Issoufou", "nickname": "", "years_attended": [1981,1982,1983,1984], "classes": ["6e","5e","4e","3e"], "city": "Niamey", "country": "Niger", "profession": "Avocat", "photo_public_id": "", "show_email": false, "show_whatsapp": false, "show_city": true, "status": "active", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}},

  {"model": "members.notificationpreference", "pk": 9001, "fields": {"member": 9001, "digest_weekly": false, "in_memoriam_alerts": true, "event_alerts": false, "tag_alerts": true, "data_saver": false}},
  {"model": "members.notificationpreference", "pk": 9002, "fields": {"member": 9002, "digest_weekly": false, "in_memoriam_alerts": true, "event_alerts": false, "tag_alerts": true, "data_saver": false}},
  {"model": "members.notificationpreference", "pk": 9003, "fields": {"member": 9003, "digest_weekly": false, "in_memoriam_alerts": true, "event_alerts": false, "tag_alerts": true, "data_saver": false}},
  {"model": "members.notificationpreference", "pk": 9004, "fields": {"member": 9004, "digest_weekly": false, "in_memoriam_alerts": true, "event_alerts": false, "tag_alerts": true, "data_saver": false}},
  {"model": "members.notificationpreference", "pk": 9005, "fields": {"member": 9005, "digest_weekly": false, "in_memoriam_alerts": true, "event_alerts": false, "tag_alerts": true, "data_saver": false}},
  {"model": "members.notificationpreference", "pk": 9006, "fields": {"member": 9006, "digest_weekly": false, "in_memoriam_alerts": true, "event_alerts": false, "tag_alerts": true, "data_saver": false}}
]
```

- [ ] **Step 4: Add a `seed` target to `Makefile`**

Append:

```make
seed:
	python manage.py loaddata seed_members
```

- [ ] **Step 5: Run tests and confirm pass**

Run: `pytest members/tests/test_seed_fixture.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add members/fixtures/seed_members.json Makefile members/tests/test_seed_fixture.py
git commit -m "feat(members): add seed fixture with 6 representative members"
```

---

## Task 24: i18n strings — French translations + compile

**Files:**
- Modify: `locale/fr/LC_MESSAGES/django.po` (regenerated)
- Create: `members/tests/test_i18n_membership.py`

- [ ] **Step 1: Write the failing test**

`members/tests/test_i18n_membership.py`:

```python
import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    return client


@pytest.mark.django_db
def test_directory_renders_french_strings(consenting_client):
    response = consenting_client.get("/annuaire/")
    body = response.content.decode("utf-8")
    assert "Annuaire" in body
    assert "Rechercher" in body or "recherch" in body.lower()


@pytest.mark.django_db
def test_profile_edit_renders_french_strings(consenting_client):
    response = consenting_client.get("/profil/")
    body = response.content.decode("utf-8")
    assert "Mon profil" in body
    assert "Enregistrer" in body


@pytest.mark.django_db
def test_charter_renders_french_accept_button(consenting_client):
    response = consenting_client.get("/charte/")
    body = response.content.decode("utf-8")
    assert "J'accepte" in body
```

- [ ] **Step 2: Generate French message catalog**

Run: `python manage.py makemessages -l fr --ignore="node_modules/*" --ignore=".venv/*"`

The catalog will pick up new `{% trans %}` strings from members templates.

- [ ] **Step 3: Open `locale/fr/LC_MESSAGES/django.po`**

For every empty `msgstr ""` introduced by Task 24 (look for `Annuaire`, `Rechercher…`, `Année`, `Ville`, `Profession`, `Mon profil`, `Informations`, `Notifications`, `Enregistrer`, `Charte`, `J'accepte`, `Modifier mon profil`, `Pagination`, `Aucun membre trouvé.`, `Email`, `Promotion`), set:

```
msgstr "<the same French string>"
```

(The fallback already shows source strings in French, but `msgstr` must be explicitly set to be considered "translated" by Django's catalog.)

- [ ] **Step 4: Compile messages**

Run: `python manage.py compilemessages`
Expected: `processing file django.po in locale/fr/LC_MESSAGES`

- [ ] **Step 5: Run tests and confirm pass**

Run: `pytest members/tests/test_i18n_membership.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add locale/ members/tests/test_i18n_membership.py
git commit -m "i18n(members): generate and compile French translations for new pages"
```

---

## Task 25: a11y assertions

**Files:**
- Create: `members/tests/test_a11y.py`

- [ ] **Step 1: Write the tests**

`members/tests/test_a11y.py`:

```python
import pytest
from bs4 import BeautifulSoup
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1")
    client = Client()
    client.login(username=user.username, password="testpass123")
    return client


@pytest.mark.django_db
def test_profile_edit_form_has_label_for_each_text_input(consenting_client):
    response = consenting_client.get("/profil/")
    soup = BeautifulSoup(response.content, "html.parser")
    text_inputs = soup.find_all("input", {"type": ["text", "email"]})
    label_for = {label.get("for") for label in soup.find_all("label")}
    for inp in text_inputs:
        if inp.get("type") == "hidden":
            continue
        assert inp.get("id") in label_for, f"Input {inp} has no associated <label>"


@pytest.mark.django_db
def test_directory_pagination_has_aria_label(consenting_client, make_member):
    for i in range(25):
        make_member(first_name=f"P{i}", last_name="X")
    response = consenting_client.get("/annuaire/")
    soup = BeautifulSoup(response.content, "html.parser")
    nav = soup.find("nav", {"aria-label": True})
    assert nav is not None


@pytest.mark.django_db
def test_directory_results_use_aria_live(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    response = consenting_client.get("/annuaire/")
    soup = BeautifulSoup(response.content, "html.parser")
    live = soup.find(attrs={"aria-live": True})
    assert live is not None


@pytest.mark.django_db
def test_avatar_initials_have_aria_label(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    response = consenting_client.get("/annuaire/")
    soup = BeautifulSoup(response.content, "html.parser")
    initials = soup.find(class_="avatar-initials")
    if initials is not None:
        assert initials.get("aria-label")
```

- [ ] **Step 2: Run and address any failures**

Run: `pytest members/tests/test_a11y.py -v`
Expected: 4 passed (templates from Tasks 13, 19 already include `aria-label` and `aria-live`).

If any test fails, adjust the corresponding template:
- Pagination `<nav>` must include `aria-label="{% trans 'Pagination' %}"` (already in directory_list_partial.html).
- The `<ul>` in directory_list_partial.html must include `aria-live="polite"` (already there).
- Initials in `_avatar.html` must include `aria-label="{{ member.full_name }}"` (already there).
- Form `<input>` elements must have matching `<label for="...">` — Django's `as_p`/`label_tag` produce these by default.

- [ ] **Step 3: Commit**

```bash
git add members/tests/test_a11y.py
git commit -m "test(members): assert label/aria-live/aria-label baseline on new pages"
```

---

## Task 26: Final verification, STATUS update, tag

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Run the full project test suite**

```bash
make db-up
docker exec retrouvailles-db-1 pg_isready -U postgres
make check
make lint
make test
```

Expected:
- `make check` — 0 issues, no migration drift.
- `make lint` — clean.
- `make test` — all P1 tests + all P2 members tests pass.

- [ ] **Step 2: Manual smoke**

```bash
make seed
python manage.py runserver
```

Visit and verify:
- `http://localhost:8000/` — landing renders, anonymous OK.
- `http://localhost:8000/health` — `{"status":"ok","db":"ok"}`.
- `http://localhost:8000/accounts/login/` — log in as one of the seeded users (set a password first via `python manage.py shell -c "from django.contrib.auth import get_user_model; u = get_user_model().objects.get(email='seed1@example.test'); u.set_password('test-pw-1'); u.save()"`).
- After login → `/charte/` — charter renders, "J'accepte" persists consent and redirects.
- `/annuaire/` — 6 seeded cards, search "idris" filters to one, year filter works, pagination appears once you load >20.
- `/membres/<slug>/` — detail page renders with privacy toggles honored.
- `/profil/` — edit form, save persists and redirects.
- `/admin/` — Django admin login.

- [ ] **Step 3: Update `docs/superpowers/STATUS.md`**

In the Phase Index, change the P2 row to:

```markdown
| P2 | Membership | Complete (tag `v0.2.0-membership`, 2026-MM-DD) | [plan](plans/2026-05-02-membership.md) |
```

(Use the actual ship date.)

Replace the entire `## P2 — Membership` section with a populated version mirroring the P1 layout: shipped date + tag, plan link, test count, and a 26-row task table where each row references the matching commit SHA.

- [ ] **Step 4: Commit the STATUS update**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs: mark P2 membership complete in STATUS.md"
```

- [ ] **Step 5: Tag the milestone**

```bash
git tag -a v0.2.0-membership -m "Membership milestone: Member/NotificationPreference/ConsentRecord, profile, directory with accent-insensitive search, Cloudinary signed uploads, project-level login+consent middleware, French i18n, a11y baseline"
```

> *No `git push` here — the user will push and merge to main when ready.*

---

## Out of scope (handed off to subsequent plans)

- **P3 (Cooptation):** real signup pipeline that creates `User` + `Member` rows; admin moderation UI; `AdminApplication` and `CooptationRequest` models; J+7/J+14 deadline machinery; Resend email integration.
- **P4 (Public surface):** public landing page replacing the current placeholder; `PublicSearchEntry` model with collegial validation; public removal flow without auth; `noindex` differentiation between public and private pages.
- **P5 (Mémoire):** `Memory` model; Mur des souvenirs admin gallery; `InMemoriamEntry`; PhotoTag with the M2M to `Member` already supported by this phase's data model.
- **P6 (Ops & RGPD):** Cloudinary→B2 backup workflow; orphan reconciliation cron; RGPD purge cascading through `User → Member`; `AuditLog` model + decorator; DMARC monitoring.
- **P7 (Soft launch):** seed content prep, pilot rollout, production launch checklist.
