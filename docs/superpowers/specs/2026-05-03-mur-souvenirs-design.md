# P5a — Mur des Souvenirs (Design Spec)

**Date:** 2026-05-03
**Status:** Approved (pending implementation)
**Predecessor:** P4d (Magazine cards + single-admin governance)
**Successor:** P5b (In Memoriam — separate phase)
**Master spec:** `docs/superpowers/specs/2026-05-01-alumni-platform-design.md` §6.4 + US-08

---

## Goal

Build the member-only photo gallery surface for the Phase 1 launch: ~10-20 admin-curated seed photos. Admins upload via Django admin; members view via `/souvenirs/` (gallery) and `/souvenirs/<id>/` (detail). Add a "Souvenirs" link in the authenticated member nav (`templates/base.html`) so members can reach the gallery. The public landing's existing 3-up feature cards (Annuaire / In Memoriam / Cooptation) are not changed.

P5b (In Memoriam) is a separate phase — different model, governance (Annexe D family-consent procedure), and ethical weight. Not included here.

## Non-goals (explicit YAGNI)

- **Member-side photo upload** — Phase 2 (US-10), with its own droit-à-l'image workflow.
- **People-tagging M2M** — Phase 2 (US-10 + US-14 tag removal).
- **Reactions / comments / "souvenirs écrits"** — Phase 2 (US-11).
- **Pagination** — defer until count ≥50; 10-20 items render trivially.
- **Bulk upload** — 10-20 photos is fine one-by-one in Django admin.
- **Archive status** — two states only (draft / published) for v1. If a depicted person later requests removal, admin uses `status=draft` + a caption note.
- **In Memoriam** — separate phase (P5b).
- **Photo download / contact-sheet export** — out of scope.
- **Admin moderation queue UI** — admins are the only authors; no peer-review surface needed.

---

## A. Data model

New Django app: **`memoires`**. Matches the project's existing French app naming (`cooptation`, `members`).

```python
# memoires/models.py
from django.conf import settings
from django.db import models


class Memory(models.Model):
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
        ordering = ["-taken_at", "-created_at"]  # newest era first; NULL taken_at falls back to created_at
        indexes = [
            models.Index(fields=["status", "-taken_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.caption[:40]} ({self.taken_at or '—'})"
```

**Notes on the field choices:**

- `photo_public_id` is a `CharField` storing the Cloudinary public_id (matches the existing `Member.photo_public_id` pattern at `members/models.py:75`). The admin form will provide a `FileField` upload widget (not on the model — see Section D); the upload helper writes the resulting public_id into this field on save.
- `caption` is required (TextField, no `blank=True`). Every memory needs a description; an unsourced photo isn't useful.
- `taken_at` and `location` are both optional. Many seed photos will have approximate or unknown dates; making them required would block curation.
- `status` two-state only. Draft = admin-only, published = member-visible. No `archived` state v1 (deferred).
- `created_by` is `SET_NULL` so admin user deletion doesn't cascade-delete photos. The gallery should outlive any single curator.
- `Meta.ordering` puts newest-era photos first. With `taken_at` nullable, Postgres NULL-handling defaults to NULLS LAST on DESC ordering — i.e., NULL `taken_at` fall to the bottom, then sub-sort by `-created_at`. Acceptable: untimed photos are usually the most-recently-added admin batches anyway.

## B. URLs and views

| URL | View | Auth | Purpose |
|---|---|---|---|
| `/souvenirs/` | `memoires.views.gallery_view` | `@login_required` | Grid of published memories |
| `/souvenirs/<int:pk>/` | `memoires.views.detail_view` | `@login_required` | Full photo + caption + date + location |

Both views are member-only. Neither is in `LOGIN_REQUIRED_WHITELIST`. Both inherit `noindex` from `base.html` (no override of `{% block robots %}`). Cloudinary URLs themselves are public on the CDN — that's acceptable since they're unguessable opaque IDs and the master spec accepts this risk for member-uploaded media generally.

**Gallery view** query:

```python
Memory.objects.filter(status="published").order_by("-taken_at", "-created_at")
```

No pagination in v1 — 10-20 items is trivially small. If the gallery later crosses ~50 entries, add Django's standard `Paginator`.

**Detail view** query:

```python
get_object_or_404(Memory, pk=pk, status="published")
```

Drafts return 404 even to logged-in members. Drafts are admin-curation territory only — visible only via `/admin/memoires/memory/`.

## C. Templates

### `templates/memoires/gallery.html`

Extends `base.html`. Structure:

