# P5a — Mur des Souvenirs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the member-only Mur des souvenirs photo gallery: ~10-20 admin-curated seed photos, Django admin for upload, member views at `/souvenirs/` (grid) and `/souvenirs/<id>/` (detail), surfaced via a new "Souvenirs" link in the auth nav.

**Architecture:** New Django app `memoires`. `Memory` model stores Cloudinary `public_id` as a CharField (matching the established `Member.photo_public_id` pattern). Admin uses a custom `ModelForm` with a temporary `upload` FileField; `save_model` pushes the file to Cloudinary via the existing `alumni.cloudinary` abstraction (extended with a new server-side `upload_file()` method) and writes the resulting public_id to the model. Two-state status (`draft` / `published`); only published memories are visible to members.

**Tech Stack:** Django 5.0, PostgreSQL, pytest-django, Tailwind/DaisyUI utility classes, Cloudinary (existing setup, FakeCloudinary in tests).

**Spec:** `docs/superpowers/specs/2026-05-03-mur-souvenirs-design.md`

---

## File Structure

**Create (new `memoires` app + supporting files):**
- `memoires/__init__.py` — empty package marker
- `memoires/apps.py` — Django app config
- `memoires/models.py` — `Memory` model
- `memoires/forms.py` — `MemoryAdminForm` with the temporary `upload` FileField
- `memoires/admin.py` — `MemoryAdmin` with custom form, `save_model`, thumbnail helper
- `memoires/urls.py` — `gallery` + `detail` routes
- `memoires/views.py` — `gallery_view`, `detail_view`
- `memoires/templatetags/__init__.py` — empty
- `memoires/templatetags/memory_photo.py` — `{% memory_thumb %}` + `{% memory_full %}` template tags
- `memoires/migrations/__init__.py` — empty
- `memoires/migrations/0001_initial.py` — auto-generated initial migration
- `memoires/templates/memoires/gallery.html` — grid layout
- `memoires/templates/memoires/detail.html` — single-photo detail
- `memoires/tests/__init__.py` — empty
- `memoires/tests/conftest.py` — shared fixtures (admin user, authed member)
- `memoires/tests/test_models_memory.py` — model tests (3)
- `memoires/tests/test_views_gallery.py` — gallery view tests (3)
- `memoires/tests/test_views_detail.py` — detail view tests (4)
- `memoires/tests/test_admin_memory.py` — admin form + save_model tests (2)
- `alumni/tests/test_cloudinary_extensions.py` — `upload_file()` + URL helpers tests (2)

**Modify:**
- `alumni/cloudinary.py` — add `upload_file()` to Protocol + `RealCloudinary` + `FakeCloudinary`; add `memory_thumbnail_url()` + `memory_full_url()` helpers
- `alumni/settings/base.py` — add `"memoires"` to `INSTALLED_APPS`
- `alumni/urls.py` — `path("", include("memoires.urls"))`
- `templates/base.html` — add "Souvenirs" link in desktop + mobile auth nav (between "Annuaire" and "Cooptations à valider")
- `core/tests/test_base_template.py` — add `test_nav_includes_souvenirs_link_for_authenticated_member`
- `docs/superpowers/STATUS.md` — add P5a row + section

---

## Task Order Rationale

1. **Task 1 (Cloudinary extension)** — foundational; the admin (Task 5) depends on `upload_file()`; the templatetag (Task 3) depends on the URL helpers. Ship first so downstream tasks have a tested helper to call.
2. **Task 2 (Scaffold app + Memory model)** — pure data layer. Establishes the app, the model, and the migration. Independent of views.
3. **Task 3 (Gallery view + template + templatetag)** — public-facing surface for the published list. Depends on Task 1 (URL helper) and Task 2 (Memory model).
4. **Task 4 (Detail view + template)** — single-photo page. Same dependencies.
5. **Task 5 (Admin)** — the curation surface. Depends on Tasks 1 (`upload_file`) and 2 (model). Built last among the "code" tasks because it integrates the most.
6. **Task 6 (Nav link)** — UI integration. Depends on Tasks 3+ existing so the link goes somewhere live.
7. **Task 7 (STATUS update)** — housekeeping.

---

## Task 1: Extend `alumni.cloudinary` with `upload_file()` + URL helpers

**Files:**
- Modify: `alumni/cloudinary.py`
- Create: `alumni/tests/test_cloudinary_extensions.py`

- [ ] **Step 1: Write the failing tests**

Create `alumni/tests/test_cloudinary_extensions.py`:

```python
"""Tests for the P5a additions to alumni/cloudinary.py:
- upload_file() on FakeCloudinary (deterministic stub)
- memory_thumbnail_url() / memory_full_url() URL shape."""

from __future__ import annotations

import io


def test_fake_cloudinary_upload_file_returns_deterministic_public_id():
    from alumni.cloudinary import FakeCloudinary

    client = FakeCloudinary()
    file_obj = io.BytesIO(b"fake-image-bytes")
    file_obj.name = "test.jpg"

    result = client.upload_file(file_obj, folder="memoires")

    assert result.startswith("memoires/")
    # Same input → same output
    file_obj_2 = io.BytesIO(b"fake-image-bytes")
    file_obj_2.name = "test.jpg"
    assert client.upload_file(file_obj_2, folder="memoires") == result
    # Different name → different public_id
    file_obj_3 = io.BytesIO(b"x")
    file_obj_3.name = "other.jpg"
    assert client.upload_file(file_obj_3, folder="memoires") != result


def test_fake_cloudinary_records_upload_calls():
    from alumni.cloudinary import FakeCloudinary

    client = FakeCloudinary()
    file_obj = io.BytesIO(b"data")
    file_obj.name = "photo.jpg"

    client.upload_file(file_obj, folder="memoires")

    assert len(client.upload_calls) == 1
    assert client.upload_calls[0]["folder"] == "memoires"
    assert client.upload_calls[0]["name"] == "photo.jpg"


def test_memory_thumbnail_url_uses_correct_transform(settings):
    settings.CLOUDINARY_CLOUD_NAME = "test-cloud"
    from alumni.cloudinary import memory_thumbnail_url

    url = memory_thumbnail_url("memoires/abc123", size=400)

    assert url == (
        "https://res.cloudinary.com/test-cloud/image/upload/"
        "f_auto,q_auto:eco,c_fill,g_auto,w_400,h_400/memoires/abc123"
    )


def test_memory_thumbnail_url_returns_empty_for_blank_public_id():
    from alumni.cloudinary import memory_thumbnail_url

    assert memory_thumbnail_url("") == ""


def test_memory_full_url_uses_limit_fit_no_crop(settings):
    settings.CLOUDINARY_CLOUD_NAME = "test-cloud"
    from alumni.cloudinary import memory_full_url

    url = memory_full_url("memoires/abc123", max_width=1200)

    assert url == (
        "https://res.cloudinary.com/test-cloud/image/upload/"
        "f_auto,q_auto:eco,c_limit,w_1200/memoires/abc123"
    )
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest alumni/tests/test_cloudinary_extensions.py -v`

Expected: 5 FAIL — `upload_file`, `memory_thumbnail_url`, `memory_full_url` don't exist yet.

- [ ] **Step 3: Add `upload_file()` to the Protocol + both client classes**

Edit `alumni/cloudinary.py`. Locate the `CloudinaryClient` Protocol (around line 13). Add `upload_file` to it:

```python
class CloudinaryClient(Protocol):
    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]: ...

    def upload_file(self, file_obj: Any, *, folder: str) -> str: ...

    def delete(self, public_id: str) -> None: ...
```

In `RealCloudinary` (around line 19), add `upload_file` after `sign_upload`:

```python
    def upload_file(self, file_obj: Any, *, folder: str) -> str:
        """Server-side upload via Cloudinary's REST API. Returns the public_id."""
        result = self._cloudinary.uploader.upload(
            file_obj,
            folder=folder,
            resource_type="image",
            use_filename=False,
        )
        return result["public_id"]
```

In `FakeCloudinary` (around line 48), add `upload_file` after `sign_upload`. Also initialize `upload_calls = []` in `__init__`:

```python
class FakeCloudinary:
    """In-memory client used in tests. Records calls; never hits the network."""

    def __init__(self) -> None:
        self.sign_calls: list[dict[str, Any]] = []
        self.delete_calls: list[str] = []
        self.upload_calls: list[dict[str, Any]] = []

    # ... existing sign_upload ...

    def upload_file(self, file_obj: Any, *, folder: str) -> str:
        """Test stub: records the call and returns a deterministic fake public_id."""
        name = getattr(file_obj, "name", "upload")
        digest = hashlib.sha1(f"{folder}:{name}".encode()).hexdigest()[:12]
        public_id = f"{folder}/fake-{digest}"
        self.upload_calls.append({"folder": folder, "name": name, "public_id": public_id})
        return public_id

    def delete(self, public_id: str) -> None:
        self.delete_calls.append(public_id)
```

- [ ] **Step 4: Add `memory_thumbnail_url()` and `memory_full_url()` helpers**

Still in `alumni/cloudinary.py`, append these helpers at the end of the file (after the existing `member_thumbnail_url`):

