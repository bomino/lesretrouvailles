# `/gestion/souvenirs/` — Co-admin Mur des souvenirs management (design + plan, combined)

**Status:** Approved (brainstorming complete 2026-05-10, five review passes).
**Phase:** post-Gestion-v1 polish — extends `/gestion/` console with photo curation parity to `/admin/memoires/memory/`.
**Branch:** `feat/gestion-souvenirs`.
**Tag target:** none — internal capability, rides on top of `main`. Test-suite trajectory: `707 → ~735`.

---

## A. Origin

Today, only the super-admin (Bomino, via `/admin/memoires/memory/`) can upload, edit, publish, or unpublish photos on the **Mur des souvenirs** (`/souvenirs/`). Designated co-admins (`is_staff=True, is_superuser=False`) have full coverage of member management and the cooptation queue via `/gestion/`, but the photo gallery is invisible to them. Curation work bottlenecks on the super-admin.

This phase closes that gap with full co-admin parity on photo CRUD — mirroring the shape of the Gestion-v1 `feat/gestion-cooptation` sub-phase that brought the cooptation queue to `/gestion/`.

## B. Goals

1. Co-admins can perform every photo-curation action on `/gestion/souvenirs/` that the super-admin currently does on `/admin/memoires/memory/`, except destructive operations (hard delete).
2. The new surface is mobile-first, French-language, accessible, and consistent with the existing `/gestion/` patterns (single subnav line, KPI dashboard, plain-form interaction).
3. Every state change writes an AuditLog row with human-readable metadata, retained per the P6c 12-month sweep.

## C. Non-goals (explicit)

| # | Non-goal | Why |
|---|---|---|
| 1 | Hard-delete via `/gestion/` | Consistent with `/gestion/membres/` no-destructive-ops rule. Super-admin can hard-delete via `/admin/memoires/memory/`. |
| 2 | Bulk operations (multi-select publish, multi-delete) | Curation is 1-at-a-time at our scale. |
| 3 | Photo cropping / editing UI | Cloudinary delivery transforms handle resizing + crop. Source photos stay as-is. |
| 4 | Manual reordering (drag-and-drop position field) | No `position` field on the model. Ordering is by `taken_at` (semantic) + `-created_at` (recency). |
| 5 | Tags / categories on photos | No demand surfaced. Phase 2 candidate. |
| 6 | Member-uploaded gallery + droit-à-l'image workflow | Phase 2 backlog item per `STATUS.md`. |
| 7 | Server-side EXIF strip with Pillow/piexif | Dedicated mini-phase planned. This phase ships `fl_strip_profile` delivery-only mitigation. |
| 8 | Direct browser → Cloudinary upload (signed) | Phase 2 enhancement; saves the double-hop for mobile co-admins. |
| 9 | HTMX partial updates | Consistent with cooptation list using plain GET. |
| 10 | "Preview before publish" 2-step flow | Full-parity decision: co-admin publishes directly. AuditLog handles accountability. |
| 11 | Filter context preservation across redirects | Consistent with cooptation pattern. Documented UX wart. |
| 12 | Idempotency tokens (POST-retry duplicate detection) | At 0–3 co-admin scale + low frequency, not worth the complexity. |
| 13 | Optimistic concurrency control via `updated_at` version field | Race window vanishingly small; `select_for_update` prevents DB corruption. Lost-update edge documented in §I Risks. |
| 14 | Photo dimension validation (reject tiny photos) | Cloudinary handles all dimensions; operator catches via preview. |
| 15 | Photo content moderation / NSFW detection | Trust model: co-admins are designated by super-admin. AuditLog catches authorship. |
| 16 | Search ranking / relevance / pg_trgm fallback | Simple `icontains` over caption + location is sufficient at memory volume. |
| 17 | EXIF-based `taken_at` auto-population | Phase 2 candidate, depends on server-side EXIF processing. |
| 18 | Duplicate-upload detection | Operator catches via list view. |
| 19 | Cloudinary orphan-blob cleanup script | Acceptable to accumulate at our scale. Phase 2 candidate when storage pressure shows. |
| 20 | "Memories I created" filter | All co-admins see all memories per full-parity decision. |