- **Section heading**: "Mur des Souvenirs" (h1, font-display) + subtitle: "Photos d'époque curées par les administrateurs."
- **Grid**: `grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4`. Responsive 1/2/3/4 columns by breakpoint.
- **Tile**: each is a clickable `<a>` to `/souvenirs/<pk>/`. Inside:
  - Square thumbnail via Cloudinary `c_fill,g_auto,w_400,h_400` (~30KB JPEG).
  - Caption truncated to ~80 chars beneath the image.
  - `taken_at` as a small uppercase tracked label (when present).
- **Empty state** (when no published memories exist): centered card with copy "Le mur sera enrichi au lancement. Revenez bientôt." + a small Mur des souvenirs icon.

### `templates/memoires/detail.html`

Extends `base.html`. Structure:

- **Back link**: `← Retour au mur` → `/souvenirs/`. Top of page, small text-secondary.
- **Photo**: full-width image, Cloudinary `c_limit,w_1200,q_auto:eco` (≤~200KB on typical photos). Centered, with a subtle border + shadow to anchor it.
- **Caption**: full text below the photo, in `text-lg` paragraph form.
- **Metadata line**: a small italic line below the caption with `taken_at` (formatted via Django's `date:"F Y"` filter, e.g., "Décembre 1983") and `location`, separated by " · ". Hidden if both are empty.

No "Posté par X" line in v1 — Phase 1 is a collective archive, not individual contributions.

## D. Admin

The admin needs to (a) accept a file upload (`<input type="file">`), (b) push it to Cloudinary server-side via the existing `alumni.cloudinary` abstraction, (c) write the resulting public_id into `Memory.photo_public_id`. The `Memory` model itself never holds raw bytes; the FileField lives only on the admin's `ModelForm`.

### `memoires/forms.py` — admin form

```python
# memoires/forms.py
from django import forms

from .models import Memory


class MemoryAdminForm(forms.ModelForm):
    """Admin form for Memory. Adds a file upload field that exists only
    on the form (not the model). Save flow: upload via alumni.cloudinary
    server-side, write the resulting public_id into Memory.photo_public_id."""

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
            raise forms.ValidationError("Une photo est obligatoire pour créer une nouvelle entrée.")
        return cleaned
```

### `memoires/admin.py:MemoryAdmin`

```python
from django.contrib import admin
from django.utils.html import format_html

from alumni.cloudinary import get_client, memory_thumbnail_url
from .forms import MemoryAdminForm
from .models import Memory


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    """Admin curation surface for the Mur des souvenirs.
    Auto-stamps created_by on first save and uploads the file to Cloudinary
    server-side via alumni.cloudinary.get_client().upload_file()."""

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
        ("Audit (lecture seule)", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="Aperçu")
    def thumbnail(self, obj):
        if not obj.photo_public_id:
            return ""
        url = memory_thumbnail_url(obj.photo_public_id, size=80)
        return format_html('<img src="{}" width="80" height="80" alt="" />', url)

    @admin.display(description="Légende")
    def caption_preview(self, obj):
        return obj.caption[:60] + ("…" if len(obj.caption) > 60 else "")

    def save_model(self, request, obj, form, change):
        # If the admin uploaded a file, push it to Cloudinary and stash the
        # resulting public_id. If they didn't (edit without re-upload), keep
        # the existing photo_public_id.
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

**Why `save_model` (not `save_related`):** `Memory` has no M2M fields, so the P4d `save_model` + `save_related` split (which works around `form.save_m2m()` clobbering M2M data) is unnecessary. Plain `save_model` is correct here.

**Why a custom `upload` field on the form (not on the model):** the model stores the canonical address (Cloudinary public_id), not raw bytes. The form holds the temporary upload. `save_model` mediates between them.

### `alumni/cloudinary.py` — extension

Add the following to `alumni/cloudinary.py`:

1. `upload_file(file_obj, folder)` method on the `CloudinaryClient` Protocol, `RealCloudinary`, and `FakeCloudinary` classes.
2. `memory_thumbnail_url(public_id, size=400)` helper, mirroring the existing `member_thumbnail_url` but with `g_auto` (no face crop bias).
3. `memory_full_url(public_id, max_width=1200)` helper for the detail view (limit-fit, no crop).

```python
class CloudinaryClient(Protocol):
    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]: ...
    def upload_file(self, file_obj: Any, *, folder: str) -> str: ...
    def delete(self, public_id: str) -> None: ...


class RealCloudinary:
    # ... existing __init__, sign_upload, delete ...

    def upload_file(self, file_obj: Any, *, folder: str) -> str:
        """Server-side upload via Cloudinary's REST API. Returns the public_id."""
        result = self._cloudinary.uploader.upload(
            file_obj,
            folder=folder,
            resource_type="image",
            use_filename=False,
        )
        return result["public_id"]