```python
def memory_thumbnail_url(public_id: str, size: int = 400) -> str:
    """Square thumbnail for the gallery grid. Auto crop with subject focus."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_fill,g_auto,w_{size},h_{size}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"


def memory_full_url(public_id: str, max_width: int = 1200) -> str:
    """Limit-fit version for the detail page. No crop; preserves aspect ratio."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_limit,w_{max_width}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `pytest alumni/tests/test_cloudinary_extensions.py -v`

Expected: 5 PASS.

- [ ] **Step 6: Run the existing alumni tests to confirm no regressions**

Run: `pytest alumni/tests/ -v`

Expected: ALL PASS (existing session-settings tests + new cloudinary tests).

- [ ] **Step 7: Commit**

```bash
git add alumni/cloudinary.py alumni/tests/test_cloudinary_extensions.py
git commit -m "feat(p5a): cloudinary upload_file + memory URL helpers"
```

---

## Task 2: Scaffold `memoires` app + Memory model + initial migration

**Files:**
- Create: `memoires/__init__.py`, `memoires/apps.py`, `memoires/models.py`
- Create: `memoires/tests/__init__.py`, `memoires/tests/conftest.py`, `memoires/tests/test_models_memory.py`
- Create: `memoires/migrations/__init__.py`
- Modify: `alumni/settings/base.py`

- [ ] **Step 1: Create the package skeleton**

Create `memoires/__init__.py` (empty file).

Create `memoires/apps.py`:

```python
from django.apps import AppConfig


class MemoiresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "memoires"
    verbose_name = "Mémoires"
```

Create `memoires/migrations/__init__.py` (empty file).

Create `memoires/tests/__init__.py` (empty file).

- [ ] **Step 2: Register the app in INSTALLED_APPS**

Edit `alumni/settings/base.py`. Locate `INSTALLED_APPS` (around lines 16-31). Add `"memoires"` after `"cooptation"`:

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
    "django.contrib.sitemaps",
    "allauth",
    "allauth.account",
    "core",
    "members",
    "cooptation",
    "memoires",
]
```

- [ ] **Step 3: Write the failing tests**

Create `memoires/tests/conftest.py`:

```python
"""Shared pytest fixtures for the memoires app."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def make_admin_user(db):
    """Staff+superuser User. Used by admin tests."""
    User = get_user_model()  # noqa: N806
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "username": f"admin{counter['i']}",
            "email": f"admin{counter['i']}@example.test",
            "password": "x",
            "is_staff": True,
            "is_superuser": True,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    return _make


@pytest.fixture
def authed_member_client(db):
    """Authenticated active Member with charter consent. Used by view tests
    so the LoginRequiredMiddleware + ConsentRequiredMiddleware both pass."""
    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="member@example.test",
        email="member@example.test",
        password="x",
    )
    member = Member.objects.create(
        user=user,
        first_name="Test",
        last_name="Member",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    ConsentRecord.objects.create(
        member=member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    client = Client()
    client.force_login(user)
    return client
```

Create `memoires/tests/test_models_memory.py`:

```python
"""Tests for the Memory model — fields, defaults, ordering."""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError


@pytest.mark.django_db
def test_memory_caption_required():
    """Caption is the only required text field. Saving without one
    must raise ValidationError on full_clean."""
    from memoires.models import Memory

    m = Memory(photo_public_id="memoires/sample", caption="")
    with pytest.raises(ValidationError):
        m.full_clean()


@pytest.mark.django_db
def test_memory_status_defaults_to_draft():
    from memoires.models import Memory

    m = Memory.objects.create(photo_public_id="memoires/x", caption="A caption.")
    assert m.status == "draft"


@pytest.mark.django_db
def test_memory_default_ordering_newest_taken_at_first():
    """Default queryset order: -taken_at, -created_at. Memories with NULL
    taken_at fall after dated entries (Postgres NULLS LAST on DESC)."""
    from memoires.models import Memory

    Memory.objects.create(
        photo_public_id="memoires/a",
        caption="Older",
        taken_at=date(1981, 6, 1),
    )
    Memory.objects.create(
        photo_public_id="memoires/b",
        caption="Newer",
        taken_at=date(1983, 6, 1),
    )
    Memory.objects.create(
        photo_public_id="memoires/c",
        caption="Undated",
    )

    captions = list(Memory.objects.values_list("caption", flat=True))
    assert captions[0] == "Newer"
    assert captions[1] == "Older"
    assert captions[2] == "Undated"
```

- [ ] **Step 4: Run tests — expect FAIL**

Run: `pytest memoires/tests/test_models_memory.py -v`

Expected: 3 FAIL — `memoires.models.Memory` doesn't exist yet.

- [ ] **Step 5: Create the Memory model**

Create `memoires/models.py`:

```python
"""Domain models for the memoires (Mur des souvenirs) app."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Memory(models.Model):
    """A single curated photo on the Mur des souvenirs.

    Phase 1: admin-curated only (10-20 seed photos). Phase 2 will open
    uploads to members and add tags + droit-à-l'image workflow.
    """

    STATUS_CHOICES = [
        ("draft", "Brouillon"),
        ("published", "Publiée"),
    ]

    photo_public_id = models.CharField(
        max_length=200,
        help_text="Cloudinary public_id (auto-rempli par l'upload admin).",
    )
    caption = models.TextField(help_text="Description visible aux membres.")
    taken_at = models.DateField(
        null=True,
        blank=True,
        help_text="Date approximative — laisser vide si inconnue.",
    )
    location = models.CharField(
        max_length=120,
        blank=True,
        help_text="Lieu (ex. : Birni, Niamey, Paris).",
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memories_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Newest era first; NULL taken_at falls after dated entries
        # (Postgres NULLS LAST on DESC ordering by default).
        ordering = ["-taken_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-taken_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.caption[:40]} ({self.taken_at or '—'})"
```

