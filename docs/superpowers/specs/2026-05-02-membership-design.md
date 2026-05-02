# P2 — Membership: Design Spec

**Date:** 2026-05-02
**Phase:** P2 of P1–P7
**Depends on:** P1 (Foundation, shipped at `v0.1.0-foundation`)
**Feeds into:** P3 (Cooptation), P4 (Public surface), P5 (Mémoire), P6 (Ops & RGPD)
**PRD reference:** `docs/archives/PRD_Alumni_CEG1_Birni_v1_2.md` §6.2, §6.3, §7.2, §7.3, §8.1, §8.3, §9.4
**Project spec:** `docs/superpowers/specs/2026-05-01-alumni-platform-design.md`

---

## 1. Overview

P2 builds the **member system** — the authenticated surface where validated alumni view and update their profile, and browse a directory of fellow members with search and filters. It does not yet handle how members come to exist (cooptation is P3) or how non-members find the site (public surface is P4).

At the end of P2, with seed data loaded:
- A logged-in member sees `/annuaire/` with paginated, searchable, filterable cards.
- They can open `/membres/<slug>/` to see another member's profile (subject to that member's privacy toggles).
- They can edit their own profile at `/profil/`, including a Cloudinary-hosted photo.
- First-time logins are gated by a charter-acceptance step that writes a `ConsentRecord`.
- Every authenticated route enforces login + current-charter consent via project-level middleware.
- All UI is in French and meets the a11y baseline established in P1.

---

## 2. Scope

### In scope

- `Member` model with profile fields, status, soft-delete.
- `NotificationPreference` model (1:1 with Member, signal-created).
- `ConsentRecord` model (append-only audit of charter acceptance).
- Profile view (`/membres/<slug>/`), profile self-edit (`/profil/`), directory (`/annuaire/`), charter (`/charte/`).
- Cloudinary signed-direct-upload integration for profile photos, with lazy render-time transforms.
- Project-level `LoginRequiredMiddleware` and `ConsentRequiredMiddleware`.
- Versioned charter content stored in repo as Markdown.
- "Économie de données" (data-saver) toggle.
- Initials-based avatar placeholder (deterministic color, CSS-only).
- `manage.py create_member` management command + JSON fixtures for tests and dev seeding.
- Postgres `unaccent` extension migration + accent-insensitive directory search.
- Comprehensive TDD coverage including i18n, a11y, rate limit, pagination edges.

### Out of scope (deferred)

- Self-signup, cooptation flow, knowledge questionnaire → **P3**.
- Admin moderation UI for member CRUD → **P3**.
- Public landing, `PublicSearchEntry`, public removal flow, `noindex` differentiation → **P4**.
- `Memory`, `PhotoTag`, `InMemoriamEntry` → **P5**.
- B2 backup of Cloudinary, `purge_user_from_backups.py`, `AuditLog`, RGPD purge cron, Cloudinary orphan reconciliation cron → **P6**.
- Map / Leaflet view → PRD Phase 2 (post-launch).

---

## 3. Architecture

A single new Django app, `members/`, owns all P2 domain models and views. Cloudinary helpers live at the project level so future apps (P5 `Memory`) can reuse them without circular imports.

```
alumni/
  cloudinary.py            # signed-upload helpers, lazy URL builder, FakeCloudinary for tests
  middleware.py            # LoginRequiredMiddleware, ConsentRequiredMiddleware
members/
  __init__.py
  apps.py
  admin.py                 # Django admin registrations (Member, NotificationPreference, ConsentRecord)
  models.py                # Member, NotificationPreference, ConsentRecord
  signals.py               # post_save: create NotificationPreference for new Member
  forms.py                 # ProfileEditForm (member-editable subset only)
  views.py                 # DirectoryView, ProfileDetailView, ProfileEditView, CharterView, cloudinary_sign
  urls.py
  charters/
    __init__.py            # CHARTER_CURRENT_VERSION + registry { "1.0": "v1_0.md" }
    v1_0.md                # full charter text, French, Markdown
  management/
    commands/
      create_member.py
  fixtures/
    seed_members.json
  context.py                # context processor exposing member_prefs to templates
  templates/members/
    directory.html
    directory_list_partial.html   # HTMX swap target
    profile_detail.html
    profile_edit.html
    charter.html
    _avatar.html            # initials/photo template tag output
  templatetags/
    member_avatar.py
  tests/
    __init__.py
    conftest.py             # member_factory, member_client, fake_cloudinary fixtures
    test_models.py
    test_signals.py
    test_create_member_command.py
    test_views_directory.py
    test_views_profile.py
    test_views_charter.py
    test_middleware.py
    test_cloudinary.py
    test_avatar.py
    test_i18n.py
    test_a11y.py
```

