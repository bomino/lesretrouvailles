# Gestion Souvenirs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the `/gestion/` co-admin console with full photo curation parity on the Mur des souvenirs (`Memory` model) — list, create, edit (incl. photo replace), publish/unpublish toggle, with server-side EXIF strip on every new upload as defense-in-depth.

**Architecture:** Mirrors the `feat/gestion-cooptation` Gestion-v1 shape. Plain Django views in `gestion/views.py`, forms in `gestion/forms.py`, URLs in `gestion/urls.py`, French-language templates in `gestion/templates/gestion/`. Cloudinary upload pipeline (`alumni.cloudinary.RealCloudinary.upload_file`) gains a Pillow-based EXIF strip step before passing bytes to Cloudinary. Transaction semantics: `with transaction.atomic():` blocks scoped to DB writes, `Memory.objects.select_for_update()` for edit/status views, `transaction.on_commit(...)` for old-photo Cloudinary cleanup.

**Tech Stack:** Django 5 + Postgres + Cloudinary SDK + Pillow + pytest-django.

**Spec:** [`docs/superpowers/specs/2026-05-10-gestion-souvenirs-design.md`](../specs/2026-05-10-gestion-souvenirs-design.md)

---

## Task 1: Infrastructure setup (Pillow dep + DATA_UPLOAD_MAX_MEMORY_SIZE + AuditLog choices)

**Files:**
- Modify: `pyproject.toml`
- Modify: `alumni/settings/base.py`
- Modify: `members/models.py` (around line 296 — `AuditLog.ACTION_CHOICES`)

- [ ] **Step 1.1: Add `pillow>=10.0` to dependencies**

Edit `pyproject.toml`. Locate the `dependencies = [...]` block (currently around line 10) and append `"pillow>=10.0"` to the list.

```toml
dependencies = [
    "django>=5.0,<5.1",
    "psycopg[binary]>=3.1",
    "django-allauth>=65.0",
    "django-environ>=0.11",
    "whitenoise>=6.6",
    "gunicorn>=21",
    "cloudinary>=1.40",
    "django-ratelimit>=4.1",
    "markdown>=3.6",
    "bleach>=6.0",
    "boto3>=1.34",
    "redis>=5.0",
    "resend>=2.0",
    "pillow>=10.0",
]
```

- [ ] **Step 1.2: Verify Pillow installs cleanly**

Run: `pip install -e .`

Expected: PASS (Pillow is already in the venv as transitive cloudinary dep; explicit install is no-op except for metadata).

- [ ] **Step 1.3: Raise `DATA_UPLOAD_MAX_MEMORY_SIZE`**

Edit `alumni/settings/base.py`. After the `STATIC_ROOT` block (~line 100), add:

```python
# Allow up to 10 MB POST payloads (accommodates 8 MB photo upload + headers).
# Files >2.5 MB still stream to disk (FILE_UPLOAD_MAX_MEMORY_SIZE default)
# rather than buffer in RAM.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
```

- [ ] **Step 1.4: Add 4 entries to `AuditLog.ACTION_CHOICES`**

Edit `members/models.py`. Locate `class AuditLog(models.Model):` and its `ACTION_CHOICES = [...]` list (around line 296). Add 4 entries — grouped together for readability, just before the `gestion.*` block:

```python
("memoires.memory.created", "Photo Souvenirs créée"),
("memoires.memory.edited", "Photo Souvenirs modifiée"),
("memoires.memory.published", "Photo Souvenirs publiée"),
("memoires.memory.unpublished", "Photo Souvenirs dépubliée"),
```

- [ ] **Step 1.5: Sanity check — Django can load**

Run: `python manage.py check`

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 1.6: Sanity check — no missing migrations**

Run: `python manage.py makemigrations --dry-run --check`

Expected: `No changes detected` (choices are Python-level; no migration needed).

- [ ] **Step 1.7: Commit**

```bash
git add pyproject.toml alumni/settings/base.py members/models.py
git commit -m "$(cat <<'EOF'
chore(infra): pin pillow, raise upload limit, add memoires audit actions

Prep work for /gestion/souvenirs/ implementation:
- pillow>=10 as explicit dep (was transitive via cloudinary; making
  explicit guards against accidental drop).
- DATA_UPLOAD_MAX_MEMORY_SIZE = 10 MB accommodates the 8 MB photo cap
  the upcoming form enforces; FILE_UPLOAD_MAX_MEMORY_SIZE stays at
  default 2.5 MB so big files stream to disk not RAM.
- 4 memoires.memory.* entries in AuditLog.ACTION_CHOICES (Python-level,
  no migration).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: EXIF strip — server-side (Pillow) + delivery-side (`fl_strip_profile`)

**Files:**
- Modify: `alumni/cloudinary.py:56-64` (`RealCloudinary.upload_file`)
- Modify: `alumni/cloudinary.py:170-185` (`memory_thumbnail_url` + `memory_full_url`)
- Modify: `alumni/tests/test_cloudinary_extensions.py` (extend)

- [ ] **Step 2.1: Write the failing tests**

Add to `alumni/tests/test_cloudinary_extensions.py`:

```python
from io import BytesIO

import pytest
from PIL import Image

from alumni.cloudinary import (
    _strip_exif_metadata,
    memory_full_url,
    memory_thumbnail_url,
)


class TestStripExifMetadata:
    def _make_jpeg_with_exif(self) -> BytesIO:
        """Build a tiny in-memory JPEG that has a recognisable EXIF tag."""
        img = Image.new("RGB", (10, 10), color="red")
        exif = img.getexif()
        # 0x010E is the standard ImageDescription tag — easy to assert against.
        exif[0x010E] = "test exif description"
        buf = BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        buf.seek(0)
        return buf

    def test_exif_present_in_unstripped_baseline(self):
        # Sanity: confirm our fixture actually carries EXIF.
        buf = self._make_jpeg_with_exif()
        roundtrip = Image.open(buf)
        assert roundtrip.getexif().get(0x010E) == "test exif description"

    def test_strip_removes_exif_from_jpeg(self):
        buf = self._make_jpeg_with_exif()
        stripped = _strip_exif_metadata(buf, content_type="image/jpeg")
        stripped_img = Image.open(stripped)
        assert dict(stripped_img.getexif()) == {}

    def test_strip_preserves_image_dimensions(self):
        buf = self._make_jpeg_with_exif()
        stripped = _strip_exif_metadata(buf, content_type="image/jpeg")
        stripped_img = Image.open(stripped)
        assert stripped_img.size == (10, 10)

    def test_strip_falls_back_to_original_on_pillow_failure(self, caplog):
        # Random bytes Pillow cannot decode → fall back to original.
        bogus = BytesIO(b"not-an-image-at-all")
        result = _strip_exif_metadata(bogus, content_type="image/jpeg")
        assert result.read() == b"not-an-image-at-all"
        assert "EXIF strip failed" in caplog.text


class TestMemoryUrlExifStripFlag:
    def test_thumbnail_url_contains_fl_strip_profile(self):
        url = memory_thumbnail_url("memoires/sample", size=200)
        assert "fl_strip_profile" in url

    def test_full_url_contains_fl_strip_profile(self):
        url = memory_full_url("memoires/sample", max_width=1200)
        assert "fl_strip_profile" in url
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `pytest alumni/tests/test_cloudinary_extensions.py::TestStripExifMetadata alumni/tests/test_cloudinary_extensions.py::TestMemoryUrlExifStripFlag -v`

Expected: All tests FAIL — `_strip_exif_metadata` doesn't exist yet; `memory_thumbnail_url`/`memory_full_url` URLs don't contain `fl_strip_profile`.

- [ ] **Step 2.3: Implement `_strip_exif_metadata`**

Edit `alumni/cloudinary.py`. Add a module-level helper above the `RealCloudinary` class (after the existing imports):

```python
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

# MIME types we know how to strip via Pillow's resave.
_STRIPPABLE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def _strip_exif_metadata(file_obj, *, content_type: str) -> BytesIO:
    """Re-encode the image via Pillow to drop EXIF/XMP/IPTC from the bytes.

    Pillow's .save() does not preserve metadata unless you pass the exif=
    kwarg explicitly. Calling it without exif= produces a clean copy.

    On any Pillow failure (corrupt file, unsupported format, etc.) we log a
    warning and return the original bytes unchanged. This trades EXIF
    protection on the failing upload for keeping the user-visible upload
    flow working — the photo lands on the wall; the operator can manually
    re-upload if they suspect a problem. The §I Risk #14 residual.
    """
    from PIL import Image, UnidentifiedImageError

    # Pillow needs a seekable stream. Read into memory once and rewind.
    raw = file_obj.read() if hasattr(file_obj, "read") else file_obj
    if isinstance(raw, bytes):
        source = BytesIO(raw)
    else:
        source = BytesIO(bytes(raw))
    source.seek(0)

    if content_type not in _STRIPPABLE_MIME_TYPES:
        # Trust the validation layer; this branch is defensive only.
        source.seek(0)
        return source

    try:
        img = Image.open(source)
        img.load()  # force-decode now so errors fire here, not later
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("EXIF strip failed (Pillow open): %s", exc)
        source.seek(0)
        return source

    out = BytesIO()
    fmt_map = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }
    pil_format = fmt_map[content_type]

    try:
        # Note: NOT passing exif= drops the EXIF chunk on JPEG.
        # PNG/WebP: Pillow drops ancillary chunks (incl. metadata) by default.
        save_kwargs = {"format": pil_format}
        if pil_format == "JPEG":
            # Preserve original quality reasonably; 95 matches Pillow's "good".
            save_kwargs["quality"] = 95
            save_kwargs["optimize"] = True
        img.save(out, **save_kwargs)
    except (OSError, ValueError) as exc:
        logger.warning("EXIF strip failed (Pillow save): %s", exc)
        source.seek(0)
        return source

    out.seek(0)
    return out
```

- [ ] **Step 2.4: Wire the strip into `RealCloudinary.upload_file`**

Edit `alumni/cloudinary.py`. Replace the existing `upload_file` body:

```python
    def upload_file(self, file_obj: Any, *, folder: str) -> str:
        """Server-side upload via Cloudinary's REST API. Returns the public_id.

        Strips EXIF/XMP/IPTC metadata server-side before passing to Cloudinary
        (see alumni.cloudinary._strip_exif_metadata). On Pillow failure the
        original bytes flow through unchanged — a logged residual, not a
        user-visible error.
        """
        content_type = getattr(file_obj, "content_type", "image/jpeg")
        stripped = _strip_exif_metadata(file_obj, content_type=content_type)
        result = self._cloudinary.uploader.upload(
            stripped,
            folder=folder,
            resource_type="image",
            use_filename=False,
        )
        return result["public_id"]
```