## D. Audience

- **Co-admins** (`is_staff=True, is_superuser=False`) — 0 to 3 designated by Bomino. Curation power equal to super-admin's, gated only by training.
- **Super-admin** (Bomino) — also uses `/gestion/souvenirs/` (mobile-friendly), retains `/admin/memoires/memory/` for advanced ops (hard delete, queryset operations).
- **End-of-line readers** — regular members never see `/gestion/souvenirs/`. The public `/souvenirs/` view is unchanged by this phase.

## E. Architecture

### URL structure (4 routes)

```
/gestion/souvenirs/                          memory_list_view
/gestion/souvenirs/nouveau/                  memory_create_view
/gestion/souvenirs/<int:pk>/modifier/        memory_edit_view
/gestion/souvenirs/<int:pk>/statut/          memory_status_view  (POST)
```

No separate detail page — the edit page renders the photo at `size=400` and serves as both viewing and editing surface. This matches `Memory`'s simple data shape (4 editable fields + photo).

### File layout

Extends existing single-file gestion convention. No per-feature split.

| Path | Action |
|---|---|
| `gestion/views.py` | Extend (~150 LOC: 4 memory view functions + `dashboard_view` KPI extension). Module constant `PAGE_SIZE_MEMORY = 12` next to existing `PAGE_SIZE = 20`. |
| `gestion/forms.py` | Extend with `GestionMemoryForm`, lifted from `memoires.forms.MemoryAdminForm` and restyled with the Tailwind `input_class` pattern that `memoriam.forms.NominationForm` uses. |
| `gestion/urls.py` | Extend with 4 routes above. |
| `gestion/templates/gestion/memory_list.html` | New. Grid of `size=200` thumbnails, status filter chips, `?q=` search, pagination. |
| `gestion/templates/gestion/memory_edit.html` | New. Shared by create + edit (renders without pk in create mode). Photo preview at `size=400` (edit only), `upload` file input, 4 form fields, save button, status-toggle form (edit only). |
| `gestion/templates/gestion/base.html` | Add `Souvenirs` subnav link (between `Cooptations` and overflow). Mirror active-state highlighting pattern. |
| `gestion/templates/gestion/dashboard.html` | Grid bumps `md:grid-cols-3` → `md:grid-cols-2 lg:grid-cols-4`; new 4th tile rendering `kpis.draft_memories` count. |
| `gestion/tests/conftest.py` | Add `make_memory(make_user)` factory fixture; default `status="published"`, `photo_public_id="seed/test-photo-{counter}"`. |
| `gestion/tests/test_memory_list.py` | New. |
| `gestion/tests/test_memory_create.py` | New. |
| `gestion/tests/test_memory_edit.py` | New. |
| `gestion/tests/test_memory_status.py` | New. |
| `gestion/tests/test_caption_xss_safe.py` | New (regression — caption never rendered as markdown/HTML). |
| `gestion/tests/test_dashboard.py` | Extend for 4th tile assertions. |
| `members/models.py::AuditLog.ACTION_CHOICES` | Add 4 entries (Python-level, no migration). |
| `alumni/cloudinary.py::memory_thumbnail_url` | Add `fl_strip_profile` to the transformation chain (delivery-side EXIF strip, no migration). |
| `alumni/settings/base.py` | Raise `DATA_UPLOAD_MAX_MEMORY_SIZE` to `10 * 1024 * 1024` (8 MB form limit + headers). **Do not** raise `FILE_UPLOAD_MAX_MEMORY_SIZE` — leave at default 2.5 MB so files >2.5 MB stream to disk rather than buffer in RAM. |

### Permissions

- `staff_required` decorator on every view (decorator already exists in `gestion/decorators.py`).
- No additional permission split for memory CRUD — full parity is the locked decision.
- Hard delete + bulk operations remain super-admin-only via `/admin/memoires/memory/`.