The existing `core/` app remains the home of cross-cutting concerns: `health` view, base template, landing placeholder, Allauth adapter. P2 adds nothing to `core/`.

---

## 4. Data Model

### 4.1 `Member`

```python
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
    )  # constrained to {1980..1985} via clean() and CHECK
    classes = ArrayField(
        models.CharField(max_length=4, choices=GRADE_CHOICES),
        size=4,
    )  # constrained to {6e, 5e, 4e, 3e}

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
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=["active", "suspended", "deleted"]),
                name="member_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["country"]),
        ]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        super().clean()
        if any(y not in range(1980, 1986) for y in self.years_attended):
            raise ValidationError({"years_attended": "Années hors plage 1980-1985."})
        if any(c not in dict(GRADE_CHOICES) for c in self.classes):
            raise ValidationError({"classes": "Classe inconnue."})

    def save(self, *args, **kwargs):
        # Normalize free-text fields so filters work consistently.
        self.city = self.city.strip().title() if self.city else ""
        self.country = self.country.strip().title() if self.country else ""
        super().save(*args, **kwargs)
```

**Critical field decisions:**

| Field | Rationale |
|-------|-----------|
| `user.on_delete=CASCADE` | Allauth/Django can delete the User; Member follows. Hard-delete (RGPD §9.4) just calls `user.delete()`. Soft-delete uses `status='deleted'`. |
| `first_name` + `last_name` separate | P4's `PublicSearchEntry` already needs `first_name` + `last_name_initial`. Storing split now avoids a P4 refactor. `full_name` is a `@property`. |
| `slug = UUIDField` | URL identifier independent of name (privacy + rename-safe). 36 chars in URLs is acceptable; not switching to Hashids in P2. |
| `years_attended = ArrayField(int)` | Cohort is fixed 1980-1985. Validated in `clean()` and at the DB via `CHECK`. |
| `classes = ArrayField(char)` | Choices not enforced by Django on array elements; `clean()` + DB `CHECK` provide belt-and-suspenders. |
| `show_email/whatsapp/city` as 3 BooleanFields | Type-safe, queryable. Migrations are trivial if a 4th preference is ever added. JSONField rejected. |
| `status` enum | `{active, suspended, deleted}`. No `pending` — P3's cooptation creates members at `active`. |
| `updated_at` | Required for "recently updated" indicators and audit hygiene. |
| Free-text `city`/`country` normalized to Title Case on save | Otherwise filters miss "paris" vs "Paris" vs "PARIS". |

### 4.2 `NotificationPreference`

```python
class NotificationPreference(models.Model):
    member = models.OneToOneField(
        Member,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    digest_weekly = models.BooleanField(default=False)        # opt-in (GDPR-safe for diaspora EU)
    in_memoriam_alerts = models.BooleanField(default=True)    # transactional
    event_alerts = models.BooleanField(default=False)          # opt-in (marketing-ish)
    tag_alerts = models.BooleanField(default=True)             # transactional, member-action-driven
    data_saver = models.BooleanField(default=False)
```

Default values were chosen to reduce GDPR risk for EU diaspora members (Persona 2 in PRD). Non-essential digest and event alerts default off; In Memoriam and tag alerts default on because they are reactions to events directly involving the member.

Auto-created via a `post_save` signal on `Member`.

### 4.3 `ConsentRecord`

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
```

Append-only. No update/delete in normal flow. RGPD purge in P6 wipes records via cascade when the user is deleted.

### 4.4 Choices and constants

```python
# members/models.py
GRADE_CHOICES = [
    ("6e", "6e"),
    ("5e", "5e"),
    ("4e", "4e"),
    ("3e", "3e"),
]

STATUS_CHOICES = [
    ("active", "Actif"),
    ("suspended", "Suspendu"),
    ("deleted", "Supprimé"),
]

VALID_YEARS = range(1980, 1986)  # 1980, 1981, 1982, 1983, 1984, 1985
```

### 4.5 Postgres extensions and indexes

A single migration enables `unaccent` and adds a functional index for accent-insensitive name search:

```python
# 0002_unaccent.py
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

