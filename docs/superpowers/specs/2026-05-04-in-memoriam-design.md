# In Memoriam (P5b) — Design Spec

**Date:** 2026-05-04
**Status:** Approved (pending implementation)
**Predecessor:** P5a (Mur des souvenirs) · master spec §6.5, §7.2, §9.4, Annexe D, §E.4

---

## Goal

Wire the previously-decorative "In Memoriam" landing card to a real, member-only surface honoring deceased CEG 1 Birni alumni. Admin-curated per Annexe D (family consent gate); members can nominate a camarade for a fiche but never publish content directly.

The page is the emotional counterweight to the "Anciens à retrouver" public surface. Both ship as part of MVP per the master spec, and both are referenced in the landing narrative ("…une page In Memoriam pour celles et ceux qui nous ont quittés en chemin").

---

## Non-goals (explicit YAGNI)

- **Public-facing In Memoriam.** Master spec §6.5 is explicit: "Aucun défunt dans cette liste" (the public ghost list). The page is `noindex` + login-gated, like the directory and the souvenirs gallery.
- **Member-submitted tributes to existing fiches** (the original brainstorming Option B). Defer to Phase 2 — opening a moderation queue for free-text member content about a deceased person is an emotional minefield and not load-bearing for MVP.
- **Search/filter beyond alphabetical sort.** MVP scope is 1–3 fiches (US-09); building a search interface for 3 cards is YAGNI.
- **Weekly In Memoriam digest cron.** Master spec §E.4 puts a weekly digest in Phase 2. We send a single immediate email per fiche on publish, not a digest.
- **"Mes nominations" dashboard for the nominator.** Admin handles offline; a member can email if they want a status update.
- **Self-service family retrait portal.** Annexe D §D.4 says the admin handles archival. The detail page footer surfaces a contact `mailto:` and that's it.
- **Bulk import or seed fixture beyond the 1–3 fiches the team prepares manually.** Annexe D consent must be obtained per fiche; there is no "seed dataset" path that bypasses that.

---

## A. Scope (load-bearing decisions baked in)

- **Member-submission scope:** Option A (nomination only). Members propose a deceased camarade; the admin runs Annexe D (contacts family, gets consent, drafts the fiche, publishes). Members never submit publishable content.
- **Access:** member-only for both browse and nomination. Anonymous visitors clicking the landing card hit `/accounts/login/?next=/in-memoriam/`.
- **Notifications:** combination A+C from brainstorming.
  - **C** (admin alert on nomination): when a member submits a nomination, an email goes to the admin emails list.
  - **A** (member alert on publish): when a fiche transitions draft→published, every member with `NotificationPreference.notif_in_memoriam=True` receives a one-shot email. No digest.
- **Visual treatment:** mirrors P5a (heritage typography, `font-display`) with `ceremonial-gold` accent and the 🕊️ icon already in use on the landing card. Same rounded-2xl card surface as the rest of the site.
- **Status lifecycle:** `draft` → `published` → `archived`. Mirrors P5a exactly. Drafts and archives 404 even to authenticated members.

---

## B. Architecture

New Django app `memoriam/` (singular, mirrors `core`/`members`/`cooptation`/`memoires`).

```
memoriam/
    __init__.py
    apps.py                  # MemoriamConfig with signal wiring in ready()
    models.py                # InMemoriamEntry + InMemoriamNomination
    admin.py                 # 2 admin classes
    forms.py                 # NominationForm, InMemoriamEntryAdminForm
    views.py                 # 3 views (list, detail, nominate)
    urls.py                  # 4 URLs (list, detail, nominate, nominate_thanks)
    emails.py                # Resend wrappers (nomination_received, fiche_published)
    signals.py               # AuditLog handlers (3 signals)
    migrations/0001_initial.py
    templates/memoriam/
        list.html
        detail.html
        nominate.html
        nominate_thanks.html
        email/
            nomination_received.txt   # to admin emails
            nomination_received.html
            fiche_published.txt        # to opted-in members
            fiche_published.html
    tests/
        __init__.py
        conftest.py                    # factories
        test_models.py
        test_admin.py
        test_views.py
        test_nomination.py
        test_emails.py
        test_signals.py
        test_landing_wire.py
```