### Subnav

`Membres / Cooptations / Souvenirs` — actionable-backlog surfaces first. No badge on Souvenirs subnav link (dashboard tile carries the draft count instead).

### Dashboard

4th KPI tile renders `Memory.objects.filter(status="draft").count()`, links to `/gestion/souvenirs/?status=draft`. Tile renders the count even at 0 (e.g., "0 photos en brouillon") to keep the section discoverable.

## F. Data flows

### Flow A — Create

```
1. GET /gestion/souvenirs/nouveau/                       → render form (status defaults to "draft")
2. POST                                                  → form.is_valid():
                                                              upload.size ∈ (0, 8 MB]
                                                              content_type ∈ {image/jpeg, image/png, image/webp}
                                                              caption non-empty, status in {draft, published}
3. If invalid: re-render with errors (file lost; operator re-picks).
4. If valid: client.upload_file(upload, folder="memoires")
                                                          → new_public_id (or raise)
   On Cloudinary failure: form.add_error("upload", "Échec…"), re-render. No DB write.
   Defensive: if not new_public_id: raise RuntimeError (contract drift safety).
5. with transaction.atomic():
       memory = Memory.objects.create(
           photo_public_id=new_public_id,
           caption, taken_at, location, status,
           created_by=request.user,
       )
       AuditLog.objects.create(
           actor=request.user, action="memoires.memory.created",
           target_type="memoires.Memory", target_id=str(memory.pk),
           metadata={
               "caption_preview": memory.caption[:60],
               "location": memory.location,
               "taken_at": memory.taken_at.isoformat() if memory.taken_at else None,
               "public_id": memory.photo_public_id,
               "initial_status": memory.status,  # "draft" or "published"
           },
       )
       # No separate .published row even if initial_status == "published".
6. 302 /gestion/souvenirs/?flash=created
```

### Flow B — Edit

```
1. GET /gestion/souvenirs/<pk>/modifier/                 → load memory, render form prefilled
                                                            + photo preview at size=400
2. POST                                                  → form.is_valid()
3. If invalid: re-render with errors.
4. If valid AND upload provided:
       client.upload_file(upload, folder="memoires")     → new_public_id
       Defensive: if not new_public_id: raise.
       On Cloudinary failure: form.add_error, re-render. Old photo intact.
5. with transaction.atomic():
       memory = Memory.objects.select_for_update().get(pk=pk)
       old_id = memory.photo_public_id
       # snapshot watched fields for no-op detection
       pre = {f: getattr(memory, f) for f in WATCH_FIELDS}
       if upload: memory.photo_public_id = new_public_id
       for f in form.changed_data:
           if f != "upload": setattr(memory, f, form.cleaned_data[f])
       post = {f: getattr(memory, f) for f in WATCH_FIELDS}
       if pre == post and not upload:
           # no-op detected
           return redirect with ?flash=noop  # zero audit rows
       memory.save()
       changed_fields = [f for f in form.changed_data if f not in ("upload", "status")]
       photo_replaced = bool(upload)
       fields_changed = bool(changed_fields) or photo_replaced
       status_changed = pre["status"] != post["status"]
       if fields_changed:
           AuditLog.create(memoires.memory.edited, metadata={
               caption_preview, public_id, changed_fields, photo_replaced
           })
       if status_changed:
           AuditLog.create(.published or .unpublished, metadata={
               caption_preview, public_id, previous_status=pre["status"]
           })
       if upload and old_id:
           transaction.on_commit(lambda: client.delete(old_id))
6. 302 /gestion/souvenirs/?flash=updated
```

`WATCH_FIELDS = ("caption", "taken_at", "location", "status", "photo_public_id")`

**On-commit semantics:** `client.delete(old_id)` runs only if the transaction commits, and runs *after* commit. Wrapped in try/except inside the callback; on failure, log warning and continue (orphan acceptable). Documented in §I Risks.

### Flow C — Status toggle