- [ ] **Step 6: Generate the initial migration**

Run: `python manage.py makemigrations memoires`

Expected: creates `memoires/migrations/0001_initial.py` with the `Memory` table.

- [ ] **Step 7: Apply the migration locally**

Run: `python manage.py migrate memoires`

Expected: applies the migration to the local Postgres DB. No errors.

- [ ] **Step 8: Run tests — expect PASS**

Run: `pytest memoires/tests/test_models_memory.py -v`

Expected: 3 PASS.

- [ ] **Step 9: Commit**

```bash
git add memoires/__init__.py memoires/apps.py memoires/models.py memoires/migrations/__init__.py memoires/migrations/0001_initial.py memoires/tests/__init__.py memoires/tests/conftest.py memoires/tests/test_models_memory.py alumni/settings/base.py
git commit -m "feat(p5a): scaffold memoires app + Memory model + migration"
```

---

## Task 3: Gallery view + URL + template + templatetag

**Files:**
- Create: `memoires/urls.py`
- Create: `memoires/views.py`
- Create: `memoires/templatetags/__init__.py`
- Create: `memoires/templatetags/memory_photo.py`
- Create: `memoires/templates/memoires/gallery.html`
- Create: `memoires/tests/test_views_gallery.py`
- Modify: `alumni/urls.py`

- [ ] **Step 1: Write the failing tests**

Create `memoires/tests/test_views_gallery.py`:

```python
"""Tests for the gallery view at /souvenirs/."""

from __future__ import annotations

import pytest
from django.test import Client


URL = "/souvenirs/"


@pytest.mark.django_db
def test_gallery_anonymous_redirects_to_login():
    response = Client().get(URL)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_gallery_member_sees_published_memories(authed_member_client):
    from memoires.models import Memory

    Memory.objects.create(
        photo_public_id="memoires/published-photo",
        caption="A precious memory from Birni",
        status="published",
    )

    response = authed_member_client.get(URL)
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "A precious memory from Birni" in body
    assert "memoires/published-photo" in body  # thumbnail URL contains public_id


@pytest.mark.django_db
def test_gallery_hides_drafts_from_members(authed_member_client):
    """Drafts are admin-curation territory and must not appear on /souvenirs/."""
    from memoires.models import Memory

    Memory.objects.create(
        photo_public_id="memoires/published",
        caption="VISIBLE PUB",
        status="published",
    )
    Memory.objects.create(
        photo_public_id="memoires/draft",
        caption="HIDDEN DRAFT",
        status="draft",
    )

    response = authed_member_client.get(URL)
    body = response.content.decode("utf-8")
    assert "VISIBLE PUB" in body
    assert "HIDDEN DRAFT" not in body
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest memoires/tests/test_views_gallery.py -v`

Expected: 3 FAIL — `/souvenirs/` route returns 404.

- [ ] **Step 3: Create the templatetag library**

Create `memoires/templatetags/__init__.py` (empty file).

Create `memoires/templatetags/memory_photo.py`:

```python
"""Template tags that build Cloudinary URLs for Memory photos."""

from __future__ import annotations

from django import template

from alumni.cloudinary import memory_full_url, memory_thumbnail_url

register = template.Library()


@register.simple_tag
def memory_thumb(public_id: str, size: int = 400) -> str:
    return memory_thumbnail_url(public_id, size=size)


@register.simple_tag
def memory_full(public_id: str, max_width: int = 1200) -> str:
    return memory_full_url(public_id, max_width=max_width)
```

- [ ] **Step 4: Create the gallery view + URL**

Create `memoires/views.py`:

```python
"""Member-only views for the Mur des souvenirs."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import Memory


@login_required
@require_http_methods(["GET"])
def gallery_view(request):
    """Grid of published memories, newest era first.

    Drafts are excluded — they are admin-curation territory only.
    """
    memories = Memory.objects.filter(status="published")
    return render(request, "memoires/gallery.html", {"memories": memories})


@login_required
@require_http_methods(["GET"])
def detail_view(request, pk: int):
    memory = get_object_or_404(Memory, pk=pk, status="published")
    return render(request, "memoires/detail.html", {"memory": memory})
```

Create `memoires/urls.py`:

```python
from django.urls import path

from . import views

app_name = "memoires"

urlpatterns = [
    path("souvenirs/", views.gallery_view, name="gallery"),
    path("souvenirs/<int:pk>/", views.detail_view, name="detail"),
]
```