- [ ] **Step 2.5: Add `fl_strip_profile` to `memory_thumbnail_url` AND `memory_full_url`**

Edit `alumni/cloudinary.py`. Update both helpers:

```python
def memory_thumbnail_url(public_id: str, size: int = 400) -> str:
    """Square thumbnail for the gallery grid. Auto crop with subject focus.

    fl_strip_profile drops EXIF/IPTC from the delivered URL — defense in
    depth alongside the server-side strip in RealCloudinary.upload_file.
    """
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_fill,g_auto,fl_strip_profile,w_{size},h_{size}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"


def memory_full_url(public_id: str, max_width: int = 1200) -> str:
    """Limit-fit version for the detail page. No crop; preserves aspect ratio.

    fl_strip_profile drops EXIF/IPTC from the delivered URL — defense in
    depth alongside the server-side strip in RealCloudinary.upload_file.
    """
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_limit,fl_strip_profile,w_{max_width}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"
```

- [ ] **Step 2.6: Run tests to verify they pass**

Run: `pytest alumni/tests/test_cloudinary_extensions.py::TestStripExifMetadata alumni/tests/test_cloudinary_extensions.py::TestMemoryUrlExifStripFlag -v`

Expected: All 6 tests PASS.

- [ ] **Step 2.7: Run full alumni test suite for regression check**

Run: `pytest alumni/ -v`

Expected: PASS for all alumni/ tests (existing `test_real_cloudinary_init_loads_required_submodules` regression test from CLAUDE.md `RealCloudinary` import contract still passes).

- [ ] **Step 2.8: Commit**