```
1. POST /gestion/souvenirs/<pk>/statut/                  → form field target_status ∈ {draft, published}
2. Validate target_status; bad value → 302 ?flash=bad_status, no audit row.
3. with transaction.atomic():
       memory = Memory.objects.select_for_update().get(pk=pk)
       if memory.status == target_status:
           return redirect with ?flash=noop  # zero audit rows
       previous_status = memory.status
       memory.status = target_status
       memory.save(update_fields=["status", "updated_at"])
       action = "memoires.memory.published" if target_status == "published" else "memoires.memory.unpublished"
       AuditLog.create(action, metadata={
           caption_preview, public_id, previous_status
       })
4. 302 /gestion/souvenirs/?flash=published (or unpublished)
```

Mirrors `member_status_view` semantics: bad-status / noop branches.

### Flow D — List

```
GET /gestion/souvenirs/?status=<all|published|draft>&q=<search>&page=<n>
  qs = Memory.objects.all()
  if status != "all": qs = qs.filter(status=status)
  if q:
      needle = Lower(Unaccent(Value(q)))
      qs = qs.annotate(
          caption_lc=Lower(Unaccent(F("caption"))),
          location_lc=Lower(Unaccent(F("location"))),
      ).filter(
          Q(caption_lc__contains=needle) | Q(location_lc__contains=needle)
      )
  qs = qs.order_by("-created_at", F("taken_at").desc(nulls_last=True))
  paginator = Paginator(qs, PAGE_SIZE_MEMORY)  # = 12
  page = paginator.page(...)
  render memory_list.html with thumbnails (memory_thumbnail_url(public_id, size=200))
```

Default `status` filter when query param absent: `"all"`.

### Error model

| Failure | Where | User sees | Side effects |
|---|---|---|---|
| Form invalid (size, MIME, missing) | `form.is_valid()` | Form re-rendered with French errors | None |
| Cloudinary upload raises | `client.upload_file` | `form.add_error("upload", "Échec du téléversement. Vérifiez votre connexion et réessayez.")` + re-render | None |
| `client.upload_file` returns empty/falsy public_id | defensive check | 500 (Django debug page) | None (atomic block not entered) |
| DB write fails inside `with transaction.atomic():` | inside view | 500 | New Cloudinary blob orphaned |
| `client.delete(old_id)` fails post-commit (Flow B) | `transaction.on_commit` callback | None (silent) | Old Cloudinary blob orphaned, `logger.warning` emitted |
| Permission denied | `staff_required` | Redirect to `/accounts/login/` (anon) or 403 page (non-staff) | None |
| Memory not found | `get_object_or_404` | 404 page | None |
| Bad `target_status` POST | view validator | Redirect with `?flash=bad_status` | None |
| No-op status change | view validator | Redirect with `?flash=noop` | None — no audit row |
| No-op edit | view comparator | Redirect with `?flash=noop` | None — no audit row |

## G. Locked decisions