Edit `alumni/urls.py`. Add `memoires.urls` to the `urlpatterns` list (after `cooptation.urls`):

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("cooptation.urls")),
    path("", include("memoires.urls")),
    path("", include("members.urls")),
    path("", include("core.urls")),
]
```

- [ ] **Step 5: Create the gallery template**

Create `memoires/templates/memoires/gallery.html`:

```html
{% extends "base.html" %}
{% load i18n memory_photo %}
{% block title %}
    {% trans "Mur des Souvenirs" %}
{% endblock %}
{% block content %}
    <div class="mx-auto max-w-6xl">
        <header class="mb-8 text-center">
            <h1 class="font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% trans "Mur des Souvenirs" %}
            </h1>
            <p class="mx-auto mt-3 max-w-2xl text-sm text-secondary">
                {% trans "Photos d'époque curées par les administrateurs." %}
            </p>
        </header>
        {% if memories %}
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {% for memory in memories %}
                    <a href="{% url 'memoires:detail' memory.pk %}"
                       class="group overflow-hidden rounded-xl border border-secondary/15 bg-surface/70 shadow-sm transition hover:border-tertiary/40">
                        <img src="{% memory_thumb memory.photo_public_id 400 %}"
                             alt="{{ memory.caption|truncatechars:80 }}"
                             loading="lazy"
                             class="aspect-square w-full object-cover">
                        <div class="p-3">
                            <p class="font-display text-sm font-semibold leading-tight">{{ memory.caption|truncatechars:80 }}</p>
                            {% if memory.taken_at %}
                                <p class="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-secondary">
                                    {{ memory.taken_at|date:"F Y" }}
                                </p>
                            {% endif %}
                        </div>
                    </a>
                {% endfor %}
            </div>
        {% else %}
            <div class="rounded-2xl border border-secondary/15 bg-surface/70 p-8 text-center shadow-sm">
                <p class="text-base text-secondary">
                    {% trans "Le mur sera enrichi au lancement. Revenez bientôt." %}
                </p>
            </div>
        {% endif %}
    </div>
{% endblock %}
```

- [ ] **Step 6: Run tests — expect PASS**

Run: `pytest memoires/tests/test_views_gallery.py -v`

Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add memoires/views.py memoires/urls.py memoires/templatetags/__init__.py memoires/templatetags/memory_photo.py memoires/templates/memoires/gallery.html memoires/tests/test_views_gallery.py alumni/urls.py
git commit -m "feat(p5a): gallery view + URL + template + memory_photo tags"
```

---

## Task 4: Detail view + template

**Files:**
- Create: `memoires/templates/memoires/detail.html`
- Create: `memoires/tests/test_views_detail.py`

The view function `detail_view` was already added in Task 3. This task adds its template and tests.

- [ ] **Step 1: Write the failing tests**

Create `memoires/tests/test_views_detail.py`:

```python
"""Tests for the detail view at /souvenirs/<id>/."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_detail_anonymous_redirects_to_login():
    from memoires.models import Memory

    m = Memory.objects.create(
        photo_public_id="memoires/p", caption="A photo", status="published"
    )

    response = Client().get(f"/souvenirs/{m.pk}/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_detail_member_sees_published_memory(authed_member_client):
    from memoires.models import Memory

    m = Memory.objects.create(
        photo_public_id="memoires/published-detail",
        caption="A full caption with rich detail.",
        location="Birni",
        status="published",
    )

    response = authed_member_client.get(f"/souvenirs/{m.pk}/")
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "A full caption with rich detail." in body
    assert "memoires/published-detail" in body  # full-size URL contains public_id
    assert "Birni" in body


@pytest.mark.django_db
def test_detail_returns_404_on_draft(authed_member_client):
    """Drafts are admin-curation territory; even members see 404."""
    from memoires.models import Memory

    m = Memory.objects.create(
        photo_public_id="memoires/draft",
        caption="A draft photo",
        status="draft",
    )

    response = authed_member_client.get(f"/souvenirs/{m.pk}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_detail_returns_404_on_unknown_pk(authed_member_client):
    response = authed_member_client.get("/souvenirs/99999/")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest memoires/tests/test_views_detail.py -v`

Expected: at least 1 FAIL — the template `memoires/detail.html` doesn't exist; published-detail test fails with `TemplateDoesNotExist`. The 404 tests may pass already since the view returns 404 before rendering.

- [ ] **Step 3: Create the detail template**

Create `memoires/templates/memoires/detail.html`:

```html
{% extends "base.html" %}
{% load i18n memory_photo %}
{% block title %}
    {% trans "Mur des Souvenirs" %}
{% endblock %}
{% block content %}
    <div class="mx-auto max-w-3xl">
        <p class="mb-6 text-sm text-secondary">
            <a href="{% url 'memoires:gallery' %}" class="hover:text-tertiary">
                ← {% trans "Retour au mur" %}
            </a>
        </p>
        <figure>
            <img src="{% memory_full memory.photo_public_id 1200 %}"
                 alt="{{ memory.caption|truncatechars:120 }}"
                 class="w-full rounded-xl border border-secondary/15 shadow-sm">
            <figcaption class="mt-6 space-y-2">
                <p class="text-lg leading-relaxed text-primary">{{ memory.caption|linebreaks }}</p>
                {% if memory.taken_at or memory.location %}
                    <p class="text-sm italic text-secondary">
                        {% if memory.taken_at %}{{ memory.taken_at|date:"F Y" }}{% endif %}
                        {% if memory.taken_at and memory.location %} · {% endif %}
                        {% if memory.location %}{{ memory.location }}{% endif %}
                    </p>
                {% endif %}
            </figcaption>
        </figure>
    </div>
{% endblock %}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest memoires/tests/test_views_detail.py -v`

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add memoires/templates/memoires/detail.html memoires/tests/test_views_detail.py
git commit -m "feat(p5a): detail view template"
```

---

## Task 5: Admin (form + save_model + Cloudinary upload)

**Files:**
- Create: `memoires/forms.py`
- Create: `memoires/admin.py`
- Create: `memoires/tests/test_admin_memory.py`

- [ ] **Step 1: Write the failing tests**

Create `memoires/tests/test_admin_memory.py`:

```python
"""Tests for MemoryAdmin — admin form upload, save_model auto-stamp,
Cloudinary upload integration via FakeCloudinary."""

from __future__ import annotations

import io

import pytest
from django.test import Client


@pytest.fixture
def fake_cloudinary(settings):
    """Force the Cloudinary client to FakeCloudinary for these tests so we
    can inspect upload_calls. The dev/test settings already point here, but
    being explicit makes the test self-contained."""
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"