```bash
git add alumni/cloudinary.py alumni/tests/test_cloudinary_extensions.py
git commit -m "$(cat <<'EOF'
feat(cloudinary): strip EXIF server-side at upload + fl_strip_profile in delivery

Prevents GPS leakage from photos uploaded via /admin/ or /gestion/.

- _strip_exif_metadata: re-encodes JPEG/PNG/WebP via Pillow without
  the exif= kwarg, which drops EXIF/XMP/IPTC from the bytes Cloudinary
  receives. On Pillow failure (corrupt, unsupported), falls back to
  uploading the original bytes with logger.warning — preserves the
  upload flow, accepts the residual.
- RealCloudinary.upload_file: now routes uploads through the strip
  helper before passing to the Cloudinary SDK. Applies to all callers
  (member admin photos, memoires admin, memoriam admin, the new
  /gestion/souvenirs/ in the next task).
- memory_thumbnail_url + memory_full_url: gain fl_strip_profile in the
  transformation chain, so existing pre-phase photos (whose stored
  originals still have EXIF) also serve stripped bytes via the
  delivery URL. Defense in depth.

Residuals documented in spec §I:
- Pillow failure path uploads original (logged warning, not a 500).
- Pre-phase photos can still be reached via the raw cloudinary.com
  /image/upload/<public_id> URL (no transformations), which bypasses
  fl_strip_profile. A restrip_existing_memories management command is
  the Phase 2 fix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `GestionMemoryForm` + URLs + test fixture

**Files:**
- Modify: `gestion/forms.py` (extend)
- Modify: `gestion/urls.py` (extend)
- Modify: `gestion/tests/conftest.py` (extend)
- Test: `gestion/tests/test_form_memory.py` (new)

- [ ] **Step 3.1: Write the form tests**

Create `gestion/tests/test_form_memory.py`:

```python
"""Validation tests for GestionMemoryForm — the form behind /gestion/souvenirs/.

Lifts memoires.forms.MemoryAdminForm into the gestion namespace and adds
the upload size/MIME guards the existing admin form doesn't enforce.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def _make_jpeg_upload(*, size_bytes: int = 1024, content_type: str = "image/jpeg",
                     name: str = "test.jpg") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"x" * size_bytes, content_type=content_type)


class TestGestionMemoryFormCreate:
    def test_valid_form_with_upload_passes(self):
        from gestion.forms import GestionMemoryForm

        form = GestionMemoryForm(
            data={
                "caption": "Sortie à Birni 1983",
                "taken_at": "",
                "location": "Birni",
                "status": "draft",
            },
            files={"upload": _make_jpeg_upload()},
        )
        assert form.is_valid(), form.errors

    def test_missing_upload_on_create_fails(self):
        from gestion.forms import GestionMemoryForm

        form = GestionMemoryForm(
            data={
                "caption": "Sortie à Birni 1983",
                "taken_at": "",
                "location": "Birni",
                "status": "draft",
            },
            files={},
        )
        assert not form.is_valid()
        # The error appears either at the upload field or as a non-field error
        # depending on whether the form's clean() raises NonField vs field-level.
        errors_text = str(form.errors)
        assert "photo" in errors_text.lower() or "obligatoire" in errors_text.lower()

    def test_oversize_upload_rejected(self):
        from gestion.forms import GestionMemoryForm

        big = _make_jpeg_upload(size_bytes=9 * 1024 * 1024)  # 9 MB > 8 MB cap
        form = GestionMemoryForm(
            data={"caption": "x", "location": "", "status": "draft", "taken_at": ""},
            files={"upload": big},
        )
        assert not form.is_valid()
        assert "upload" in form.errors
        assert "8" in str(form.errors["upload"])  # error message mentions the limit

    def test_zero_byte_upload_rejected(self):
        from gestion.forms import GestionMemoryForm

        empty = _make_jpeg_upload(size_bytes=0)
        form = GestionMemoryForm(
            data={"caption": "x", "location": "", "status": "draft", "taken_at": ""},
            files={"upload": empty},
        )
        assert not form.is_valid()
        assert "upload" in form.errors

    def test_disallowed_mime_rejected(self):
        from gestion.forms import GestionMemoryForm

        bad = SimpleUploadedFile("file.gif", b"x" * 100, content_type="image/gif")
        form = GestionMemoryForm(
            data={"caption": "x", "location": "", "status": "draft", "taken_at": ""},
            files={"upload": bad},
        )
        assert not form.is_valid()
        assert "upload" in form.errors

    def test_jpeg_png_webp_all_accepted(self):
        from gestion.forms import GestionMemoryForm

        for ctype, name in [
            ("image/jpeg", "p.jpg"),
            ("image/png", "p.png"),
            ("image/webp", "p.webp"),
        ]:
            up = _make_jpeg_upload(content_type=ctype, name=name)
            form = GestionMemoryForm(
                data={"caption": "x", "location": "", "status": "draft", "taken_at": ""},
                files={"upload": up},
            )
            assert form.is_valid(), f"{ctype} should validate; got {form.errors}"


class TestGestionMemoryFormEdit:
    def test_edit_without_new_upload_passes(self, make_memory):
        from gestion.forms import GestionMemoryForm

        memory = make_memory()
        form = GestionMemoryForm(
            data={
                "caption": "Updated caption",
                "taken_at": "",
                "location": "",
                "status": "published",
            },
            files={},
            instance=memory,
        )
        assert form.is_valid(), form.errors

    def test_edit_with_new_upload_passes(self, make_memory):
        from gestion.forms import GestionMemoryForm

        memory = make_memory()
        form = GestionMemoryForm(
            data={
                "caption": "Updated",
                "taken_at": "",
                "location": "",
                "status": "draft",
            },
            files={"upload": _make_jpeg_upload()},
            instance=memory,
        )
        assert form.is_valid(), form.errors
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `pytest gestion/tests/test_form_memory.py -v`

Expected: All tests FAIL with `ImportError: cannot import name 'GestionMemoryForm'` (form doesn't exist yet) — and `make_memory` fixture not yet defined.

- [ ] **Step 3.3: Add the `make_memory` fixture to `gestion/tests/conftest.py`**

Append to `gestion/tests/conftest.py`:

```python
@pytest.fixture
def make_memory(db, make_user):
    """Factory for Memory rows. Defaults: status=published, seed public_id.
    Pass status="draft" to build a draft. Pass created_by=user to override
    the auto-created uploader."""
    from memoires.models import Memory

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        created_by = kwargs.pop("created_by", None) or make_user(
            username=f"memory_owner_{counter['i']}",
            email=f"memory_owner_{counter['i']}@example.test",
            is_staff=True,
        )
        defaults = {
            "photo_public_id": f"seed/test-photo-{counter['i']}",
            "caption": f"Test memory {counter['i']}",
            "status": "published",
            "created_by": created_by,
        }
        defaults.update(kwargs)
        return Memory.objects.create(**defaults)

    return _make
```

- [ ] **Step 3.4: Add `GestionMemoryForm` to `gestion/forms.py`**

Append to `gestion/forms.py`:

```python
class GestionMemoryForm(forms.ModelForm):
    """Memory create/edit form for /gestion/souvenirs/.

    Lifted from memoires.forms.MemoryAdminForm + hardened with the
    upload size/MIME guards the admin form doesn't enforce. Tailwind-
    styled inputs to fit the /gestion/ visual language.
    """

    ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
    MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8 MB

    upload = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            "accept": "image/jpeg,image/png,image/webp",
            "class": "block w-full text-base min-h-tap",
        }),
        help_text="Choisir une photo (JPEG, PNG ou WebP, ≤ 8 Mo). "
                  "Laisser vide pour conserver l'image existante.",
    )

    class Meta:
        from memoires.models import Memory  # avoid circular import at module load
        model = Memory
        fields = ("caption", "taken_at", "location", "status")
        widgets = {
            "caption": forms.Textarea(attrs={"rows": 4}),
            "taken_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "block w-full rounded-lg border border-secondary/20 bg-white "
            "px-3 py-2.5 text-base shadow-sm focus:border-tertiary "
            "focus:outline-none focus:ring-2 focus:ring-tertiary/30 min-h-tap"
        )
        for name, field in self.fields.items():
            if name == "upload":
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " " + input_class).strip()

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if not upload:
            return upload  # may be empty on edit; whole-form clean re-checks create case
        if upload.size == 0:
            raise forms.ValidationError("Le fichier est vide.")
        if upload.size > self.MAX_UPLOAD_SIZE:
            raise forms.ValidationError(
                "Photo trop volumineuse : 8 Mo maximum."
            )
        if upload.content_type not in self.ALLOWED_MIME_TYPES:
            raise forms.ValidationError(
                "Format non pris en charge. Utilisez JPEG, PNG ou WebP."
            )
        return upload

    def clean(self):
        cleaned = super().clean()
        # On CREATE, upload is required.
        if not self.instance.pk and not cleaned.get("upload"):
            raise forms.ValidationError(
                "Une photo est obligatoire pour créer une nouvelle entrée."
            )
        return cleaned
```

- [ ] **Step 3.5: Add the 4 URL routes to `gestion/urls.py`**

Edit `gestion/urls.py`. Append to the `urlpatterns` list (before the closing `]`):

```python
    path(
        "souvenirs/",
        views.memory_list_view,
        name="memory_list",
    ),
    path(
        "souvenirs/nouveau/",
        views.memory_create_view,
        name="memory_create",
    ),
    path(
        "souvenirs/<int:pk>/modifier/",
        views.memory_edit_view,
        name="memory_edit",
    ),
    path(
        "souvenirs/<int:pk>/statut/",
        views.memory_status_view,
        name="memory_status",
    ),
```

These point at views we'll add in Tasks 4–7. To keep Django from blowing up at import time, add placeholder view stubs in `gestion/views.py` for now (we'll flesh them out next):

```python
@staff_required
def memory_list_view(request):
    return HttpResponse(status=501)  # stub — Task 4


@staff_required
def memory_create_view(request):
    return HttpResponse(status=501)  # stub — Task 5


@staff_required
def memory_edit_view(request, pk):
    return HttpResponse(status=501)  # stub — Task 6


@staff_required
def memory_status_view(request, pk):
    return HttpResponse(status=501)  # stub — Task 7
```

If `HttpResponse` isn't already imported in `gestion/views.py`, ensure the imports include:

```python
from django.http import HttpResponse, HttpResponseRedirect
```

- [ ] **Step 3.6: Run form tests to verify pass**

Run: `pytest gestion/tests/test_form_memory.py -v`

Expected: All 8 tests PASS.

- [ ] **Step 3.7: Run system check (URLs resolve)**

Run: `python manage.py check`

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3.8: Commit**

```bash
git add gestion/forms.py gestion/urls.py gestion/views.py gestion/tests/conftest.py gestion/tests/test_form_memory.py
git commit -m "$(cat <<'EOF'
feat(gestion): GestionMemoryForm + souvenirs URL routes + make_memory fixture

- GestionMemoryForm: ModelForm over Memory with the upload validation
  the existing admin form lacks (size ≤ 8 MB, MIME ∈ {jpeg,png,webp}).
  French error messages, Tailwind-styled inputs with min-h-tap.
- 4 URL routes under /gestion/souvenirs/ — list, create, edit, status.
  Views are placeholder stubs (501) at this commit; bodies land in the
  next 4 tasks.
- make_memory fixture in gestion/tests/conftest.py. Default
  status=published; tests call make_memory(status="draft") for drafts.

8 form tests added.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `memory_list_view` + template

**Files:**
- Modify: `gestion/views.py` (replace stub)
- Create: `gestion/templates/gestion/memory_list.html`
- Test: `gestion/tests/test_memory_list.py` (new)

- [ ] **Step 4.1: Write the list-view tests**

Create `gestion/tests/test_memory_list.py`:

```python
"""Tests for /gestion/souvenirs/ — the memory list view."""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestMemoryListPermissions:
    def test_anon_redirected_to_login(self, client):
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_regular_member_gets_403(self, client, regular_member_user):
        client.force_login(regular_member_user)
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 403

    def test_coadmin_sees_200(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 200

    def test_superadmin_sees_200(self, client, superadmin_user):
        client.force_login(superadmin_user)
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 200


class TestMemoryListContent:
    def test_lists_all_memories_by_default(self, client, coadmin_user, make_memory):
        m1 = make_memory(caption="Photo published one", status="published")
        m2 = make_memory(caption="Photo draft one", status="draft")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Photo published one" in body
        assert "Photo draft one" in body

    def test_filter_published(self, client, coadmin_user, make_memory):
        make_memory(caption="P1", status="published")
        make_memory(caption="D1", status="draft")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?status=published")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "P1" in body
        assert "D1" not in body

    def test_filter_draft(self, client, coadmin_user, make_memory):
        make_memory(caption="P1", status="published")
        make_memory(caption="D1", status="draft")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?status=draft")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "D1" in body
        assert "P1" not in body

    def test_bad_status_param_falls_back_to_all(self, client, coadmin_user, make_memory):
        make_memory(caption="P1", status="published")
        make_memory(caption="D1", status="draft")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?status=garbage")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "P1" in body
        assert "D1" in body

    def test_search_caption(self, client, coadmin_user, make_memory):
        make_memory(caption="Sortie à Birni 1983")
        make_memory(caption="Cérémonie de fin d'année")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?q=Birni")
        body = resp.content.decode()
        assert "Sortie à Birni 1983" in body
        assert "Cérémonie" not in body

    def test_search_location(self, client, coadmin_user, make_memory):
        make_memory(caption="Photo 1", location="Niamey")
        make_memory(caption="Photo 2", location="Paris")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?q=Niamey")
        body = resp.content.decode()
        assert "Photo 1" in body
        assert "Photo 2" not in body

    def test_search_accent_insensitive(self, client, coadmin_user, make_memory):
        make_memory(caption="Cérémonie")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?q=ceremonie")
        body = resp.content.decode()
        assert "Cérémonie" in body

    def test_empty_state_when_no_drafts(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?status=draft")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Aucune photo" in body

    def test_thumbnails_lazy_load(self, client, coadmin_user, make_memory):
        make_memory(caption="Sample")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/")
        body = resp.content.decode()
        assert 'loading="lazy"' in body

    def test_pagination_at_page_size_12(self, client, coadmin_user, make_memory):
        # Create 13 memories; first page shows 12, second page shows 1.
        for i in range(13):
            make_memory(caption=f"Photo {i:02d}")
        client.force_login(coadmin_user)
        resp_p1 = client.get("/gestion/souvenirs/?page=1")
        body_p1 = resp_p1.content.decode()
        # Count occurrences of "Photo " — should be 12 on page 1 (in the grid).
        # Using a loose check: at least 12 figure tags.
        assert body_p1.count("<figure") >= 12

        resp_p2 = client.get("/gestion/souvenirs/?page=2")
        assert resp_p2.status_code == 200

    def test_orders_by_created_at_descending(self, client, coadmin_user, make_memory):
        # Recency-first: newer memories appear before older ones.
        first_created = make_memory(caption="Early upload")
        second_created = make_memory(caption="Recent upload")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/")
        body = resp.content.decode()
        assert body.index("Recent upload") < body.index("Early upload")
```

- [ ] **Step 4.2: Run tests to verify failures**

Run: `pytest gestion/tests/test_memory_list.py -v`

Expected: Tests FAIL — the view is still the 501 stub from Task 3.

- [ ] **Step 4.3: Implement `memory_list_view`**

Edit `gestion/views.py`. Replace the `memory_list_view` stub:

```python
PAGE_SIZE_MEMORY = 12  # photo grid — distinct from PAGE_SIZE = 20 for text-heavy lists

MEMORY_STATUS_FILTERS = ("all", "published", "draft")


@staff_required
@require_http_methods(["GET"])
def memory_list_view(request):
    """Grid of memories with status filter, q search, pagination."""
    from django.contrib.postgres.lookups import Unaccent
    from django.db.models import F, Q, Value
    from django.db.models.functions import Lower

    from memoires.models import Memory

    status = request.GET.get("status", "all")
    if status not in MEMORY_STATUS_FILTERS:
        status = "all"

    qs = Memory.objects.all()
    if status != "all":
        qs = qs.filter(status=status)

    q = (request.GET.get("q") or "").strip()[:80]
    if q:
        needle = Lower(Unaccent(Value(q)))
        qs = qs.annotate(
            caption_lc=Lower(Unaccent(F("caption"))),
            location_lc=Lower(Unaccent(F("location"))),
        ).filter(
            Q(caption_lc__contains=needle) | Q(location_lc__contains=needle)
        )

    qs = qs.order_by("-created_at", F("taken_at").desc(nulls_last=True))

    paginator = Paginator(qs, PAGE_SIZE_MEMORY)
    raw_page = request.GET.get("page", "1")
    try:
        page_number = max(1, int(raw_page))
    except (TypeError, ValueError):
        page_number = 1
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(paginator.num_pages or 1)

    return render(
        request,
        "gestion/memory_list.html",
        {
            "page": page,
            "memories": page.object_list,
            "q": q,
            "status": status,
        },
    )
```

If `Paginator`, `EmptyPage`, `PageNotAnInteger`, or `render` aren't already imported at the top of `gestion/views.py`, ensure imports include:

```python
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
```

- [ ] **Step 4.4: Create the list template**

Create `gestion/templates/gestion/memory_list.html`:

```html
{% extends "gestion/base.html" %}
{% load memory_photo %}
{% block gestion_title %}Souvenirs{% endblock %}
{% block gestion_heading %}Mur des souvenirs — curation{% endblock %}
{% block gestion_content %}
    <section aria-labelledby="filters-heading" class="mb-6">
        <h2 id="filters-heading" class="sr-only">Filtres</h2>

        <div role="group"
             aria-label="Filtrer par statut"
             class="mb-4 flex flex-wrap gap-2">
            {% for filter_value, filter_label in filter_chips %}
                <a href="?status={{ filter_value }}{% if q %}&q={{ q }}{% endif %}"
                   class="rounded-full px-3 py-1.5 text-sm border min-h-tap inline-flex items-center {% if status == filter_value %}border-tertiary bg-tertiary/10 text-tertiary font-medium{% else %}border-secondary/20 bg-base-200 text-primary hover:bg-base-300{% endif %}"
                   {% if status == filter_value %}aria-pressed="true"{% else %}aria-pressed="false"{% endif %}>
                    {{ filter_label }}
                </a>
            {% endfor %}
        </div>

        <form method="get" class="mb-4">
            {% if status != "all" %}
                <input type="hidden" name="status" value="{{ status }}">
            {% endif %}
            <input type="search"
                   name="q"
                   value="{{ q }}"
                   placeholder="Rechercher (légende ou lieu)"
                   class="block w-full md:w-96 rounded-lg border border-secondary/20 bg-white px-3 py-2 text-base shadow-sm focus:border-tertiary focus:outline-none focus:ring-2 focus:ring-tertiary/30 min-h-tap"
                   aria-label="Rechercher une photo">
        </form>

        <div class="mb-4 flex items-center justify-between">
            <p class="text-sm text-secondary">{{ page.paginator.count }} photo{{ page.paginator.count|pluralize }}</p>
            <a href="{% url 'gestion:memory_create' %}"
               class="rounded-lg bg-tertiary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-tertiary/90 min-h-tap inline-flex items-center">
                Ajouter une photo
            </a>
        </div>
    </section>

    {% if memories %}
        <ul class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" role="list">
            {% for memory in memories %}
                <li>
                    <a href="{% url 'gestion:memory_edit' pk=memory.pk %}"
                       class="block rounded-2xl border border-secondary/15 bg-surface shadow-sm hover:border-tertiary/40 hover:shadow-md transition overflow-hidden min-h-tap">
                        <figure class="aspect-square bg-base-200">
                            <img src="{% memory_photo memory.photo_public_id size=200 %}"
                                 alt="{{ memory.caption|truncatechars:80 }}"
                                 loading="lazy"
                                 class="h-full w-full object-cover">
                        </figure>
                        <div class="p-3">
                            <p class="text-sm font-medium text-primary line-clamp-2">{{ memory.caption|truncatechars:80 }}</p>
                            <p class="mt-1 text-xs text-secondary">
                                {% if memory.status == "draft" %}
                                    <span class="inline-flex items-center rounded-full bg-base-300 px-2 py-0.5 text-xs">Brouillon</span>
                                {% else %}
                                    <span class="inline-flex items-center rounded-full bg-tertiary/10 px-2 py-0.5 text-xs text-tertiary">Publiée</span>
                                {% endif %}
                                {% if memory.location %}<span class="ml-2">{{ memory.location }}</span>{% endif %}
                                {% if memory.taken_at %}<span class="ml-2">{{ memory.taken_at|date:"d F Y" }}</span>{% endif %}
                            </p>
                        </div>
                    </a>
                </li>
            {% endfor %}
        </ul>

        {% if page.has_other_pages %}
            <nav aria-label="Pagination" class="mt-6 flex items-center justify-center gap-2">
                {% if page.has_previous %}
                    <a href="?page={{ page.previous_page_number }}{% if status != 'all' %}&status={{ status }}{% endif %}{% if q %}&q={{ q }}{% endif %}"
                       class="rounded-lg border border-secondary/20 px-3 py-1.5 text-sm min-h-tap inline-flex items-center"
                       aria-label="Page précédente">Précédent</a>
                {% endif %}
                <span class="text-sm text-secondary" aria-current="page">Page {{ page.number }} sur {{ page.paginator.num_pages }}</span>
                {% if page.has_next %}
                    <a href="?page={{ page.next_page_number }}{% if status != 'all' %}&status={{ status }}{% endif %}{% if q %}&q={{ q }}{% endif %}"
                       class="rounded-lg border border-secondary/20 px-3 py-1.5 text-sm min-h-tap inline-flex items-center"
                       aria-label="Page suivante">Suivant</a>
                {% endif %}
            </nav>
        {% endif %}
    {% else %}
        <div class="rounded-2xl border border-dashed border-secondary/30 p-8 text-center">
            <p class="text-base text-primary">
                {% if status == "draft" %}Aucune photo en brouillon.
                {% elif status == "published" %}Aucune photo publiée.
                {% else %}Aucune photo.
                {% endif %}
                <a href="{% url 'gestion:memory_create' %}" class="text-tertiary underline hover:no-underline">Ajouter une photo</a> pour en créer une.
            </p>
        </div>
    {% endif %}
{% endblock %}
```

- [ ] **Step 4.5: Pass `filter_chips` to template context**

Edit `memory_list_view` to add `filter_chips` to the context (so the template's `{% for filter_value, filter_label in filter_chips %}` loop has data):

```python
    return render(
        request,
        "gestion/memory_list.html",
        {
            "page": page,
            "memories": page.object_list,
            "q": q,
            "status": status,
            "filter_chips": [
                ("all", "Toutes"),
                ("published", "Publiées"),
                ("draft", "Brouillons"),
            ],
        },
    )
```

- [ ] **Step 4.6: Verify `{% load memory_photo %}` works**

The template uses `{% memory_photo memory.photo_public_id size=200 %}`. This tag must exist in `memoires/templatetags/memory_photo.py`. Verify it returns a URL by reading the file:

Run: `grep -n "def memory_photo\|register" memoires/templatetags/memory_photo.py`

If the tag doesn't exist with the right signature, fall back to using `{{ memory.photo_public_id|memory_thumbnail_url:200 }}` (a filter) OR import `memory_thumbnail_url` into the view context. As a safe default, change the template's `<img src>` to:

```html
<img src="https://res.cloudinary.com/{{ cloud_name }}/image/upload/f_auto,q_auto:eco,c_fill,g_auto,fl_strip_profile,w_200,h_200/{{ memory.photo_public_id }}"
     ...>
```

But the cleaner solution is to use the existing memoires template tag. Read its source and use accordingly. If it expects `{% memory_photo memory size="200" %}` (with size as keyword), match the signature.

- [ ] **Step 4.7: Run list tests to verify pass**

Run: `pytest gestion/tests/test_memory_list.py -v`

Expected: All 14 tests PASS.

- [ ] **Step 4.8: Commit**

```bash
git add gestion/views.py gestion/templates/gestion/memory_list.html gestion/tests/test_memory_list.py
git commit -m "$(cat <<'EOF'
feat(gestion): memory list view — filter, search, pagination

GET /gestion/souvenirs/ — grid of photo thumbnails with:
- 3-chip status filter (Toutes / Publiées / Brouillons), default Toutes.
- ?q= search over caption + location, accent-insensitive via
  Lower(Unaccent(...)) matching the /gestion/membres/ pattern.
- Pagination at PAGE_SIZE_MEMORY = 12 (distinct from PAGE_SIZE = 20
  for text-heavy lists).
- Ordering -created_at, then taken_at DESC NULLS LAST.
- Lazy-loaded thumbnails at size=200; alt text from truncated caption.
- Helpful empty state with "Ajouter une photo" CTA.

14 list-view tests added covering all 4 user types (anon, regular
member, co-admin, super-admin), all 3 filter values + invalid fallback,
search by caption/location/accent, empty state, pagination, ordering.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `memory_create_view` + shared `memory_edit.html` template

**Files:**
- Modify: `gestion/views.py` (replace stub)
- Create: `gestion/templates/gestion/memory_edit.html` (shared with edit view, render-no-pk = create mode)
- Test: `gestion/tests/test_memory_create.py` (new)

- [ ] **Step 5.1: Write the create-view tests**

Create `gestion/tests/test_memory_create.py`:

```python
"""Tests for POST /gestion/souvenirs/nouveau/ — memory create view."""

from __future__ import annotations

from io import BytesIO
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from members.models import AuditLog
from memoires.models import Memory

pytestmark = pytest.mark.django_db


def _make_upload(*, size_bytes: int = 1024, content_type: str = "image/jpeg") -> SimpleUploadedFile:
    return SimpleUploadedFile("test.jpg", b"x" * size_bytes, content_type=content_type)


class TestMemoryCreatePermissions:
    def test_anon_redirected(self, client):
        resp = client.get("/gestion/souvenirs/nouveau/")
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_non_staff_403(self, client, regular_member_user):
        client.force_login(regular_member_user)
        resp = client.get("/gestion/souvenirs/nouveau/")
        assert resp.status_code == 403

    def test_coadmin_get_200(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/nouveau/")
        assert resp.status_code == 200

    def test_superadmin_get_200(self, client, superadmin_user):
        client.force_login(superadmin_user)
        resp = client.get("/gestion/souvenirs/nouveau/")
        assert resp.status_code == 200


class TestMemoryCreateHappyPath:
    def test_create_draft_persists_memory(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client
        reset_fake_client()
        client.force_login(coadmin_user)
        # Django's test client auto-encodes multipart when an UploadedFile is
        # present in data — do NOT pass files= or format= kwargs.
        resp = client.post(
            "/gestion/souvenirs/nouveau/",
            data={
                "caption": "Sortie 1983",
                "taken_at": "",
                "location": "Birni",
                "status": "draft",
                "upload": _make_upload(),
            },
        )
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=created"
        memory = Memory.objects.get(caption="Sortie 1983")
        assert memory.status == "draft"
        assert memory.location == "Birni"
        assert memory.created_by == coadmin_user
        assert memory.photo_public_id.startswith("memoires/")

    def test_create_emits_one_audit_row_for_draft(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client
        reset_fake_client()
        client.force_login(coadmin_user)
        client.post(
            "/gestion/souvenirs/nouveau/",
            data={
                "caption": "Draft photo",
                "location": "",
                "status": "draft",
                "taken_at": "",
                "upload": _make_upload(),
            },
        )
        rows = list(AuditLog.objects.filter(action="memoires.memory.created"))
        assert len(rows) == 1
        assert rows[0].metadata["initial_status"] == "draft"
        assert rows[0].metadata["caption_preview"] == "Draft photo"
        assert rows[0].metadata["public_id"].startswith("memoires/")
        # No standalone .published row for create-draft
        assert not AuditLog.objects.filter(action="memoires.memory.published").exists()

    def test_create_emits_one_audit_row_for_published(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client
        reset_fake_client()
        client.force_login(coadmin_user)
        client.post(
            "/gestion/souvenirs/nouveau/",
            data={
                "caption": "Published from create",
                "location": "",
                "status": "published",
                "taken_at": "",
                "upload": _make_upload(),
            },
        )
        created_rows = list(AuditLog.objects.filter(action="memoires.memory.created"))
        assert len(created_rows) == 1
        assert created_rows[0].metadata["initial_status"] == "published"
        # Key contract: NO separate .published row at create time.
        assert not AuditLog.objects.filter(action="memoires.memory.published").exists()


class TestMemoryCreateValidation:
    def test_no_upload_re_renders_with_error(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.post("/gestion/souvenirs/nouveau/", data={
            "caption": "x",
            "location": "",
            "status": "draft",
            "taken_at": "",
        })
        assert resp.status_code == 200
        assert Memory.objects.count() == 0
        assert not AuditLog.objects.filter(action="memoires.memory.created").exists()

    def test_oversize_upload_re_renders_with_error(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        client.force_login(coadmin_user)
        big = _make_upload(size_bytes=9 * 1024 * 1024)
        resp = client.post("/gestion/souvenirs/nouveau/", data={
            "caption": "x",
            "location": "",
            "status": "draft",
            "taken_at": "",
            "upload": big,
        })
        assert resp.status_code == 200
        assert Memory.objects.count() == 0

    def test_cloudinary_failure_surfaces_to_form(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client
        reset_fake_client()
        client.force_login(coadmin_user)
        with mock.patch(
            "alumni.cloudinary.FakeCloudinary.upload_file",
            side_effect=RuntimeError("simulated cloudinary outage"),
        ):
            resp = client.post(
                "/gestion/souvenirs/nouveau/",
                data={
                    "caption": "x",
                    "location": "",
                    "status": "draft",
                    "taken_at": "",
                    "upload": _make_upload(),
                },
            )
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Échec" in body or "réessayez" in body.lower()
        assert Memory.objects.count() == 0
        assert not AuditLog.objects.filter(action="memoires.memory.created").exists()
```

- [ ] **Step 5.2: Run tests to verify failures**

Run: `pytest gestion/tests/test_memory_create.py -v`

Expected: All tests FAIL — view is still the 501 stub.

- [ ] **Step 5.3: Implement `memory_create_view`**

Edit `gestion/views.py`. Replace the `memory_create_view` stub:

```python
@staff_required
@require_http_methods(["GET", "POST"])
def memory_create_view(request):
    """Create a new Memory. Upload goes through Cloudinary first; DB write +
    AuditLog are atomic. Redirects to list with ?flash=created on success."""
    from django.db import transaction
    from alumni.cloudinary import get_client
    from gestion.forms import GestionMemoryForm
    from members.models import AuditLog
    from memoires.models import Memory

    if request.method == "POST":
        form = GestionMemoryForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["upload"]
            client = get_client()
            try:
                new_public_id = client.upload_file(upload, folder="memoires")
            except Exception as exc:  # noqa: BLE001
                form.add_error(
                    "upload",
                    "Échec du téléversement. Vérifiez votre connexion et réessayez.",
                )
                logger.warning("memory_create_view: Cloudinary upload failed: %s", exc)
            else:
                if not new_public_id:
                    raise RuntimeError(
                        "Cloudinary returned empty public_id; refusing to write"
                    )
                with transaction.atomic():
                    memory = Memory.objects.create(
                        photo_public_id=new_public_id,
                        caption=form.cleaned_data["caption"],
                        taken_at=form.cleaned_data["taken_at"] or None,
                        location=form.cleaned_data["location"] or "",
                        status=form.cleaned_data["status"],
                        created_by=request.user,
                    )
                    AuditLog.objects.create(
                        actor=request.user,
                        action="memoires.memory.created",
                        target_type="memoires.Memory",
                        target_id=str(memory.pk),
                        metadata={
                            "caption_preview": memory.caption[:60],
                            "location": memory.location,
                            "taken_at": memory.taken_at.isoformat() if memory.taken_at else None,
                            "public_id": memory.photo_public_id,
                            "initial_status": memory.status,
                        },
                    )
                return HttpResponseRedirect("/gestion/souvenirs/?flash=created")
    else:
        form = GestionMemoryForm()

    return render(
        request,
        "gestion/memory_edit.html",
        {
            "form": form,
            "memory": None,  # signals create mode to the template
        },
    )
```

If `logger` isn't already a module-level definition in `gestion/views.py`, add to imports:

```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 5.4: Create the shared `memory_edit.html` template**

Create `gestion/templates/gestion/memory_edit.html`:

```html
{% extends "gestion/base.html" %}
{% load memory_photo %}
{% block gestion_title %}{% if memory %}Modifier{% else %}Nouvelle photo{% endif %}{% endblock %}
{% block gestion_heading %}{% if memory %}Modifier la photo{% else %}Ajouter une photo{% endif %}{% endblock %}
{% block gestion_content %}
    {% if memory %}
        <figure class="mb-6 rounded-2xl overflow-hidden border border-secondary/15 bg-base-200">
            <img src="{% memory_photo memory.photo_public_id size=400 %}"
                 alt="{{ memory.caption }}"
                 class="w-full h-auto max-h-[500px] object-contain bg-base-200">
            <figcaption class="px-4 py-2 text-xs text-secondary border-t border-secondary/15">
                {% if memory.status == "draft" %}Brouillon{% else %}Publiée{% endif %}
                · ajoutée le {{ memory.created_at|date:"d F Y" }}
                {% if memory.location %}· {{ memory.location }}{% endif %}
            </figcaption>
        </figure>
    {% endif %}

    <form method="post" enctype="multipart/form-data" class="space-y-4" novalidate>
        {% csrf_token %}

        <div>
            <label for="id_upload" class="block text-sm font-medium text-primary">
                {% if memory %}Remplacer la photo{% else %}Photo{% endif %}
            </label>
            {{ form.upload }}
            {% if form.upload.help_text %}
                <p class="mt-1 text-xs text-secondary">{{ form.upload.help_text }}</p>
            {% endif %}
            {% if form.upload.errors %}
                <p class="mt-1 text-sm text-error">{{ form.upload.errors|join:" " }}</p>
            {% endif %}
        </div>

        <div>
            <label for="id_caption" class="block text-sm font-medium text-primary">Légende</label>
            {{ form.caption }}
            {% if form.caption.errors %}
                <p class="mt-1 text-sm text-error">{{ form.caption.errors|join:" " }}</p>
            {% endif %}
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label for="id_taken_at" class="block text-sm font-medium text-primary">Date approximative</label>
                {{ form.taken_at }}
                <p class="mt-1 text-xs text-secondary">Laissez vide si vous ne savez pas.</p>
                {% if form.taken_at.errors %}
                    <p class="mt-1 text-sm text-error">{{ form.taken_at.errors|join:" " }}</p>
                {% endif %}
            </div>
            <div>
                <label for="id_location" class="block text-sm font-medium text-primary">Lieu</label>
                {{ form.location }}
                {% if form.location.errors %}
                    <p class="mt-1 text-sm text-error">{{ form.location.errors|join:" " }}</p>
                {% endif %}
            </div>
        </div>

        <div>
            <label for="id_status" class="block text-sm font-medium text-primary">Statut</label>
            {{ form.status }}
            {% if form.status.errors %}
                <p class="mt-1 text-sm text-error">{{ form.status.errors|join:" " }}</p>
            {% endif %}
        </div>

        {% if form.non_field_errors %}
            <p class="text-sm text-error">{{ form.non_field_errors|join:" " }}</p>
        {% endif %}

        <div class="flex flex-wrap gap-3 pt-4">
            <button type="submit"
                    class="rounded-lg bg-tertiary px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-tertiary/90 min-h-tap">
                {% if memory %}Enregistrer{% else %}Créer{% endif %}
            </button>
            <a href="{% url 'gestion:memory_list' %}"
               class="rounded-lg border border-secondary/20 bg-base-200 px-5 py-2.5 text-sm text-primary hover:bg-base-300 min-h-tap inline-flex items-center">
                Annuler
            </a>
        </div>
    </form>

    {% if memory %}
        <section class="mt-8 pt-6 border-t border-secondary/15">
            <h2 class="text-lg font-medium text-primary mb-3">Statut</h2>
            <form method="post" action="{% url 'gestion:memory_status' pk=memory.pk %}" class="flex flex-wrap gap-3">
                {% csrf_token %}
                {% if memory.status == "draft" %}
                    <button type="submit" name="target_status" value="published"
                            class="rounded-lg bg-tertiary px-4 py-2 text-sm font-medium text-white hover:bg-tertiary/90 min-h-tap">
                        Publier
                    </button>
                {% else %}
                    <button type="submit" name="target_status" value="draft"
                            class="rounded-lg border border-secondary/20 bg-base-200 px-4 py-2 text-sm text-primary hover:bg-base-300 min-h-tap">
                        Dépublier
                    </button>
                {% endif %}
            </form>
        </section>
    {% endif %}
{% endblock %}
```

- [ ] **Step 5.5: Run tests to verify pass**

Run: `pytest gestion/tests/test_memory_create.py -v`

Expected: All create-view tests PASS.

- [ ] **Step 5.6: Commit**

```bash
git add gestion/views.py gestion/templates/gestion/memory_edit.html gestion/tests/test_memory_create.py
git commit -m "$(cat <<'EOF'
feat(gestion): memory create view + shared edit template

POST /gestion/souvenirs/nouveau/ uploads via Cloudinary then atomically
writes Memory + AuditLog rows. Redirects to list with ?flash=created.

- Upload happens BEFORE the transaction.atomic() block; if the DB
  write rolls back, the Cloudinary blob is orphaned (documented in
  spec §I Risk #2, consistent with memoires/admin.py).
- Defensive empty-public_id check after upload (contract drift safety).
- Cloudinary failure: form.add_error("upload", "Échec du téléversement…")
  + re-render with the file lost (operator re-picks).
- Status-on-create: emits ONE .created row with initial_status in
  metadata. NO separate .published row when status=published was chosen
  at create — the .created event captures it via metadata.
- Shared memory_edit.html template renders form for both create (no
  pk, no photo preview) and edit modes (pk + photo preview at size=400
  + status-toggle subform).

12 create-view tests added covering permissions (4 user types), happy
path (draft + published), AuditLog emission rules, no-upload rejection,
oversize rejection, Cloudinary failure path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `memory_edit_view` (GET prefill + POST with photo replace, no-op, status emission)

**Files:**
- Modify: `gestion/views.py` (replace stub)
- Test: `gestion/tests/test_memory_edit.py` (new)

- [ ] **Step 6.1: Write the edit-view tests**

Create `gestion/tests/test_memory_edit.py`:

```python
"""Tests for /gestion/souvenirs/<pk>/modifier/ — memory edit view."""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile

import pytest

from members.models import AuditLog
from memoires.models import Memory

pytestmark = pytest.mark.django_db


def _make_upload(content_type: str = "image/jpeg") -> SimpleUploadedFile:
    return SimpleUploadedFile("new.jpg", b"x" * 1024, content_type=content_type)


class TestMemoryEditPermissions:
    def test_anon_redirected(self, client, make_memory):
        m = make_memory()
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        assert resp.status_code == 302

    def test_non_staff_403(self, client, regular_member_user, make_memory):
        m = make_memory()
        client.force_login(regular_member_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        assert resp.status_code == 403

    def test_coadmin_get_200(self, client, coadmin_user, make_memory):
        m = make_memory()
        client.force_login(coadmin_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        assert resp.status_code == 200

    def test_unknown_pk_404(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/999999/modifier/")
        assert resp.status_code == 404


class TestMemoryEditGet:
    def test_get_prefills_form_fields(self, client, coadmin_user, make_memory):
        m = make_memory(caption="Original caption", location="Niamey", status="published")
        client.force_login(coadmin_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        body = resp.content.decode()
        assert "Original caption" in body
        assert "Niamey" in body

    def test_get_renders_photo_preview(self, client, coadmin_user, make_memory):
        m = make_memory()
        client.force_login(coadmin_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        body = resp.content.decode()
        assert m.photo_public_id in body


class TestMemoryEditFieldsOnly:
    def test_edit_caption_emits_one_edited_row(self, client, coadmin_user, make_memory):
        m = make_memory(caption="Original", status="published")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/modifier/", data={
            "caption": "Updated caption",
            "location": m.location,
            "status": m.status,
            "taken_at": "",
        })
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=updated"
        m.refresh_from_db()
        assert m.caption == "Updated caption"
        rows = AuditLog.objects.filter(action="memoires.memory.edited")
        assert rows.count() == 1
        assert "caption" in rows.first().metadata["changed_fields"]
        assert rows.first().metadata["photo_replaced"] is False

    def test_edit_no_changes_emits_no_rows(self, client, coadmin_user, make_memory):
        m = make_memory(caption="Same", location="Niamey", status="published")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/modifier/", data={
            "caption": m.caption,
            "location": m.location,
            "status": m.status,
            "taken_at": "",
        })
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=noop"
        assert AuditLog.objects.filter(action="memoires.memory.edited").count() == 0
        assert AuditLog.objects.filter(action="memoires.memory.published").count() == 0
        assert AuditLog.objects.filter(action="memoires.memory.unpublished").count() == 0


class TestMemoryEditPhotoReplace:
    def test_replace_photo_triggers_old_id_delete(self, client, coadmin_user, make_memory, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import get_client, reset_fake_client
        reset_fake_client()

        m = make_memory(photo_public_id="memoires/old-id-here", status="published")
        old_id = m.photo_public_id
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/modifier/", data={
            "caption": m.caption,
            "location": m.location,
            "status": m.status,
            "taken_at": "",
            "upload": _make_upload(),
        })
        assert resp.status_code == 302
        m.refresh_from_db()
        assert m.photo_public_id != old_id
        # on_commit fired by transaction.atomic context exit
        fake = get_client()
        assert old_id in fake.delete_calls
        # Edited row with photo_replaced=True, changed_fields=[]
        edited = AuditLog.objects.get(action="memoires.memory.edited")
        assert edited.metadata["photo_replaced"] is True
        assert edited.metadata["changed_fields"] == []


class TestMemoryEditStatusFlip:
    def test_status_only_flip_via_edit_form_emits_only_status_row(self, client, coadmin_user, make_memory):
        m = make_memory(status="draft")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/modifier/", data={
            "caption": m.caption,
            "location": m.location,
            "status": "published",
            "taken_at": "",
        })
        assert resp.status_code == 302
        m.refresh_from_db()
        assert m.status == "published"
        # No .edited because only status changed
        assert AuditLog.objects.filter(action="memoires.memory.edited").count() == 0
        assert AuditLog.objects.filter(action="memoires.memory.published").count() == 1

    def test_field_change_plus_status_flip_emits_two_rows(self, client, coadmin_user, make_memory):
        m = make_memory(caption="Old", status="draft")
        client.force_login(coadmin_user)
        client.post(f"/gestion/souvenirs/{m.pk}/modifier/", data={
            "caption": "New",
            "location": m.location,
            "status": "published",
            "taken_at": "",
        })
        assert AuditLog.objects.filter(action="memoires.memory.edited").count() == 1
        assert AuditLog.objects.filter(action="memoires.memory.published").count() == 1
```

- [ ] **Step 6.2: Run tests to verify failures**

Run: `pytest gestion/tests/test_memory_edit.py -v`

Expected: All FAIL — view is still the 501 stub.

- [ ] **Step 6.3: Implement `memory_edit_view`**

Edit `gestion/views.py`. Replace the `memory_edit_view` stub:

```python
WATCH_FIELDS = ("caption", "taken_at", "location", "status", "photo_public_id")


@staff_required
@require_http_methods(["GET", "POST"])
def memory_edit_view(request, pk):
    """Edit an existing Memory. Photo replace optional. Detects no-op edits;
    emits 1 row per logical event (edited + optional status transition)."""
    from django.db import transaction
    from alumni.cloudinary import get_client
    from gestion.forms import GestionMemoryForm
    from members.models import AuditLog
    from memoires.models import Memory

    memory = get_object_or_404(Memory, pk=pk)

    if request.method == "POST":
        form = GestionMemoryForm(request.POST, request.FILES, instance=memory)
        if form.is_valid():
            upload = form.cleaned_data.get("upload")
            new_public_id = None
            if upload:
                client = get_client()
                try:
                    new_public_id = client.upload_file(upload, folder="memoires")
                except Exception as exc:  # noqa: BLE001
                    form.add_error(
                        "upload",
                        "Échec du téléversement. Vérifiez votre connexion et réessayez.",
                    )
                    logger.warning("memory_edit_view: Cloudinary upload failed: %s", exc)
                    new_public_id = None
                else:
                    if not new_public_id:
                        raise RuntimeError(
                            "Cloudinary returned empty public_id; refusing to write"
                        )

            if form.is_valid():  # re-check after the optional add_error above
                with transaction.atomic():
                    locked = Memory.objects.select_for_update().get(pk=memory.pk)
                    old_id = locked.photo_public_id
                    pre = {f: getattr(locked, f) for f in WATCH_FIELDS}

                    # Apply form changes onto the locked instance.
                    if new_public_id:
                        locked.photo_public_id = new_public_id
                    for field_name in form.changed_data:
                        if field_name == "upload":
                            continue
                        setattr(locked, field_name, form.cleaned_data[field_name])

                    post = {f: getattr(locked, f) for f in WATCH_FIELDS}

                    if pre == post and not new_public_id:
                        # True no-op — bail without DB writes or audit rows.
                        return HttpResponseRedirect("/gestion/souvenirs/?flash=noop")

                    locked.save()

                    changed_fields = [
                        f for f in form.changed_data
                        if f not in ("upload", "status")
                    ]
                    photo_replaced = bool(new_public_id)
                    fields_changed = bool(changed_fields) or photo_replaced
                    status_changed = pre["status"] != post["status"]

                    if fields_changed:
                        AuditLog.objects.create(
                            actor=request.user,
                            action="memoires.memory.edited",
                            target_type="memoires.Memory",
                            target_id=str(locked.pk),
                            metadata={
                                "caption_preview": locked.caption[:60],
                                "public_id": locked.photo_public_id,
                                "changed_fields": changed_fields,
                                "photo_replaced": photo_replaced,
                            },
                        )

                    if status_changed:
                        action = (
                            "memoires.memory.published"
                            if post["status"] == "published"
                            else "memoires.memory.unpublished"
                        )
                        AuditLog.objects.create(
                            actor=request.user,
                            action=action,
                            target_type="memoires.Memory",
                            target_id=str(locked.pk),
                            metadata={
                                "caption_preview": locked.caption[:60],
                                "public_id": locked.photo_public_id,
                                "previous_status": pre["status"],
                            },
                        )

                    if new_public_id and old_id:
                        def _delete_old(old=old_id):
                            try:
                                get_client().delete(old)
                            except Exception as exc:  # noqa: BLE001
                                logger.warning(
                                    "memory_edit_view: post-commit delete of %s failed: %s",
                                    old, exc,
                                )
                        transaction.on_commit(_delete_old)

                return HttpResponseRedirect("/gestion/souvenirs/?flash=updated")
    else:
        form = GestionMemoryForm(instance=memory)

    return render(
        request,
        "gestion/memory_edit.html",
        {"form": form, "memory": memory},
    )
```

- [ ] **Step 6.4: Run tests to verify pass**

Run: `pytest gestion/tests/test_memory_edit.py -v`

Expected: All 11 edit-view tests PASS.

- [ ] **Step 6.5: Commit**

```bash
git add gestion/views.py gestion/tests/test_memory_edit.py
git commit -m "$(cat <<'EOF'
feat(gestion): memory edit view — photo replace + no-op + status emissions

POST /gestion/souvenirs/<pk>/modifier/ handles:
- Field-only edit → 1 .edited row with changed_fields.
- Field change + status flip → 2 rows (.edited + .published/.unpublished).
- Photo replace (with or without field changes) → .edited row with
  photo_replaced=True; old Cloudinary blob queued for deletion via
  transaction.on_commit(...).
- Status-only flip via edit form → 1 row (.published/.unpublished),
  NO .edited row (nothing else changed).
- No-op (zero diffs, no upload) → redirect to ?flash=noop, ZERO rows.

Implementation:
- Cloudinary upload happens BEFORE the atomic block.
- Inside the block: select_for_update() locks the Memory row; pre/post
  WATCH_FIELDS snapshots detect what changed.
- Old-photo delete via transaction.on_commit(...) — fires after commit;
  failure is swallowed with logger.warning (orphan accepted).
- Audit metadata always carries caption_preview + public_id; .edited
  carries changed_fields + photo_replaced; status events carry
  previous_status.

11 edit-view tests covering permissions, GET prefill, field-only edit,
no-op detection, photo replace + on_commit delete, status flip
emission rules.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `memory_status_view`

**Files:**
- Modify: `gestion/views.py` (replace stub)
- Test: `gestion/tests/test_memory_status.py` (new)

- [ ] **Step 7.1: Write the status-view tests**

Create `gestion/tests/test_memory_status.py`:

```python
"""Tests for POST /gestion/souvenirs/<pk>/statut/ — memory status toggle."""

from __future__ import annotations

import pytest

from members.models import AuditLog
from memoires.models import Memory

pytestmark = pytest.mark.django_db


class TestMemoryStatusPermissions:
    def test_anon_redirected(self, client, make_memory):
        m = make_memory()
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "draft"})
        assert resp.status_code == 302

    def test_non_staff_403(self, client, regular_member_user, make_memory):
        m = make_memory()
        client.force_login(regular_member_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "draft"})
        assert resp.status_code == 403

    def test_get_405(self, client, coadmin_user, make_memory):
        m = make_memory()
        client.force_login(coadmin_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/statut/")
        assert resp.status_code == 405

    def test_unknown_pk_404(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.post("/gestion/souvenirs/999999/statut/", data={"target_status": "draft"})
        assert resp.status_code == 404


class TestMemoryStatusToggle:
    def test_publish_a_draft(self, client, coadmin_user, make_memory):
        m = make_memory(status="draft")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "published"})
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=published"
        m.refresh_from_db()
        assert m.status == "published"
        row = AuditLog.objects.get(action="memoires.memory.published")
        assert row.metadata["previous_status"] == "draft"
        assert row.metadata["public_id"] == m.photo_public_id

    def test_unpublish_a_published(self, client, coadmin_user, make_memory):
        m = make_memory(status="published")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "draft"})
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=unpublished"
        m.refresh_from_db()
        assert m.status == "draft"
        row = AuditLog.objects.get(action="memoires.memory.unpublished")
        assert row.metadata["previous_status"] == "published"

    def test_target_equals_current_is_noop(self, client, coadmin_user, make_memory):
        m = make_memory(status="published")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "published"})
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=noop"
        m.refresh_from_db()
        assert m.status == "published"
        assert AuditLog.objects.filter(target_id=str(m.pk)).count() == 0

    def test_bad_target_status(self, client, coadmin_user, make_memory):
        m = make_memory(status="draft")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "archived"})
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=bad_status"
        m.refresh_from_db()
        assert m.status == "draft"
        assert AuditLog.objects.filter(target_id=str(m.pk)).count() == 0
```

- [ ] **Step 7.2: Run tests to verify failures**

Run: `pytest gestion/tests/test_memory_status.py -v`

Expected: All FAIL — view is still the 501 stub.

- [ ] **Step 7.3: Implement `memory_status_view`**

Edit `gestion/views.py`. Replace the `memory_status_view` stub:

```python
MEMORY_VALID_TARGETS = ("draft", "published")


@staff_required
@require_http_methods(["POST"])
def memory_status_view(request, pk):
    """Toggle Memory.status between 'draft' and 'published'.
    Mirrors member_status_view's noop / bad_status branches."""
    from django.db import transaction
    from members.models import AuditLog
    from memoires.models import Memory

    target = request.POST.get("target_status", "").strip()
    if target not in MEMORY_VALID_TARGETS:
        return HttpResponseRedirect("/gestion/souvenirs/?flash=bad_status")

    memory = get_object_or_404(Memory, pk=pk)

    with transaction.atomic():
        locked = Memory.objects.select_for_update().get(pk=memory.pk)
        if locked.status == target:
            return HttpResponseRedirect("/gestion/souvenirs/?flash=noop")
        previous = locked.status
        locked.status = target
        locked.save(update_fields=["status", "updated_at"])

        action = (
            "memoires.memory.published"
            if target == "published"
            else "memoires.memory.unpublished"
        )
        AuditLog.objects.create(
            actor=request.user,
            action=action,
            target_type="memoires.Memory",
            target_id=str(locked.pk),
            metadata={
                "caption_preview": locked.caption[:60],
                "public_id": locked.photo_public_id,
                "previous_status": previous,
            },
        )

    flash = "published" if target == "published" else "unpublished"
    return HttpResponseRedirect(f"/gestion/souvenirs/?flash={flash}")