Cloudinary integration uses the existing `alumni.cloudinary.upload_file()` + URL helpers added in P5a. No new Cloudinary surface.

AuditLog signal pattern from P4b (`core/signals.py`-style) records `in_memoriam_published`, `in_memoriam_archived`, `in_memoriam_nominated`.

---

## C. Models

### `InMemoriamEntry`

| Field | Type | Notes |
|---|---|---|
| `full_name` | `CharField(max_length=200)` | Display name |
| `nickname` | `CharField(max_length=80, blank=True)` | Surnom |
| `years_attended` | `ArrayField(IntegerField, choices=1980..1985)` | Mirrors `Member.years_attended` |
| `classes` | `ArrayField(CharField(max=8))` | Section letters allowed (4eA, 3eB) — mirrors `AdminApplication.classes` post-P3 |
| `birth_year` | `IntegerField(null=True, blank=True)` | Optional, sensitive |
| `death_year` | `IntegerField(null=True, blank=True)` | Optional, sensitive |
| `photo_public_id` | `CharField(max_length=200, blank=True)` | Cloudinary ID, mirrors `Memory.photo_public_id` |
| `tribute` | `TextField` | Markdown-rendered (use existing `markdown` helper from charter) |
| `family_consent_giver` | `CharField(max_length=200)` | Annexe D D.5 — name of family member who gave consent |
| `family_consent_date` | `DateField` | Annexe D D.5 |
| `family_consent_canal` | `CharField(choices=email/whatsapp/phone/in_person)` | Annexe D D.5 |
| `approved_content_version` | `IntegerField(default=1)` | Annexe D D.5 — bumped on text edits via admin save_model |
| `created_by` | `FK(User, on_delete=PROTECT)` | Admin who created |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |
| `published_at` | `DateTimeField(null=True, blank=True)` | Set in admin save_model on first draft→published transition |
| `status` | `CharField(choices=draft/published/archived, default=draft)` | |

**Validation in `clean()`:**
- `years_attended` values within 1980–1985 (mirrors Member.clean()).
- `classes` validated against `VALID_CLASS_PATTERN` (mirrors AdminApplication.clean()).
- `family_consent_giver`, `family_consent_date`, `family_consent_canal` all required when `status='published'` (defense in depth — admin form normally enforces this, but model-level guard prevents an admin shortcut).

**Manager:** `InMemoriamEntry.published` returns `status='published'` only (the list view uses this).

### `InMemoriamNomination`

| Field | Type | Notes |
|---|---|---|
| `nominator` | `FK(Member, on_delete=PROTECT)` | The logged-in member who submitted |
| `proposed_name` | `CharField(max_length=200)` | |
| `proposed_nickname` | `CharField(max_length=80, blank=True)` | |
| `proposed_years` | `ArrayField(IntegerField, blank=True, default=list)` | Best-guess years |
| `personal_memory` | `TextField` | Why this person deserves a fiche; helps admin draft |
| `family_contact_hint` | `TextField(blank=True)` | Names, phone numbers, etc.; helps admin reach out |
| `submitted_at` | `DateTimeField(auto_now_add=True)` | |
| `status` | `CharField(choices=pending/accepted/declined/duplicate, default=pending)` | |
| `reviewed_by` | `FK(User, null=True, blank=True, on_delete=SET_NULL)` | Admin who reviewed |
| `reviewed_at` | `DateTimeField(null=True, blank=True)` | |
| `admin_note` | `TextField(blank=True)` | Internal |
| `linked_entry` | `FK(InMemoriamEntry, null=True, blank=True, on_delete=SET_NULL)` | Set if accepted |