| Area | Decision |
|---|---|
| Scope | Full parity with super-admin. No destructive ops on `/gestion/`. |
| File layout | Extend `gestion/views.py`, `gestion/forms.py`, `gestion/urls.py` (single-file convention). At ~600 LOC post-merge, `gestion/views.py` is at the upper-comfortable boundary; future Gestion phases should consider a per-feature split. |
| URLs | 4 routes under `/gestion/souvenirs/`. No detail page. |
| Subnav | `Membres / Cooptations / Souvenirs`. No badge on Souvenirs link. |
| Dashboard | 4th KPI tile = draft count. Renders count at 0. Grid `md:grid-cols-2 lg:grid-cols-4`. |
| List filter | Chips `Toutes / Publiées / Brouillons` via `?status=`. Default when absent: `Toutes`. |
| List ordering | `-created_at, F("taken_at").desc(nulls_last=True)` — curation-recency first. Public `/souvenirs/` ordering unchanged. |
| Pagination | `PAGE_SIZE_MEMORY = 12` (module constant in `gestion/views.py`). |
| Search | `?q=` over `caption` + `location`, `Lower(Unaccent(...))` accent-insensitive pattern. |
| Thumbnails | List: `size=200`, `loading="lazy"`, `alt="{{ caption\|truncatechars:80 }}"`. Edit preview: `size=400`, full caption as alt. |
| Form fields | `upload, caption, taken_at, location, status`. `upload` is form-only (not on model). Status defaults via `Memory.status` model default (`"draft"`); no explicit form `initial=`. |
| Upload validation | `upload.size ∈ (0, 8 MB]`, `content_type ∈ {"image/jpeg", "image/png", "image/webp"}`. French error messages. |
| Cloudinary folder | `"memoires"` (unchanged). |
| Status toggle | POST `/<pk>/statut/` with `target_status ∈ {"draft", "published"}`. Single `<form>`, two submit buttons sharing `name="target_status"`. No-op + bad-status branches mirror `member_status_view`. |
| Transactions | `with transaction.atomic():` block scoped to DB writes only (NOT decorator). Cloudinary upload happens BEFORE the block. Edit + status views use `Memory.objects.select_for_update().get(pk=pk)` as first statement inside the block. |
| Old-photo cleanup | `transaction.on_commit(lambda: client.delete(old_id))` inside the atomic block. Failure logged + ignored. |
| No-op edit | WATCH_FIELDS snapshot pre vs post; if equal AND no upload, skip writes, redirect with `?flash=noop`. |
| Caption rendering | Plain text only, never HTML/markdown. Regression test asserts XSS-safety. |
| EXIF strip | Phase 1: `fl_strip_profile` in `memory_thumbnail_url` (delivery-side). Stored originals retain GPS. Phase 2 mini-phase planned for server-side strip. |
| HTMX | Not used. Plain GET/POST + full-page reload. |
| Accessibility | `min-h-tap` on every interactive element. Status chips wrapped in `role="group" aria-label="Filtrer par statut"`, active chip has `aria-pressed="true"`. Pagination links carry `aria-label` + `aria-current="page"` on the active page. |
| `taken_at` validation | None. No min-year / max-year check. Trust operator. |
| Settings | Raise `DATA_UPLOAD_MAX_MEMORY_SIZE` to `10 * 1024 * 1024` in `alumni/settings/base.py`. Leave `FILE_UPLOAD_MAX_MEMORY_SIZE` at default. |
| Concurrency | `select_for_update` serializes concurrent writes on the same memory. Form-load-time silent-lost-update edge documented in §I Risks. |
| Permission tests | Every view's test file: anon → login redirect; non-staff member → 403; co-admin → 200; super-admin → 200. |
| `make_memory` fixture | Defaults `status="published"`, `photo_public_id="seed/test-photo-{counter}"`. No separate `make_draft_memory` fixture — tests call `make_memory(status="draft")` explicitly. |
| Filter context preservation | Across edit/create redirects, filter+page query params lost. Consistent with cooptation pattern. Out of scope. |
| Time zone | `created_at` uses Django's TZ-aware `auto_now_add`; rendered in `TIME_ZONE = "Africa/Niamey"` per project settings. No special handling. |
| Cloudinary asset visibility | Public-by-default (anyone with the URL can fetch). Intentional — `/souvenirs/` must reach members. Public_ids are random, never embedded in HTML — enumeration not feasible. |
| `/admin/auditlog/` filter | New ACTION_CHOICES entries auto-appear in admin list filter at request time. No `members/admin.py` change. |

## H. AuditLog details

**Action additions** to `members/models.py::AuditLog.ACTION_CHOICES` (Python-level, no migration):

```python
("memoires.memory.created", "Photo Souvenirs créée"),
("memoires.memory.edited", "Photo Souvenirs modifiée"),
("memoires.memory.published", "Photo Souvenirs publiée"),
("memoires.memory.unpublished", "Photo Souvenirs dépubliée"),
```

**`target_type` / `target_id`:**

- `target_type = "memoires.Memory"`
- `target_id = str(memory.pk)`