```

- [ ] **Step 7.4: Run tests to verify pass**

Run: `pytest gestion/tests/test_memory_status.py -v`

Expected: All 8 tests PASS.

- [ ] **Step 7.5: Commit**

```bash
git add gestion/views.py gestion/tests/test_memory_status.py
git commit -m "$(cat <<'EOF'
feat(gestion): memory status toggle view

POST /gestion/souvenirs/<pk>/statut/ with target_status ∈ {draft, published}:
- Valid + status changes → save + emit .published or .unpublished row,
  redirect with ?flash=published or ?flash=unpublished.
- Valid + status == current → ?flash=noop, no audit row.
- Invalid target → ?flash=bad_status, no audit row.
- GET → 405 (POST-only).

Wraps the DB write + audit emission in transaction.atomic() with
select_for_update() to serialize concurrent toggles.

8 status-view tests cover permissions (anon, non-staff, GET 405,
unknown pk 404), happy paths (publish + unpublish, audit metadata),
noop, bad_status.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Dashboard 4th tile + subnav + flash messages + XSS regression

**Files:**
- Modify: `gestion/views.py:46-55` (`dashboard_view` — add `draft_memories` KPI)
- Modify: `gestion/templates/gestion/dashboard.html` (grid + 4th tile)
- Modify: `gestion/templates/gestion/base.html` (subnav link + flash map)
- Test: `gestion/tests/test_dashboard.py` (extend)
- Test: `gestion/tests/test_caption_xss_safe.py` (new)