def _image_file(name: str = "photo.jpg") -> io.BytesIO:
    """Build a minimal in-memory file-like object for upload testing."""
    f = io.BytesIO(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    f.name = name
    return f


@pytest.mark.django_db
def test_admin_create_uploads_to_cloudinary_and_stamps_creator(
    fake_cloudinary, make_admin_user
):
    """Creating a Memory via /admin/memoires/memory/add/ uploads the file
    to Cloudinary (FakeCloudinary records the call), writes the resulting
    public_id into Memory.photo_public_id, and stamps created_by."""
    from memoires.models import Memory

    creator = make_admin_user()
    client = Client()
    client.force_login(creator)

    response = client.post(
        "/admin/memoires/memory/add/",
        {
            "upload": _image_file("souvenir.jpg"),
            "photo_public_id": "",  # blank on create — populated by save_model
            "caption": "Cours de récréation, 1983.",
            "taken_at": "1983-04-15",
            "location": "Birni",
            "status": "draft",
        },
    )
    assert response.status_code == 302, (
        f"got {response.status_code}, body={response.content[:500]}"
    )

    m = Memory.objects.get(caption="Cours de récréation, 1983.")
    assert m.photo_public_id.startswith("memoires/fake-")  # FakeCloudinary stub
    assert m.created_by == creator


@pytest.mark.django_db
def test_admin_edit_without_new_upload_keeps_existing_photo(
    fake_cloudinary, make_admin_user
):
    """On edit, leaving the upload field blank must preserve the existing
    photo_public_id rather than blanking it."""
    from memoires.models import Memory

    creator = make_admin_user()
    client = Client()
    client.force_login(creator)

    # First create via admin to get a real photo_public_id from FakeCloudinary
    client.post(
        "/admin/memoires/memory/add/",
        {
            "upload": _image_file("first.jpg"),
            "photo_public_id": "",
            "caption": "Original caption",
            "status": "draft",
        },
    )
    m = Memory.objects.get(caption="Original caption")
    original_public_id = m.photo_public_id

    # Now edit without uploading a new file
    response = client.post(
        f"/admin/memoires/memory/{m.pk}/change/",
        {
            "upload": "",  # no new file
            "photo_public_id": original_public_id,
            "caption": "Updated caption",
            "status": "published",
        },
    )
    assert response.status_code in (302, 200), (
        f"got {response.status_code}, body={response.content[:500]}"
    )
    m.refresh_from_db()
    assert m.photo_public_id == original_public_id  # unchanged
    assert m.caption == "Updated caption"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest memoires/tests/test_admin_memory.py -v`

Expected: 2 FAIL — `MemoryAdmin` not registered yet.

- [ ] **Step 3: Create the admin form**

Create `memoires/forms.py`:

```python
"""Forms for the memoires admin."""

from __future__ import annotations

from django import forms

from .models import Memory


class MemoryAdminForm(forms.ModelForm):
    """Admin form for Memory. Adds an `upload` FileField that exists only on
    the form (not on the Memory model). MemoryAdmin.save_model uploads the
    file to Cloudinary via alumni.cloudinary and writes the resulting
    public_id into Memory.photo_public_id."""

    upload = forms.FileField(
        required=False,
        help_text="Choisir une photo. Conservera l'image existante si vide (en édition).",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    class Meta:
        model = Memory
        fields = ("photo_public_id", "caption", "taken_at", "location", "status")
        widgets = {
            "photo_public_id": forms.HiddenInput(),  # populated by save_model after upload
        }

    def clean(self):
        cleaned = super().clean()
        # On create, upload is required. On edit, may be blank (keep existing).
        if not self.instance.pk and not cleaned.get("upload"):
            raise forms.ValidationError(
                "Une photo est obligatoire pour créer une nouvelle entrée."
            )
        return cleaned
```

- [ ] **Step 4: Create the admin class**

Create `memoires/admin.py`:

```python
"""Admin curation surface for the Mur des souvenirs."""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from alumni.cloudinary import get_client, memory_thumbnail_url

from .forms import MemoryAdminForm
from .models import Memory


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    """Auto-stamps created_by on first save and uploads the file to
    Cloudinary server-side via alumni.cloudinary.get_client().upload_file().
    """

    form = MemoryAdminForm

    list_display = ("thumbnail", "caption_preview", "taken_at", "status", "updated_at")
    list_filter = ("status", "taken_at")
    search_fields = ("caption", "location")
    readonly_fields = ("created_by", "created_at", "updated_at")

    fieldsets = (
        ("Photo", {"fields": ("upload", "photo_public_id")}),
        ("Légende", {"fields": ("caption",)}),
        ("Contexte", {"fields": ("taken_at", "location")}),
        ("Publication", {"fields": ("status",)}),
        (
            "Audit (lecture seule)",
            {"fields": ("created_by", "created_at", "updated_at")},
        ),
    )

    @admin.display(description="Aperçu")
    def thumbnail(self, obj):
        if not obj.photo_public_id:
            return ""
        url = memory_thumbnail_url(obj.photo_public_id, size=80)
        return format_html(
            '<img src="{}" width="80" height="80" alt="" />', url
        )

    @admin.display(description="Légende")
    def caption_preview(self, obj):
        return obj.caption[:60] + ("…" if len(obj.caption) > 60 else "")

    def save_model(self, request, obj, form, change):
        upload = form.cleaned_data.get("upload")
        if upload:
            old_public_id = obj.photo_public_id  # may be empty on create
            client = get_client()
            obj.photo_public_id = client.upload_file(upload, folder="memoires")
            if old_public_id and old_public_id != obj.photo_public_id:
                client.delete(old_public_id)
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `pytest memoires/tests/test_admin_memory.py -v`

Expected: 2 PASS.

- [ ] **Step 6: Run all memoires tests + cloudinary tests to confirm no regressions**

Run: `pytest memoires/tests/ alumni/tests/test_cloudinary_extensions.py -v`

Expected: ALL PASS (3 model + 3 gallery + 4 detail + 2 admin + 5 cloudinary = 17).

- [ ] **Step 7: Commit**

```bash
git add memoires/forms.py memoires/admin.py memoires/tests/test_admin_memory.py
git commit -m "feat(p5a): admin form + save_model with cloudinary upload"
```

---

## Task 6: Nav link in `templates/base.html`

**Files:**
- Modify: `templates/base.html`
- Modify: `core/tests/test_base_template.py`

- [ ] **Step 1: Write the failing test**

Edit `core/tests/test_base_template.py`. Append at the end of the file:

```python
@pytest.mark.django_db
def test_nav_includes_souvenirs_link_for_authenticated_member(client):
    """Authenticated members see a 'Souvenirs' link in the auth nav
    pointing to /souvenirs/. Anonymous visitors see no auth nav at all,
    so no negative case is needed."""
    from django.contrib.auth import get_user_model

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="navtest@example.test",
        email="navtest@example.test",
        password="x",
    )
    member = Member.objects.create(
        user=user,
        first_name="Nav",
        last_name="Test",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    client.force_login(user)

    response = client.get(reverse("landing"))
    body = response.content.decode("utf-8")
    # Link must appear at least twice (desktop + mobile nav blocks)
    assert body.count("/souvenirs/") >= 2
    assert "Souvenirs" in body
```

- [ ] **Step 2: Run the test — expect FAIL**

Run: `pytest core/tests/test_base_template.py::test_nav_includes_souvenirs_link_for_authenticated_member -v`

Expected: FAIL — the nav doesn't include `/souvenirs/` yet.

- [ ] **Step 3: Add the desktop nav link**

Edit `templates/base.html`. Locate the desktop auth nav block (search for `<nav class="hidden md:flex` — the block that currently contains "Annuaire" and "Cooptations à valider"):

```html
{% if request.user.is_authenticated %}
    <nav class="hidden md:flex items-center gap-1 text-sm"
         aria-label="{% trans 'Navigation principale' %}">
        <a href="/annuaire/"
           class="rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">{% trans "Annuaire" %}</a>
        <a href="/cooptations-a-valider/"
           class="inline-flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">
            {% trans "Cooptations à valider" %}
            ...
        </a>
        <a href="/profil/"
           class="rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">{% trans "Mon profil" %}</a>
    </nav>
{% endif %}
```

INSERT the Souvenirs link between "Annuaire" and "Cooptations à valider":

```html
<a href="/souvenirs/"
   class="rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">{% trans "Souvenirs" %}</a>
```

So the desktop nav order becomes: Annuaire · Souvenirs · Cooptations à valider · Mon profil.

- [ ] **Step 4: Add the mobile nav link**

Still in `templates/base.html`, locate the mobile auth nav block (search for `<nav class="md:hidden` — the block containing the same labels in shorter form). INSERT the Souvenirs link in the same position (between "Annuaire" and "À valider"):

```html
<a href="/souvenirs/" class="rounded-lg px-3 py-2 hover:text-tertiary">{% trans "Souvenirs" %}</a>
```

- [ ] **Step 5: Run the test — expect PASS**

Run: `pytest core/tests/test_base_template.py::test_nav_includes_souvenirs_link_for_authenticated_member -v`

Expected: PASS.

- [ ] **Step 6: Run the full base template test file**

Run: `pytest core/tests/test_base_template.py -v`

Expected: ALL PASS.

- [ ] **Step 7: Commit**

```bash
git add templates/base.html core/tests/test_base_template.py
git commit -m "feat(p5a): add Souvenirs link to authenticated member nav"
```

---

## Task 7: STATUS update + final verification

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Add the P5a row to the Phase Index table**

Open `docs/superpowers/STATUS.md`. Locate the Phase Index table. Insert a new P5a row after the P3.1 row and before the P5 row:

```markdown
| P5a | Mur des souvenirs (member-only photo gallery) | Complete (2026-05-03) | [plan](plans/2026-05-03-mur-souvenirs.md) |
```

After your edit, the relevant section should read:

```markdown
| P3.1 | Parrain UX Polish (pending-vouches dashboard + 90-day session) | Complete (2026-05-03) | [plan](plans/2026-05-03-parrain-ux-polish.md) |
| P5a | Mur des souvenirs (member-only photo gallery) | Complete (2026-05-03) | [plan](plans/2026-05-03-mur-souvenirs.md) |
| P5 | Mémoire seed | (split into P5a + P5b) | — |
```

(Update the existing P5 row to indicate the split.)

- [ ] **Step 2: Add the P5a phase section**

Append a new section to `docs/superpowers/STATUS.md`. Place it after the existing P3.1 section (or wherever the latest phase section is) and before the existing P5 placeholder:

```markdown
## P5a — Mur des souvenirs

**Shipped:** 2026-05-03
**Plan:** [plans/2026-05-03-mur-souvenirs.md](plans/2026-05-03-mur-souvenirs.md)
**Spec:** [specs/2026-05-03-mur-souvenirs-design.md](specs/2026-05-03-mur-souvenirs-design.md)
**Test suite:** all passing

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Cloudinary client extension (upload_file + URL helpers) | [x] | _filled by implementer_ |
| 2 | Scaffold memoires app + Memory model + migration | [x] | _filled by implementer_ |
| 3 | Gallery view + URL + template + memory_photo tags | [x] | _filled by implementer_ |
| 4 | Detail view + template | [x] | _filled by implementer_ |
| 5 | Admin (form + save_model + Cloudinary upload) | [x] | _filled by implementer_ |
| 6 | Nav link in base.html (desktop + mobile) | [x] | _filled by implementer_ |
| 7 | STATUS.md update | [x] | (this commit) |

---
```

- [ ] **Step 3: Fill in the commit SHAs**

Run: `git log --oneline | head -10`

Expected output: a list of P5a-related commits in reverse chronological order. Map each Task # to its terminal commit SHA. Replace each `_filled by implementer_` placeholder with the appropriate short SHA.

- [ ] **Step 4: Run the full test suite**

Run: `pytest --ignore=members/tests/test_cloudinary_sign.py --tb=short`

Expected: ALL PASS. Test count should be roughly 383 (368 prior + ~15 new from P5a).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(p5a): mark Mur des souvenirs complete in STATUS"
```

---

## Final verification checklist

After Task 7 commits:

- [ ] `pytest --ignore=members/tests/test_cloudinary_sign.py` exits clean.
- [ ] `git log --oneline | head -15` shows all P5a commits in order.
- [ ] Manual smoke (against local runserver, logged in as admin):
  1. Visit `/admin/memoires/memory/add/` — form has the `upload` file picker.
  2. Upload a real JPEG, fill caption, save with `status=draft`. Confirm `Memory.photo_public_id` is populated (visible after save in the changelist's thumbnail column).
  3. Visit `/souvenirs/` as an authenticated member — empty state OR the entry doesn't appear (it's a draft).
  4. Switch the entry to `status=published` via admin. Reload `/souvenirs/`. Entry appears.
  5. Click → land on `/souvenirs/<pk>/` showing full caption + photo + date + location.
  6. Confirm "Souvenirs" link appears in the desktop and mobile auth navs.

---

## What this plan does NOT do (per spec §Non-goals)

- No member-side photo upload (Phase 2 / US-10).
- No people-tagging M2M (Phase 2).
- No reactions / comments / souvenirs écrits (Phase 2).
- No pagination (defer until count ≥50).
- No bulk upload UI.
- No archived status (deferred — admins use `status=draft` + caption note for now).
- No In Memoriam (P5b — separate phase).
- No Backblaze B2 backup pipeline (Phase 6 ops).