**Metadata payload schema (per event):**

`memoires.memory.created`:
```python
{
    "caption_preview": memory.caption[:60],
    "location": memory.location,
    "taken_at": memory.taken_at.isoformat() if memory.taken_at else None,
    "public_id": memory.photo_public_id,
    "initial_status": memory.status,  # "draft" or "published"
}
```

`memoires.memory.edited`:
```python
{
    "caption_preview": memory.caption[:60],
    "public_id": memory.photo_public_id,
    "changed_fields": [f for f in form.changed_data if f not in ("upload", "status")],
    "photo_replaced": bool(new_upload),
}
```

`memoires.memory.published`:
```python
{
    "caption_preview": memory.caption[:60],
    "public_id": memory.photo_public_id,
    "previous_status": "draft",  # only legal pre-state
}
```

`memoires.memory.unpublished`:
```python
{
    "caption_preview": memory.caption[:60],
    "public_id": memory.photo_public_id,
    "previous_status": "published",  # only legal pre-state
}
```

**Atomicity guarantee.** Each `AuditLog.objects.create(...)` runs *inside* the same `with transaction.atomic():` block that performs the underlying Memory write. If audit fails, Memory write rolls back. Cloudinary side-effects (upload + delete) are explicitly outside the atomic transaction — orphan-on-rollback and orphan-on-delete-failure both documented in §I Risks.

**Emission rules:**

| User action | AuditLog rows emitted |
|---|---|
| Create with `status="draft"` | 1: `.created` (metadata `initial_status="draft"`) |
| Create with `status="published"` | 1: `.created` (metadata `initial_status="published"`) — NOT a separate `.published` row |
| Edit, fields changed, status unchanged | 1: `.edited` |
| Edit, fields changed, status flipped | 2: `.edited` + `.published`/`.unpublished` |
| Edit, only photo replaced | 1: `.edited` (with `photo_replaced=True`, `changed_fields=[]`) |
| Edit, only status flipped | 1: `.published` or `.unpublished` (no `.edited` because nothing else changed) |
| Edit, no actual change detected | 0: redirect with `?flash=noop` |
| Status toggle via `/statut/` | 1: `.published` or `.unpublished` |
| Status toggle, target == current | 0: redirect with `?flash=noop` |
| Status toggle, invalid target | 0: redirect with `?flash=bad_status` |

## I. Risks

| # | Risk | Mitigation | Residual |
|---|------|------------|----------|
| 1 | Photo-replace / metadata race — two co-admins editing same memory near-simultaneously can produce a silent lost-update | `select_for_update()` row lock serializes commits; no DB corruption | Silent lost-update of B's-unchanged-from-form-load fields possible. Likelihood near-zero at 0–3 co-admin scale. Mitigation = optimistic concurrency via `updated_at` (deferred) |
| 2 | Cloudinary upload succeeds → DB write fails inside atomic → blob orphaned | Acknowledged; consistent with `memoires/admin.py` | Acceptable; Cloudinary free-tier headroom |
| 3 | `client.delete(old_id)` fails post-commit | `transaction.on_commit` callback + try/except; `logger.warning` on failure | Orphan; operator unaware (intentional) |
| 4 | EXIF GPS in stored Cloudinary originals | `fl_strip_profile` in delivery transformation chain | Original blob retains EXIF. Reaching it requires either Cloudinary console credentials OR constructing the raw URL from a known random public_id (never embedded in rendered HTML). Effective attack surface: someone with our Cloudinary admin access. Mini-phase planned for server-side strip. |
| 5 | Dashboard tile may read 0 long-term if curation pattern is "create-and-publish" | None | Revisit after first real usage; may swap for a different KPI |
| 6 | Filter context lost on edit-redirect | None | Documented; consistent with cooptation |
| 7 | Browser POST retry → duplicate Memory created | None | Acceptable at 0–3 co-admin scale, low frequency |
| 8 | Cloudinary down during upload | `form.add_error` with French message | Operator sees error, re-tries; no DB write |
| 9 | Cloudinary monthly quota exceeded (free tier ~25 credits/month ≈ ~1k uploads + 25k transforms) | None (well within budget at our scale; ~1 credit/month projected) | Monitoring via Cloudinary console; upgrade tier if it ever becomes load-bearing |
| 10 | Orphan blob accumulation over months (from rollbacks + delete failures) | None | At our scale, maybe 10–50 orphans/year. Cloudinary console exposes "storage used"; operator can prune manually. `cleanup_orphans` management command is a Phase 2 candidate. |
| 11 | DB connection pool exhaustion from `select_for_update` holding connections | None special | At 0–3 co-admin scale, well within Railway's pool size (~20). Awareness only. |
| 12 | Browser cache shows stale thumbnail after photo replace | None | New upload → new random public_id → new URL → fresh fetch within 5–15 min (Cloudinary CDN default). No time-critical replacements expected. |