- [ ] **Step 8.1: Write the dashboard extension tests**

Open `gestion/tests/test_dashboard.py` and append:

```python
class TestDashboardMemoriesTile:
    def test_tile_shows_zero_when_no_drafts(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/")
        body = resp.content.decode()
        assert "Souvenirs" in body or "Brouillons" in body
        # Tile renders even at 0 (intentional, per spec).

    def test_tile_count_matches_draft_count(self, client, coadmin_user, make_memory):
        make_memory(status="draft")
        make_memory(status="draft")
        make_memory(status="published")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/")
        body = resp.content.decode()
        # Count of 2 should appear near the Brouillons label.
        # Loose assertion to avoid HTML brittleness:
        assert '>2<' in body or '"2"' in body or 'data-count="2"' in body

    def test_tile_links_to_draft_filtered_list(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/")
        body = resp.content.decode()
        assert "/gestion/souvenirs/?status=draft" in body
```

- [ ] **Step 8.2: Write the XSS regression test**

Create `gestion/tests/test_caption_xss_safe.py`:

```python
"""Regression: Memory.caption is ALWAYS plain text. Never markdown, never HTML.

If a future PR adds markdown rendering of captions, these tests catch it
before it ships.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

XSS_CAPTION = "<script>alert('xss')</script>"


def test_caption_escaped_on_public_souvenirs(client, regular_member_user, make_memory):
    make_memory(caption=XSS_CAPTION, status="published")
    client.force_login(regular_member_user)
    resp = client.get("/souvenirs/")
    body = resp.content.decode()
    assert "<script>alert" not in body
    assert "&lt;script&gt;" in body or "&lt;script" in body


def test_caption_escaped_on_gestion_list_alt(client, coadmin_user, make_memory):
    make_memory(caption=XSS_CAPTION, status="published")
    client.force_login(coadmin_user)
    resp = client.get("/gestion/souvenirs/")
    body = resp.content.decode()
    assert "<script>alert" not in body


def test_caption_escaped_on_gestion_edit(client, coadmin_user, make_memory):
    m = make_memory(caption=XSS_CAPTION, status="published")
    client.force_login(coadmin_user)
    resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
    body = resp.content.decode()
    # In a <textarea>, the content is auto-escaped by Django.
    assert "<script>alert" not in body
    # The escaped variant must be present somewhere (form value or img alt).
    assert "&lt;script" in body
```