Search queries use `Unaccent(Lower(F('first_name'))).contains(Lower(Unaccent(query)))` so "idrissa" matches "Idrïssa".

A separate `CHECK` constraint migration validates `years_attended` and `classes` array elements at the DB level (Django can't express these natively).

---

## 5. Routes

| Path | View | Methods | Auth | Notes |
|------|------|---------|------|-------|
| `/annuaire/` | `DirectoryView` | GET | login + consent | HTMX list partial supported via `Hx-Request` header |
| `/membres/<uuid:slug>/` | `ProfileDetailView` | GET | login + consent | 404 if member `status='deleted'`; suspended visible only to admins |
| `/profil/` | `ProfileEditView` | GET, POST | login + consent | Self-edit only — operates on `request.user.member` |
| `/api/cloudinary/sign/` | `cloudinary_sign` | POST | login + consent + rate limit | Returns JSON signature; rate-limited 10/min/user |
| `/charte/` | `CharterView` | GET, POST | login (no consent gate — this IS the gate) | POST records consent and redirects to `?next` |

URLs are mounted at the project level with a `members/` namespace so `{% url 'members:directory' %}` works.

---

## 6. Directory (annuaire)

### 6.1 Search and filters

A single GET form on `/annuaire/`:

```
?q=<text>&year=<int>&city=<text>&profession=<text>&page=<int>
```

| Param | Behavior |
|-------|----------|
| `q` | Accent-insensitive case-insensitive substring match against `first_name`, `last_name`, `nickname`. Combined with `OR`. Truncated to 80 chars (defensive; not a hard error). |
| `year` | One year from {1980..1985}. Filters `years_attended__contains=[year]`. Invalid values are silently dropped. |
| `city` | Exact match (`__iexact`) on the normalized title-case value; populated by a `<select>` of distinct cities. |
| `profession` | `__icontains` (free-text); typed by user. |
| `page` | Page number; clamped to `1..max_page`; out-of-range silently clamps. |

Filters are AND'd. Members with `status != 'active'` are excluded.

### 6.2 Pagination

20 per page, page-number pagination, no infinite scroll (PRD §8.1). Pagination links use plain `<a>` with `?page=N` to remain HTMX-compatible.

### 6.3 HTMX behavior

- The form uses `hx-get="/annuaire/"`, `hx-target="#directory-list"`, `hx-push-url="true"`.
- View checks `request.headers.get("Hx-Request")` and renders `directory_list_partial.html` instead of the full template. Browsers without JS still get a full-page reload.
- `hx-trigger="input changed delay:300ms"` on `q` for live search.

### 6.4 Card rendering

Each card shows: avatar (photo or initials per data-saver/missing-photo logic), `full_name`, `city` (only if `show_city`), `profession`, and a comma-joined sorted `years_attended`.

Email and WhatsApp are not rendered on directory cards regardless of preferences — those appear only on the detail view, gated by the member's own toggles.

---

## 7. Profile

### 7.1 View (`/membres/<slug>/`)

Renders all fields except `status`, `created_at`, `updated_at`. Email and WhatsApp are shown subject to the *target* member's `show_email` and `show_whatsapp` toggles. City is shown subject to `show_city`.

A "Modifier mon profil" CTA appears only when `slug == request.user.member.slug`.

`status='deleted'` returns 404. `status='suspended'` returns 404 to non-admins, 200 to admins (Phase 1 admin = `is_staff`; full role system is P3+).

### 7.2 Edit (`/profil/`)

`ProfileEditForm` (member-facing):

| Editable | Locked |
|----------|--------|
| `nickname`, `city`, `country`, `profession` | `first_name`, `last_name` (admin-only) |
| `show_email`, `show_whatsapp`, `show_city` | `years_attended`, `classes` (immutable post-cooptation) |
| `NotificationPreference.*` (all 5 toggles via inline form) | `status` (admin-only) |
| Profile photo (separate flow, §8) | `slug`, `user`, `photo_public_id` (managed by photo flow) |

Form uses Django's standard `ModelForm` + a manual nested form for `NotificationPreference`. Submission redirects to `/profil/` with a success flash message. Server-side validation enforces locked fields; client side hides them.

---

## 8. Cloudinary Integration

### 8.1 Strategy: signed direct upload

Browser uploads directly to Cloudinary; Django only signs the request. Django is never in the upload bandwidth path.

```
[Browser]                [Django]                 [Cloudinary]
   |  POST /api/cloudinary/sign/   |
   |---------------------------------->                       |
   |  { signature, timestamp, ... }                            |
   |<-------------------------------|                          |
   |  POST upload (multipart)                                  |
   |--------------------------------------------------------->|
   |                          { public_id, secure_url }       |
   |<---------------------------------------------------------|
   |  POST /profil/ { photo_public_id }                        |
   |---------------------------------->                       |
   |       (validate folder, persist, delete previous)         |
```

### 8.2 Sign endpoint

```
POST /api/cloudinary/sign/
Body: { folder?: optional, original_public_id?: optional }
```

Server pins `folder = f"members/{member.slug}/"` regardless of client input (defense against folder-traversal). Returns:

```json
{
  "api_key": "...",
  "timestamp": 1746201600,
  "signature": "...",
  "folder": "members/<slug>/",
  "max_file_size": 5242880,
  "allowed_formats": ["jpg", "jpeg", "png", "webp"]
}
```

Rate limited to 10/min/user via `django-ratelimit`. New dependency added to `pyproject.toml`.

### 8.3 Render-time transforms (lazy)

Use lazy `transformation` parameters when building image URLs in templates — never `eager`. Eager runs at upload time, costs more, and slows the upload UX.

```python
# alumni/cloudinary.py
def member_thumbnail_url(public_id: str, size: int = 240) -> str:
    return cloudinary.utils.cloudinary_url(
        public_id,
        secure=True,
        transformation=[
            {"fetch_format": "auto", "quality": "auto:eco"},
            {"width": size, "height": size, "crop": "fill", "gravity": "face"},
        ],
    )[0]
```

### 8.4 Test adapter

`alumni/cloudinary.py` exposes a `CloudinaryClient` class. In tests, `settings.CLOUDINARY_CLIENT = FakeCloudinary()` records sign/delete calls and never hits the network. Production wires the real client via `CLOUDINARY_URL`.

### 8.5 Known risk: orphans

If Cloudinary upload succeeds but the `/profil/` POST fails or the user navigates away, an unreferenced photo remains in Cloudinary. Acceptable for MVP. P6 adds a reconciliation cron that lists `members/*/` folders, diffs against `Member.photo_public_id` values, and deletes orphans older than 24 hours.

---

## 9. Auth & Consent Gating

### 9.1 `LoginRequiredMiddleware`

Project-level middleware in `alumni/middleware.py`. Redirects anonymous users to `/accounts/login/?next=<path>` for any URL not in the whitelist:

```python
LOGIN_REQUIRED_WHITELIST = [
    "/",
    "/health",
    "/accounts/",        # prefix match — login/logout/password reset
    "/static/",
    "/media/",
    "/__debug__/",       # dev only, ignored in prod
]
```

Whitelist matching uses `path.startswith(prefix)` for entries ending in `/`, exact match otherwise.

### 9.2 `ConsentRequiredMiddleware`

Runs after `LoginRequired`. For authenticated requests, checks whether the user's `Member` has a `ConsentRecord` for `CHARTER_CURRENT_VERSION`. If not, redirects to `/charte/?next=<path>`.

Skipped for: `/charte/`, `/accounts/logout/`, `/api/cloudinary/sign/` is **not** skipped (consent must precede photo upload).

### 9.3 Charter content versioning

`members/charters/__init__.py`:

```python
CHARTER_CURRENT_VERSION = "1.0"
CHARTER_VERSIONS = {
    "1.0": "v1_0.md",
}
```

When the charter changes, add a new file (`v1_1.md`), bump `CHARTER_CURRENT_VERSION`, keep the old file in repo. Existing `ConsentRecord` rows referencing `1.0` remain auditable; `ConsentRequiredMiddleware` re-prompts everyone for `1.1`.

`CharterView` renders the current version's Markdown via Django's `markdown` filter (vendored or via `django-markdownify` — choose during planning).

### 9.4 Session caching

To avoid a DB query per request, the middleware caches the consent state in `request.session`:

```python
session["consent_ok_for"] = "1.0"   # set on POST /charte/
```

Middleware short-circuits if `session["consent_ok_for"] == CHARTER_CURRENT_VERSION`. Otherwise it queries `ConsentRecord` and updates the session.

---

## 10. Data-saver mode

When `request.user.member.preferences.data_saver` is `True`:

- Member avatars render as initials (§11) instead of `<img>` tags.
- Cloudinary URLs are not generated.
- `prefers-reduced-data` CSS hint is added to the response (forward-compatible with Save-Data UAs).

A context processor `members.context.member_preferences` exposes `member_prefs` to every template so `{% if member_prefs.data_saver %}` works without per-view fetches.

---

## 11. Initials placeholder

Used when (a) a member has no `photo_public_id`, OR (b) the viewer has `data_saver=True`.

Algorithm:
- Initials = `first_name[0] + last_name[0]`, uppercased.
- Background hue = `int(hashlib.md5(str(slug).encode()).hexdigest()[:8], 16) % 360` — deterministic across processes (Python's built-in `hash()` is salted and unsuitable). Saturation 55%, lightness 45%; foreground white.
- CSS-only render via the `{% member_avatar member size=240 %}` template tag, output is a `<div class="avatar avatar-initials">` with inline `style="background:..."`.

Tests assert: same slug always yields same hue; foreground/background contrast ≥ WCAG AA (4.5:1) for the generated palette.

---

## 12. Management command + fixtures

### 12.1 `manage.py create_member`

```
python manage.py create_member \
  --email idrissa@example.com \
  --first-name Idrissa \
  --last-name Saidou \
  --years 1980 1981 1982 1983 \
  --classes 6e 5e 4e 3e \
  --city Niamey \
  [--password <pwd>] \
  [--nickname Idi] \
  [--profession Enseignant] \
  [--country Niger]
```

Behavior:
- Creates a `User` (Allauth) and a `Member`. If `--password` omitted, sets an unusable password (member can request a reset).
- Idempotent on email: re-running with the same email updates the existing Member's editable fields.
- Validates years and classes against the same rules as `Member.clean()`.
- Auto-creates `NotificationPreference` via the signal.
- Does **not** create a `ConsentRecord` — the next login will trigger the charter flow.

### 12.2 Fixtures

`members/fixtures/seed_members.json` holds 6-8 representative members spanning the 1980-1985 cohort with varied cities (Niamey, Zinder, Paris, Cotonou, Niamey, Maradi) and professions. Loaded via `manage.py loaddata seed_members` for dev and test setup.

---

## 13. Test Strategy (TDD — every test written before implementation)

| File | Coverage |
|------|----------|
| `test_models.py` | Field constraints, `clean()` validation (years range, grade choices), `save()` normalization (city/country title-case), `full_name` property, `status` enum CHECK, soft-delete semantics. |
| `test_signals.py` | Creating a Member auto-creates `NotificationPreference` with the documented defaults. |
| `test_create_member_command.py` | Happy path, idempotency on email, rejects invalid year, rejects invalid grade, missing required arg, password optional. |
| `test_views_directory.py` | Empty state, full-text search (incl. accent-insensitive), each filter, combined filters, pagination boundaries (page=0, page=-1, page>max), HTMX partial response, anonymous → login redirect, `noindex` meta present, suspended/deleted excluded. |
| `test_views_profile.py` | Detail renders for active, 404 for deleted, 404 for suspended (non-admin), 200 for suspended (admin). Edit form locks `first_name`/`last_name`/`years_attended`/`classes`/`status`. `show_email/whatsapp/city` toggles correctly hide/show fields on detail page. Data-saver replaces image with initials. |
| `test_views_charter.py` | First login redirects to charter, accepting POSTs creates `ConsentRecord` with IP, charter renders Markdown, `next` param honored, version bump re-prompts. |
| `test_middleware.py` | LoginRequired whitelist works (`/`, `/health`, `/accounts/*`, `/static/*`), non-whitelisted paths redirect. ConsentRequired skips `/charte/`, redirects others. Session cache short-circuits DB query. |
| `test_cloudinary.py` | Sign endpoint requires login + consent. Folder is server-pinned (client-supplied folder ignored). Rate limit kicks in at 11th request/min. FakeCloudinary used in all tests. Lazy URL builder produces expected transform string. |
| `test_avatar.py` | Initials extracted correctly; same slug → same color; WCAG AA contrast on generated palette. |
| `test_i18n.py` | Directory, profile, edit, charter pages render French strings (extends P1's i18n smoke). |
| `test_a11y.py` | Forms have label-for-id associations, required fields marked with `aria-required`, error messages associated via `aria-describedby`, headings hierarchical. Implementation: HTML structure assertions via Django test client + `BeautifulSoup`; full axe-core scans deferred to a future visual-regression phase. |

**Test infrastructure:**

- `conftest.py` provides `member_factory`, `consenting_member_client` (logged-in + consent recorded), and `fake_cloudinary` fixtures.
- `settings.test` swaps in `FakeCloudinary`.
- pytest-django's `--reuse-db` works with the new migrations.

---

## 14. Error handling and edge cases

| Case | Behavior |
|------|----------|
| Cloudinary upload fails browser-side | Inline error in profile form; photo unchanged. |
| `/profil/` POST receives `photo_public_id` outside `members/<slug>/` | 400 Bad Request, photo not persisted. |
| Member tries to view `/membres/<slug>/` for `status='deleted'` member | 404 (not 410, to avoid leaking existence). |
| Member tries to view `/membres/<slug>/` for `status='suspended'` and viewer is not staff | 404. |
| Search query > 80 chars | Truncated server-side with no error. |
| Invalid `year` filter (e.g., `year=9999`) | Silently dropped from the query. |
| `page=0` or `page=-1` | Clamped to page 1. |
| `page > max_page` | Clamped to last page. |
| Sign endpoint receives 11th request in 60 s | 429 with Retry-After header. |
| User with no `Member` (impossible after P3 wiring, possible during P2 dev) | Redirect to `/charte/` fails gracefully → 500 is acceptable; document that `create_member` must be used in dev. |
| Consent middleware loop (charter redirects to charter) | Whitelisted explicitly to break the cycle. |

---

## 15. i18n and a11y notes

- Every user-visible string passes through `gettext_lazy` or `{% trans %}`.
- `manage.py makemessages -l fr` after every PR touching templates; `compilemessages` in CI (already established by P1).
- Forms inherit P1's a11y baseline: `<label for="...">`, error messages tied via `aria-describedby`, required fields marked.
- Directory cards use `<article>` with proper heading hierarchy.
- HTMX swaps use `aria-live="polite"` regions so screen readers announce result updates.
- Color contrast on initials avatars verified ≥ WCAG AA.

---

## 16. Dependencies on other phases

- **P1 (shipped)** — Allauth login flow, base template, Tailwind tokens, i18n machinery, CI.
- **P3 (next)** — will create `User` + `Member` rows via the cooptation flow; in P2 we use `create_member` for the same effect. P3 will also reference `Member` as `CooptationRequest.parrain`; our model supports this with no changes.
- **P4** — will re-use `Member.first_name` and `Member.last_name` for `PublicSearchEntry.last_name_initial`. No changes required from P2 side.
- **P5** — will reference `Member` from `Memory.author` and `PhotoTag.tagged_member`. No changes required from P2 side.
- **P6** — will add Cloudinary orphan reconciliation + RGPD purge cascading through `User → Member → ConsentRecord/NotificationPreference`. The CASCADE chain is correct as designed.

---

## 17. Open questions / risks (non-blocking for spec)

1. **Charter content for v1.0.** Placeholder French text will be drafted during planning; final wording is a stakeholder review. Spec mechanism does not block.
2. **Markdown renderer choice.** `markdown` (Python lib) vs `django-markdownify`. Resolved during planning — both are trivial drop-ins.
3. **Distinct-cities dropdown caching.** Acceptable to skip caching at MVP scale (~50 members). Add 1-hour cache when membership crosses ~200.
4. **`profession` autocomplete.** Free-text icontains works but is rough. P3 may introduce a controlled vocabulary; P2 stays free-text.
5. **NotificationPreference defaults review.** The opt-in stance for `digest_weekly` and `event_alerts` was chosen for GDPR safety. If the project owner wants opt-out, change the migration default before P2 ships — easy reversal.

---

## 18. Acceptance criteria

P2 ships when:

- Every plan task is a single atomic commit on the feature branch.
- The full project test suite is green: P1's existing 19 tests in `core/` plus all new tests in `members/`.
- `make check && make lint && make test` exits cleanly.
- A logged-in test member can: see `/annuaire/`, search by accented name, filter by year+city, open a card, view another member's profile (with privacy toggles honored), edit their own profile (locked fields blocked), upload a photo via Cloudinary signed flow, toggle data-saver, accept the charter on first login.
- `STATUS.md` updated with the P2 row marked Complete.
- `git tag v0.2.0-membership` after merge to `main`.