Visibility is admin-only — no member-facing list of nominations (nominator can't see their own status). They email if they care.

---

## D. Views & URLs

URL prefix: `/in-memoriam/` (note hyphen — French SEO-friendly slug, matches the landing copy "page In Memoriam"). All views under `LoginRequiredMiddleware` + `ConsentRequiredMiddleware` (already in place). All templates `{% extends "base.html" %}` + `{% block meta_robots %}noindex,nofollow{% endblock %}`.

| URL | Name | View | Description |
|---|---|---|---|
| `/in-memoriam/` | `memoriam:list` | `MemoriamListView` (TemplateView) | Lists `InMemoriamEntry.published` ordered by `full_name`. Cards: photo-or-initials, name, years badge, tribute teaser (first ~120 chars of stripped tribute, computed via a `tribute_teaser` model property that strips markdown then truncates on a word boundary). CTA "Nominer un camarade" links to nominate. |
| `/in-memoriam/<int:pk>/` | `memoriam:detail` | `MemoriamDetailView` (DetailView) | 404 on `draft` or `archived` (mirrors P5a Memory). Photo (full quality, Cloudinary `memory_full_url`-style helper), full tribute (markdown), years/classes line, optional birth–death year line. Footer paragraph: "Toute famille souhaitant le retrait peut écrire à `<mailto:settings.MEMORIAM_CONTACT_EMAIL>`". |
| `/in-memoriam/nominer/` | `memoriam:nominate` | `NominateView` (FormView) | `NominationForm`. Rate-limited via `django-ratelimit`: 1 successful submission per Member per 24h (key: `user`). On success → redirect to `nominate_thanks`. |
| `/in-memoriam/nominer/merci/` | `memoriam:nominate_thanks` | `NominateThanksView` (TemplateView) | Confirmation page; copy emphasizes admin will reach out and that publication requires family consent. |

Nav link in `templates/base.html` (member-only desktop + mobile, between Souvenirs and Cooptation), label "In Memoriam" with the 🕊️ glyph.

---

## E. Admin

### `InMemoriamEntryAdmin`

- Form: `InMemoriamEntryAdminForm` with a transient `photo` `FileField` (mirrors `MemoryAdminForm` from P5a).
- `save_model` (mirror of `memoires.admin.MemoryAdmin.save_model`):
  1. **Detect transitions before mutating.** Load the pre-save DB row (or use `change=False` for new objects) to compare. Capture `was_unpublished = (db_obj is None) or (db_obj.published_at is None)` and `text_changed = any of full_name/nickname/tribute differs from db_obj` (only relevant when `change=True`).
  2. If `photo` provided in the form → call `alumni.cloudinary.upload_file(file, folder="in-memoriam")`, store returned `public_id`. If `obj.photo_public_id` was set, call `cloudinary.delete(old_public_id)` after successful upload.
  3. If `text_changed` and `change=True` → bump `obj.approved_content_version` by 1 (Annexe D D.5). Any non-equal change counts (whitespace included — simpler and defensible).
  4. If `obj.status == 'published'` and `was_unpublished` → set `obj.published_at = timezone.now()`. Mark `should_fire_publish_email = True`.
  5. If `change=False` (new object) → set `obj.created_by = request.user`.
  6. Call `super().save_model(...)`.
  7. Post-save: if `should_fire_publish_email`, iterate `Member.objects.filter(notification_preference__notif_in_memoriam=True)` and dispatch `fiche_published` email per recipient. Synchronous; fire-and-forget per recipient via Resend, same as P3 (no Celery in this phase).

  Note: republishing a fiche that was archived back to `published` does NOT re-fire the email (`published_at` is already set, so `was_unpublished` is False). This is intentional — the publish email is a one-shot life-event signal.
- List display: `full_name`, `years_attended`, `status`, `published_at`, `created_by`.
- List filter: `status`.
- Search: `full_name`, `nickname`.
- Read-only: `created_by`, `created_at`, `updated_at`, `published_at`, `approved_content_version`.

### `InMemoriamNominationAdmin`

- List display: `proposed_name`, `nominator`, `status`, `submitted_at`, `reviewed_at`.
- List filter: `status`.
- Search: `proposed_name`, `nominator__full_name`.
- Read-only: `nominator`, `submitted_at`, `proposed_name`, `proposed_nickname`, `proposed_years`, `personal_memory`, `family_contact_hint` (the nomination content is immutable; admin only edits status fields).
- Editable: `status`, `admin_note`, `linked_entry`. On status change to non-pending, `reviewed_by` and `reviewed_at` autostamp via `save_model`.

---

## F. Notifications

Two distinct emails, both via the existing `cooptation/emails.py` Resend pattern.

### F.1 Nomination received (admin alert)

- **Trigger:** `InMemoriamNomination.objects.create(...)` post-save signal on first creation (status='pending').
- **Recipients:** `settings.MEMORIAM_ADMIN_EMAILS` (list, defaults to `settings.ADMINS` email column).
- **Templates:** `memoriam/email/nomination_received.{txt,html}`.
- **Subject:** `[In Memoriam] Nouvelle nomination : {{ proposed_name }}`.
- **Body:** Nominator, proposed name + years, personal memory, family contact hint, link to admin URL of the nomination.

### F.2 Fiche published (member alert)

- **Trigger:** `InMemoriamEntryAdmin.save_model` step 7 above (only on first transition to `published`, identified by `published_at` being unset pre-save). Iterates `Member.objects.filter(notification_preference__notif_in_memoriam=True)`, sends one email per member synchronously. At MVP scale (≤ 50 members, ≤ 3 fiches/year, ~150 emails/year max) this stays well within Resend free tier 100/day so long as the admin doesn't bulk-publish. Same caveat documented in the runbook for cooptation onboarding.
- **Templates:** `memoriam/email/fiche_published.{txt,html}`.
- **Subject:** `Une nouvelle page In Memoriam : {{ entry.full_name }}`.
- **Body:** Heritage tone, link to detail page (`SITE_URL` + `entry.get_absolute_url()`), opt-out hint at footer ("Vous recevez cet email car votre profil a coché 'In Memoriam' dans les préférences de notification").

---

## G. AuditLog wiring

Mirrors P4b's signal pattern (`core/signals.py` style). Three signals:

| Signal | Action | Metadata |
|---|---|---|
| `InMemoriamEntry.post_save`, transitions to `published_at` set for first time | `in_memoriam_published` | `{entry_id, full_name, version}` |
| `InMemoriamEntry.post_save`, status='archived' (was not before) | `in_memoriam_archived` | `{entry_id, full_name}` |
| `InMemoriamNomination.post_save`, on creation | `in_memoriam_nominated` | `{nomination_id, proposed_name, nominator_id}` |

`actor` resolved from `created_by` / `reviewed_by` / `nominator.user`.

---

## H. Landing-card wire

`templates/core/landing.html:161-167` — the current `<article>` becomes a link.

```html
<a href="{% if request.user.is_authenticated %}{% url 'memoriam:list' %}{% else %}{% url 'account_login' %}?next={% url 'memoriam:list' %}{% endif %}"
   class="rounded-2xl border border-secondary/15 bg-surface/70 p-6 shadow-sm hover:border-tertiary/40 transition">
    <span class="inline-flex h-10 w-10 items-center justify-center rounded-full bg-ceremonial-gold/15 text-ceremonial-gold text-xl">🕊️</span>
    <h2 class="mt-4 font-display text-xl font-semibold tracking-tight">{% trans "In Memoriam" %}</h2>
    <p class="mt-2 text-sm text-secondary leading-relaxed">
        {% trans "Un espace de recueillement pour celles et ceux qui nous ont quittés." %}
    </p>
</a>
```

Same hover treatment as the Cooptation card alongside it.

---

## I. Settings additions

`alumni/settings/base.py`:

```python
INSTALLED_APPS += ["memoriam"]

# Family retrait inquiries (Annexe D §D.4)
MEMORIAM_CONTACT_EMAIL = env("MEMORIAM_CONTACT_EMAIL", default=DEFAULT_FROM_EMAIL)

# Admin alert recipients for new nominations
MEMORIAM_ADMIN_EMAILS = env.list("MEMORIAM_ADMIN_EMAILS", default=[a[1] for a in ADMINS])
```

`Dockerfile`: add `COPY memoriam/ ./memoriam/` in **both** css-builder stage and runtime stage (same regression we just fixed for `memoires/`).

---

## J. Tests (~22 new)

| Suite | Tests | Notes |
|---|---|---|
| `test_models.py` | ~7 | Defaults, status choices, `clean()` rejects bad classes / years, `clean()` rejects published without consent fields, `published_at` set logic, `approved_content_version` semantics, `InMemoriamNomination` defaults |
| `test_admin.py` | ~4 | `save_model` uploads photo + deletes old `public_id` (uses fake Cloudinary), bumps `approved_content_version` on text edit, sets `published_at` on transition, autostamps `created_by` on new |
| `test_views.py` | ~5 | List view — anon redirect, member 200, only published in queryset; Detail view — draft 404, archived 404, published 200 |
| `test_nomination.py` | ~4 | GET 200, POST creates `InMemoriamNomination(status=pending)`, rate limit triggers on 2nd POST within 24h, success redirects to thanks |
| `test_emails.py` | ~3 | Nomination submit fires email to `MEMORIAM_ADMIN_EMAILS`; publish transition fires to opted-in members; opted-out members do not receive |
| `test_signals.py` | ~3 | AuditLog rows on publish, archive, nominate |
| `test_landing_wire.py` | ~1 | Landing card now contains `href` to `/in-memoriam/` (not just an `<article>`) |

Total target: ~22 new tests. Full suite expected: ~427 passing (405 current + 22).

Tests use the existing `make_member`, `make_application` factories from `cooptation/tests/conftest.py` plus a new `make_memoriam_entry`, `make_memoriam_nomination` in `memoriam/tests/conftest.py`. Cloudinary tests use `alumni.cloudinary.FakeCloudinary` per the existing pattern.

---

## K. Risks & migration notes

- **No DB schema risk.** Two new tables, no FKs to existing tables beyond `Member` and `User` (both well-indexed).
- **Resend cap.** Publishing a fiche fires N emails synchronously in the admin save. At MVP scale (~50 members, ≤ 3 fiches), well within free-tier 100/day. Documented constraint, not a code constraint.
- **Annexe D adherence.** The `family_consent_*` fields are required at the model level when `status='published'`, so an admin can't accidentally publish a fiche without recording consent. This is the load-bearing data-integrity guarantee of this phase.
- **Cloudinary folder pinning.** Photos go to `in-memoriam/` folder (separate from `memories/`). Required so a future bulk-purge of memories doesn't accidentally drop In Memoriam photos.
- **Notification fatigue.** Initial design fires one email per opted-in member on every fiche publish. Worst case (e.g., five fiches in a week) is five emails per opted-in member. We accept this: the opt-in flag is explicit consent, and at MVP scale it won't actually happen. If it becomes a problem, P9 adds a digest cron that drains a queue.
- **Operational ripple.** Once shipped, the In Memoriam card on the landing becomes a real link. First-time visitors who aren't logged in get bounced through `/accounts/login/` — same behavior as the Souvenirs card already has via the directory route.
- **Allauth version pin** (carried from P5a/styled-allauth-templates): `allauth>=65.0`. No new Allauth surface introduced here.

---

## L. Open questions (all resolved during brainstorming)

- **Scope of member submission?** Option A only (nomination, no member-published content). Tributes-to-existing-fiches deferred to Phase 2.
- **Visibility?** Member-only (login-gated, noindex).
- **Notifications?** A+C: admins on nomination, opted-in members on publish. No digest.
- **Search/filter?** Alphabetical sort only — YAGNI for 1–3 fiches.
- **Member-facing "my nominations" view?** No — admin handles offline.
- **Family retrait flow?** `mailto:` link in detail footer; admin archives manually. Annexe D §D.4 satisfied.