class FakeCloudinary:
    # ... existing fields, sign_upload, delete ...

    def upload_file(self, file_obj: Any, *, folder: str) -> str:
        """Test stub: records the call and returns a deterministic fake public_id."""
        name = getattr(file_obj, "name", "upload")
        digest = hashlib.sha1(f"{folder}:{name}".encode()).hexdigest()[:12]
        public_id = f"{folder}/fake-{digest}"
        self.upload_calls = getattr(self, "upload_calls", [])
        self.upload_calls.append({"folder": folder, "name": name, "public_id": public_id})
        return public_id


def memory_thumbnail_url(public_id: str, size: int = 400) -> str:
    """Square thumbnail with auto crop. Used in the gallery grid."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_fill,g_auto,w_{size},h_{size}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"


def memory_full_url(public_id: str, max_width: int = 1200) -> str:
    """Limit-fit version used in the detail view. No crop; keeps aspect ratio."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_limit,w_{max_width}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"
```

The `FakeCloudinary` change is forward-compatible — existing tests that didn't reference `upload_file` continue to work; tests that need it can call it and inspect `upload_calls`.

### Templates

Templates use `memory_thumbnail_url` and `memory_full_url` via a small custom template tag in `memoires/templatetags/memory_photo.py`:

```python
# memoires/templatetags/memory_photo.py
from django import template

from alumni.cloudinary import memory_full_url, memory_thumbnail_url

register = template.Library()


@register.simple_tag
def memory_thumb(public_id, size=400):
    return memory_thumbnail_url(public_id, size=size)


@register.simple_tag
def memory_full(public_id, max_width=1200):
    return memory_full_url(public_id, max_width=max_width)
```

Then in `gallery.html` and `detail.html`:

```html
{% load memory_photo %}
<img src="{% memory_thumb memory.photo_public_id 400 %}" alt="{{ memory.caption }}" loading="lazy">
```

No bulk upload in v1.

## E. Member nav integration

The public landing's three feature cards (Annuaire, In Memoriam, Cooptation) are NOT touched. Mur des souvenirs is a member-only surface and the master spec scopes the public landing to recruitment (Fantômes), not internal navigation.

Surface the gallery via the **authenticated member nav** in `templates/base.html`. Both the desktop nav block and the mobile nav block currently show: Annuaire · Cooptations à valider · Mon profil. Insert "Souvenirs" between "Annuaire" and "Cooptations à valider":

```html
<a href="/souvenirs/"
   class="rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">
    {% trans "Souvenirs" %}
</a>
```

Same shape on both desktop (`<header>` block) and mobile (`md:hidden` block). Anonymous visitors see no auth nav at all, so the link is automatically scoped to members.

The `<title>` block on `gallery.html` should read "Mur des Souvenirs" (full title) even though the nav label is just "Souvenirs" (compact for header constraints).

## F. Tests (~12)

**`memoires/tests/test_models_memory.py`** (3):
1. `test_memory_caption_required` — saving without caption raises ValidationError on full_clean
2. `test_memory_status_defaults_to_draft` — newly created Memory has status="draft"
3. `test_memory_default_ordering_newest_taken_at_first` — querying returns memories ordered by `-taken_at`, NULLs after dated entries

**`memoires/tests/test_views_gallery.py`** (3):
4. `test_gallery_anonymous_redirects_to_login` — `/souvenirs/` returns 302 to allauth login
5. `test_gallery_member_sees_published_memories` — authenticated Member sees a published memory
6. `test_gallery_hides_drafts_from_members` — draft memories not in body even for authed member

**`memoires/tests/test_views_detail.py`** (4):
7. `test_detail_anonymous_redirects_to_login` — `/souvenirs/<pk>/` returns 302 anonymous
8. `test_detail_member_sees_published` — 200 + caption + photo URL in body
9. `test_detail_returns_404_on_draft` — even authenticated member gets 404 on draft pk
10. `test_detail_returns_404_on_unknown_pk` — pk that doesn't exist → 404

**`memoires/tests/test_admin_memory.py`** (1):
11. `test_admin_save_model_stamps_created_by` — POST to `/admin/memoires/memory/add/` records request.user as created_by

**`templates/base.html` integration** — extend `core/tests/test_base_template.py` (existing file for nav-shape assertions):
12. `test_nav_includes_souvenirs_link_for_authenticated_member` — `/souvenirs/` appears in the auth nav. Anonymous visitors see no auth nav so no negative case needed.

Total: **12 tests**.

## G. Cloudinary integration notes

- **Storage**: photos land in Cloudinary's `memoires/` folder (passed to `client.upload_file(file, folder="memoires")` from `MemoryAdmin.save_model`). Namespaced separately from member profile photos (`members/`) so future backups, transforms, or retention policies can target one without touching the other.
- **Upload mechanism**: server-side via the new `CloudinaryClient.upload_file(file_obj, folder)` method on both `RealCloudinary` and `FakeCloudinary`. Different from P2's frontend signed-upload flow because admin-side server uploads are simpler (Django admin already accepts `<input type="file">`) and there's no benefit to bypassing the Django server for trusted admin paths.
- **Replacement on edit**: when an admin uploads a new file for an existing memory, `save_model` deletes the old public_id via `client.delete(old)` before stamping the new one. Mirrors `members/views.py:profile_edit_view` lines 93-101.
- **Backups**: Backblaze B2 backup is a master-spec mandate (§7.1) but a Phase 6 ops concern. P5a doesn't add the backup pipeline — it just stores via Cloudinary. The B2 backup will sweep all Cloudinary folders when it ships.
- **Test environment**: tests use `FakeCloudinary` (P2 fixture) — no real Cloudinary calls during pytest runs. Existing `CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"` setting handles this. `FakeCloudinary.upload_file()` returns a deterministic synthetic public_id based on the folder + filename hash.