## J. Testing strategy

### Test file organization

| File | Action | Covers |
|---|---|---|
| `gestion/tests/test_memory_list.py` | New | Filter (all/published/draft), `?q=` search with accent-insensitivity, pagination at 12, ordering by `-created_at`, empty state, `loading="lazy"` attribute, permission gates (4 user types) |
| `gestion/tests/test_memory_create.py` | New | Upload validation (0 / >8MB / bad MIME), Cloudinary success path, Cloudinary failure path (form-error re-render, no DB write), defensive empty-public_id check, AuditLog `.created` row + full metadata schema, **create-with-status=published emits ONE `.created` row** (not separate `.published`), redirect with `?flash=created`, permission gates |
| `gestion/tests/test_memory_edit.py` | New | Field-only edit → `.edited` row; photo replace triggers `client.delete(old_id)` post-commit (FakeCloudinary records the call); status flip via edit form → `.edited` + `.published`/`.unpublished` only when other fields ALSO changed; status-only flip via edit form → just `.published`/`.unpublished`; no-op detection → `?flash=noop` zero audit rows; smoke-level `select_for_update` presence; permission gates |
| `gestion/tests/test_memory_status.py` | New | `target_status=published` on draft → `.published` row + redirect; `target_status=draft` on published → `.unpublished` row + redirect; `target_status==current` → `?flash=noop` zero rows; invalid `target_status` → `?flash=bad_status` zero rows; GET → 405; permission gates |
| `gestion/tests/test_caption_xss_safe.py` | New | Caption containing `<script>alert(1)</script>` renders escaped on (a) public `/souvenirs/<pk>/`, (b) `/gestion/souvenirs/` list view `alt` attribute, (c) `/gestion/souvenirs/<pk>/modifier/` form textarea. Regression to prevent future markdown-render PR. |
| `gestion/tests/test_dashboard.py` | Extend | New 4th tile renders correct draft count; link target is `/gestion/souvenirs/?status=draft`; grid class `md:grid-cols-2 lg:grid-cols-4`. |

### Fixture additions to `gestion/tests/conftest.py`