- [ ] **Step 8.3: Run tests to verify failures**

Run: `pytest gestion/tests/test_dashboard.py::TestDashboardMemoriesTile gestion/tests/test_caption_xss_safe.py -v`

Expected: Dashboard tile tests FAIL (dashboard hasn't been extended yet). XSS tests may pass (auto-escaping is on by default); if so, the regression test still has value.

- [ ] **Step 8.4: Extend `dashboard_view`**

Edit `gestion/views.py`. Find `def dashboard_view(request)` and update:

```python
@staff_required
def dashboard_view(request):
    """Landing page — KPI tiles + nav to the section pages."""
    from memoires.models import Memory

    kpis = {
        "active_members": Member.objects.filter(status="active").count(),
        "suspended_members": Member.objects.filter(status="suspended").count(),
        "pending_cooptations": AdminApplication.objects.filter(
            status__in=("cooptation_pending", "awaiting_admin")
        ).count(),
        "draft_memories": Memory.objects.filter(status="draft").count(),
    }
    return render(request, "gestion/dashboard.html", {"kpis": kpis})
```

- [ ] **Step 8.5: Add the 4th tile to the dashboard template**

Edit `gestion/templates/gestion/dashboard.html`. Replace the `<div class="grid grid-cols-1 gap-4 md:grid-cols-3">` opener with `md:grid-cols-2 lg:grid-cols-4`:

```html
<div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
```

Then add this 4th tile inside that grid (after the third tile `<a>` block, before the `</div>` that closes the grid):

```html
            <a href="/gestion/souvenirs/?status=draft"
               data-kpi="draft-memories"
               data-count="{{ kpis.draft_memories }}"
               class="rounded-2xl border border-secondary/15 bg-surface p-5 shadow-sm transition hover:border-tertiary/40 hover:shadow-md">
                <p class="text-[11px] font-semibold uppercase tracking-[0.18em] text-secondary">Souvenirs en brouillon</p>
                <p class="mt-2 font-display text-3xl font-semibold text-tertiary">
                    {{ kpis.draft_memories }} <span class="text-base font-normal text-primary">photo{{ kpis.draft_memories|pluralize }}</span>
                </p>
                <p class="mt-2 text-sm text-secondary">Photos téléversées, en attente de publication.</p>
            </a>
```

Also extend the helper list at the bottom of the dashboard:

```html
            <li>
                <strong>Souvenirs</strong> — ajouter, modifier, publier ou dépublier les photos du Mur des souvenirs.
            </li>
```

- [ ] **Step 8.6: Add Souvenirs subnav link + flash messages to `base.html`**

Edit `gestion/templates/gestion/base.html`. After the `Cooptations` `<a>` link (around line 22), add:

```html
            <a href="/gestion/souvenirs/"
               class="rounded-lg px-3 py-2 min-h-tap hover:bg-base-200 hover:text-tertiary transition">Souvenirs</a>
```

Then locate the flash-message rendering block (search for `request.GET.flash` or similar; if absent, add this block just above `{% block gestion_content %}{% endblock %}`):

```html
{% with flash=request.GET.flash %}
    {% if flash %}
        <div class="mb-4 rounded-lg border border-tertiary/30 bg-tertiary/5 px-4 py-2.5 text-sm text-tertiary" role="status" aria-live="polite">
            {% if flash == "created" %}Photo créée.
            {% elif flash == "updated" %}Photo mise à jour.
            {% elif flash == "published" %}Photo publiée.
            {% elif flash == "unpublished" %}Photo dépubliée.
            {% elif flash == "noop" %}Aucune modification.
            {% elif flash == "bad_status" %}Statut invalide.
            {% else %}{{ flash }}
            {% endif %}
        </div>
    {% endif %}
{% endwith %}
```

(If the existing `base.html` already renders flash messages for other gestion flows like `gestion.member.suspended`, extend the existing block to add the new keys rather than duplicate the markup.)

- [ ] **Step 8.7: Run dashboard + XSS tests to verify pass**

Run: `pytest gestion/tests/test_dashboard.py gestion/tests/test_caption_xss_safe.py -v`

Expected: All tests PASS (3 new dashboard tile tests + 3 XSS regression tests).

- [ ] **Step 8.8: Commit**

```bash
git add gestion/views.py gestion/templates/gestion/dashboard.html gestion/templates/gestion/base.html gestion/tests/test_dashboard.py gestion/tests/test_caption_xss_safe.py
git commit -m "$(cat <<'EOF'
feat(gestion): souvenirs dashboard tile + subnav + flash + xss regression

- Dashboard: 4th KPI tile shows count of drafts; clicks through to
  /gestion/souvenirs/?status=draft. Grid bumps md:grid-cols-3 →
  md:grid-cols-2 lg:grid-cols-4. Tile renders count even at 0 to
  keep the section discoverable (spec §G locked decision).
- Subnav: "Souvenirs" link added after Cooptations.
- Flash messages: 6 new keys (created, updated, published,
  unpublished, noop, bad_status) wired into the existing
  ?flash= rendering map with French copy.
- XSS regression test: Memory.caption containing <script> tag must
  render escaped on (a) public /souvenirs/, (b) /gestion/souvenirs/
  list view (alt attr), (c) /gestion/souvenirs/<pk>/modifier/
  (textarea + photo preview alt). Prevents a future "let's add
  markdown to captions" PR from regressing this.

3 dashboard tile tests + 3 XSS regression tests added.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Full suite + STATUS.md + manual smoke + merge prep

**Files:**
- Modify: `docs/superpowers/STATUS.md` (new row in §Post-launch polish table + trajectory bump)

- [ ] **Step 9.1: Run the full pytest suite**

Run: `make test`

Expected: All tests pass. The plan adds ~57 tests across 6 new files + extensions, so total runs ~764 (current 707 + plan's 57). The spec's original "+28 / 735" estimate was conservative; the plan ended up with more granular coverage. If a test count > or < estimate by a small margin, that's fine — the goal is zero failures, not a specific count.

- [ ] **Step 9.2: Run linting**

Run: `make lint`

Expected: No ruff errors. If ruff complains about import-order or unused-import in the new view module, run `make format` to auto-fix.

- [ ] **Step 9.3: Manual smoke tests** (run before opening PR — checklist from spec §J)

Each item is a manual browser test:

- Boot staging stack: `make docker-run` (note: needs Docker; basic-auth `admin / compose-test-pw`).
- Visit `http://localhost:8000/admin/` and create a co-admin user manually (`is_staff=True, is_superuser=False`) OR log in as super-admin.
- Visit `http://localhost:8000/gestion/souvenirs/` — list view should render empty state.
- Click "Ajouter une photo" → upload a 1–6 MB JPEG → choose "Brouillon" → submit. Verify redirect to list with green flash banner. Verify draft appears in list filtered by `?status=draft`.
- Click into the new photo → change caption → save. Verify flash "Photo mise à jour."
- Same edit page → upload a replacement photo → save. Verify replacement appears in list. Verify old Cloudinary URL eventually 404s.
- On edit page → click "Publier". Verify redirect with `?flash=published`. Visit `/souvenirs/` (logged in as member) — photo appears.
- Visit `/admin/members/auditlog/` (super-admin) — verify 4 audit rows: `.created`, `.edited` (caption change), `.edited` (photo replace, photo_replaced=True), `.published`.
- Inspect a rendered `<img src>` on `/souvenirs/`, `/souvenirs/<pk>/`, `/gestion/souvenirs/`, `/gestion/souvenirs/<pk>/modifier/` — each URL contains `fl_strip_profile`.
- Open `http://localhost:8000/gestion/souvenirs/` on Chrome DevTools mobile view (360 × 800) — every tap target ≥ 44 px, no horizontal scroll.

- [ ] **Step 9.4: Update `docs/superpowers/STATUS.md`**

In `docs/superpowers/STATUS.md`, find the §Post-launch polish table (look for `## Post-launch polish (post-v1.0.0-soft-launch)`). Insert a new row at the top (after the header row, before the existing 2026-05-09 handbook row):

```markdown
| 2026-05-10 | `feat/gestion-souvenirs` (9 commits) | `<merge SHA>` | **Co-admin Mur des souvenirs management on `/gestion/`** — full parity with super-admin: list with filter/search/pagination, create with upload, edit with photo replace, publish/unpublish toggle. 4 routes under `/gestion/souvenirs/`. New 4th dashboard KPI tile (draft count). Subnav line gains "Souvenirs" after "Cooptations". 4 new `memoires.memory.*` actions in `AuditLog.ACTION_CHOICES` (Python-level, no migration). **Material side benefit:** server-side EXIF strip via Pillow at upload time in `alumni.cloudinary.RealCloudinary.upload_file` — strips EXIF/XMP/IPTC from ALL future uploads (members, memoires, memoriam). `fl_strip_profile` added to both `memory_thumbnail_url` and `memory_full_url` delivery transforms for defense-in-depth on pre-phase photos. Pre-phase Cloudinary originals still retain EXIF; reaching them requires constructing the raw `cloudinary.com/<cloud>/image/upload/<public_id>` URL — `restrip_existing_memories` management command becomes Phase 2. `DATA_UPLOAD_MAX_MEMORY_SIZE` raised to 10 MB. Suite grew 707 → ~764 (+57 tests). Spec: [specs/2026-05-10-gestion-souvenirs-design.md](specs/2026-05-10-gestion-souvenirs-design.md). |
```

Also extend the test-suite trajectory line at the bottom of §Post-launch polish:

```markdown
**Test suite trajectory:** ... → 707 (handbook pipeline) → 764 (gestion souvenirs). New tests added with each fix; no regressions introduced.
```

- [ ] **Step 9.5: Commit STATUS update**

```bash
git add docs/superpowers/STATUS.md
git commit -m "$(cat <<'EOF'
docs(status): post-launch polish row for feat/gestion-souvenirs

Suite 707 → ~764 (+57 tests). Phase ships co-admin parity on the Mur
des souvenirs + server-side EXIF strip at upload time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 9.6: Merge to main**

```bash
git checkout main
git merge --no-ff feat/gestion-souvenirs -m "$(cat <<'EOF'
Merge branch 'feat/gestion-souvenirs' into main

Extends /gestion/ with full co-admin parity on the Mur des souvenirs:
list (filter + search + pagination), create with upload, edit with
photo replace + no-op detection + status emissions, publish/unpublish
toggle. 4 new routes under /gestion/souvenirs/, 4th dashboard tile,
Souvenirs subnav link.

Material side benefit: server-side EXIF strip via Pillow in
alumni.cloudinary.RealCloudinary.upload_file — eliminates GPS
leakage in stored originals for ALL future uploads (member admin
photos, memoires admin, memoriam admin, new /gestion/ flow).
fl_strip_profile added to memory_thumbnail_url + memory_full_url
delivery transforms for defense-in-depth on pre-phase photos.

Suite: 707 → ~764. No migrations (4 new AuditLog ACTION_CHOICES
entries are Python-level). No tag — internal capability rides on top
of main.

Spec: docs/superpowers/specs/2026-05-10-gestion-souvenirs-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 9.7: Run full suite once more on main**

Run: `make test`

Expected: All tests pass.

- [ ] **Step 9.8: Push to deploy**

```bash
git push origin main
```

Watch Railway for the deploy to finish (~3 min). Per CLAUDE.md, verify `/gestion/souvenirs/` is reachable in production via `bominomla` super-admin login. Co-admin verification deferred until a co-admin account exists in prod.

- [ ] **Step 9.9: Delete the merged feature branch**

```bash
git branch -d feat/gestion-souvenirs
```

---

## Notes for the executor

**Testing conventions reminders:**

- All tests use `@pytest.mark.django_db` (module-level via `pytestmark = pytest.mark.django_db` is the project convention).
- For Cloudinary, use `settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"` and call `alumni.cloudinary.reset_fake_client()` between tests that share Cloudinary call lists.
- Existing gestion fixtures: `make_user`, `make_member`, `make_application`, `coadmin_user`, `superadmin_user`, `regular_member_user` (all already in `gestion/tests/conftest.py`). Task 3 adds `make_memory`.
- French test data: use real French alumni names + locations to mirror real production data shape.

**Deviation handling:**

If during implementation a task reveals a locked-decision gap not anticipated by the spec, **stop** and flag it to the user. Don't silently improvise. The spec's §L Open questions section currently says "None remaining" — but unknown unknowns may surface during TDD.

Common things to watch for during execution:

1. **`memory_photo` templatetag signature** (used in `memory_list.html` + `memory_edit.html`). Task 4.6 calls this out — verify the tag's actual signature before assuming `{% memory_photo memory.photo_public_id size=200 %}` works. If the existing tag takes a Memory instance instead of a public_id, adapt the template.

2. **Flash-message render block in `gestion/base.html`** — Task 8.6 adds 6 new keys. If the existing block already renders flash messages for member-flow keys, extend (don't replace). If no block exists, add it as shown.

3. **Atomic transaction rollback behavior in tests** — pytest-django uses `transaction=True` to enable rollback isolation. `transaction.on_commit(...)` callbacks fire when the OUTER test transaction commits (which may not happen until test teardown). The edit-photo-replace test asserts via `fake.delete_calls` — if that assertion is flaky because on_commit doesn't fire in time, use `@pytest.mark.django_db(transaction=True)` on the specific test, OR explicitly trigger `connection.commit_on_exit_callback()` after the view returns. The simpler workaround is to use `pytest_django`'s `django_db_serialized_rollback` fixture sparingly.

4. **`Memory.objects.create(...)` with `taken_at=None`** — Memory.taken_at has `null=True, blank=True`, so passing None is fine. Test data uses `taken_at=""` (empty string) which the form converts to None via Django's DateField cleaner.