## H. Migration + dependencies

- **New app `memoires`**. Add `"memoires"` to `INSTALLED_APPS` in `alumni/settings/base.py`.
- **New migration**: `memoires/migrations/0001_initial.py` creating the `Memory` table with the indexes shown above. Auto-generated.
- **No new pip dependencies** — `cloudinary` is already installed via P2.
- **No data migration** — the table starts empty. Admins seed manually post-deploy.
- **App-level `urls.py`** in `memoires/urls.py`, mounted in `alumni/urls.py` at `/`.

## I. File touch list

**Create:**
- `memoires/__init__.py`
- `memoires/apps.py`
- `memoires/models.py`
- `memoires/forms.py` — `MemoryAdminForm` with the temporary `upload` FileField
- `memoires/admin.py`
- `memoires/views.py`
- `memoires/urls.py`
- `memoires/templatetags/__init__.py`
- `memoires/templatetags/memory_photo.py` — `{% memory_thumb %}` + `{% memory_full %}` tags
- `memoires/migrations/__init__.py`
- `memoires/migrations/0001_initial.py` (auto-generated)
- `memoires/templates/memoires/gallery.html`
- `memoires/templates/memoires/detail.html`
- `memoires/tests/__init__.py`
- `memoires/tests/conftest.py` — `make_admin_user` + `make_authed_member_client` fixtures (mirroring `cooptation/tests/conftest.py` pattern)
- `memoires/tests/test_models_memory.py`
- `memoires/tests/test_views_gallery.py`
- `memoires/tests/test_views_detail.py`
- `memoires/tests/test_admin_memory.py`

**Modify:**
- `alumni/cloudinary.py` — add `upload_file()` to `CloudinaryClient` Protocol + `RealCloudinary` + `FakeCloudinary`; add `memory_thumbnail_url()` and `memory_full_url()` helpers
- `alumni/settings/base.py` — add `"memoires"` to `INSTALLED_APPS`
- `alumni/urls.py` — include `memoires.urls`
- `templates/base.html` — add "Souvenirs" link in desktop + mobile auth nav
- `core/tests/test_base_template.py` — add `test_nav_includes_souvenirs_link_for_authenticated_member`
- `docs/superpowers/STATUS.md` — add P5a row + section

## J. Phase plan summary

| # | Task | Files | Tests |
|---|------|-------|-------|
| 1 | Cloudinary client extension: `upload_file()` + URL helpers | `alumni/cloudinary.py` | 2 (upload_file behavior on both clients, helpers shape URLs correctly) |
| 2 | Scaffold `memoires` app + Memory model + migration | new app | 3 model tests |
| 3 | Gallery view + URL + template | `memoires/views.py`, `urls.py`, `gallery.html`, `templatetags/memory_photo.py` | 3 view tests |
| 4 | Detail view + template | `memoires/views.py`, `detail.html` | 4 view tests |
| 5 | Admin (form + save_model auto-stamp + Cloudinary upload + replacement-on-edit) | `memoires/forms.py`, `memoires/admin.py` | 2 admin tests |
| 6 | Nav link in base.html (desktop + mobile) | `templates/base.html`, `core/tests/test_base_template.py` | 1 nav test |
| 7 | STATUS.md update | `docs/superpowers/STATUS.md` | — |

Estimated: ~half a day. **~15 new tests**, no migrations beyond the new app's initial.

---

## K. Risk / migration notes

- **Cloudinary dependency**: the `cloudinary` package was added in P2 for member profile photos. P5a reuses the same setup (FakeCloudinary in tests). No new env vars, no new credentials.
- **No DB schema regressions** — purely additive migration (new table, new indexes).
- **Operational impact at deploy**: empty gallery shows the empty-state copy until admins seed photos. No content gating beyond that.