```python
@pytest.fixture
def make_memory(db, make_user):
    from memoires.models import Memory
    counter = {"i": 0}
    def _make(**kwargs):
        counter["i"] += 1
        created_by = kwargs.pop("created_by", None) or make_user(
            username=f"memory_owner_{counter['i']}",
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

Tests call `make_memory(status="draft")` directly for drafts.

### Manual smoke-test checklist (run before merge)

- [ ] `make docker-run` against staging.py settings; upload a 6 MB JPEG → publishes correctly to `/souvenirs/`.
- [ ] Replace photo on existing memory; verify old Cloudinary URL eventually 404s; new URL renders.
- [ ] Status toggle round-trip (publish → unpublish → publish); verify 2 AuditLog rows in `/admin/memoires/` admin AuditLog view.
- [ ] Mobile viewport (360 × 800) walkthrough: list view, filter chips, search, create, edit, status toggle — every tap target reachable, no horizontal scroll.
- [ ] Verify `fl_strip_profile` substring in a rendered `<img>` URL on (a) `/souvenirs/`, (b) `/souvenirs/<pk>/`, (c) `/gestion/souvenirs/`, (d) `/gestion/souvenirs/<pk>/modifier/`.
- [ ] Co-admin login flow: login → `/gestion/` dashboard → click Souvenirs tile → see drafts → publish one.

### Coverage targets

- **Permission coverage:** 4 user types × 4 routes = 16 cases (parametrized).
- **AuditLog coverage:** every row in §H emission-rules table has a matching test asserting (row count, action string, metadata keys, metadata values).
- **Error-path coverage:** every row in §F error-model table has a test.
- **Concurrency:** smoke-level only — `select_for_update` call presence, decorator/context presence. True race testing (threading + atomic) is brittle in pytest; out of scope.

### Test suite trajectory

`707 → ~735` (+28 tests). New tests added with each task; no regressions introduced.

## K. Implementation checklist

The order below is the recommended commit sequence for `gsd-plan-phase`-style task breakdown.

- [ ] **Settings change.** Verify and update `DATA_UPLOAD_MAX_MEMORY_SIZE` in `alumni/settings/base.py` to `10 * 1024 * 1024`. Leave `FILE_UPLOAD_MAX_MEMORY_SIZE` at default.
- [ ] **AuditLog choices.** Add 4 entries to `members/models.py::AuditLog.ACTION_CHOICES`. No migration. Verify `/admin/` list filter auto-updates.
- [ ] **EXIF strip surface audit (5 substeps).**
  1. Read `alumni/cloudinary.py` for all functions producing memory URLs.
  2. Read `memoires/templatetags/memory_photo.py`.
  3. Read `memoires/templates/memoires/{gallery,detail}.html` for image tags.
  4. Ensure every render path includes `fl_strip_profile` (preferably at a chokepoint in `alumni/cloudinary.py`).
  5. Add regression test asserting `"fl_strip_profile"` substring in a rendered `<img>` URL.
- [ ] **`gestion/forms.py`.** Add `GestionMemoryForm` lifted from `memoires.forms.MemoryAdminForm`. Tailwind `input_class` styling. Validation: `upload.size in (0, 8MB]`, `content_type` allow-list with French errors.
- [ ] **`gestion/urls.py`.** Add 4 routes.
- [ ] **`gestion/views.py`.** Add `PAGE_SIZE_MEMORY = 12` constant. Add `memory_list_view`, `memory_create_view`, `memory_edit_view`, `memory_status_view`. Extend `dashboard_view` KPIs with `draft_memories` count.
- [ ] **Templates.** Add `gestion/templates/gestion/memory_list.html` + `memory_edit.html`. Extend `gestion/templates/gestion/base.html` subnav + `dashboard.html` 4th tile.
- [ ] **Fixture.** Add `make_memory` to `gestion/tests/conftest.py`.
- [ ] **Tests.** Add 5 new test files + extend `test_dashboard.py`. Target ~28 new tests.
- [ ] **Flash messages.** Extend `gestion/templates/gestion/base.html` flash-message map with `created`, `updated`, `published`, `unpublished`, `noop`, `bad_status` → French copy.
- [ ] **Full suite.** Run `make test`; expect `735` passing.
- [ ] **Manual smoke tests.** Run the §J checklist before opening PR.
- [ ] **Merge.** `git checkout main && git merge --no-ff feat/gestion-souvenirs -m "..."` with the descriptive merge message.
- [ ] **Push + deploy.** `git push origin main`; watch Railway deploy; verify `/gestion/souvenirs/` reachable in prod with a real co-admin account.
- [ ] **STATUS.md update.** New row in §Post-launch polish table. Test-suite trajectory bump.

## L. Open questions

**None remaining.** All scoping decisions are locked across §A–§K and the five review passes. If something emerges during TDD implementation that doesn't match a locked decision, the loop is: stop → surface the conflict → re-decide → update the spec → continue.

---

**End of spec.**
