# P3.1 — Parrain UX Polish (Design Spec)

**Date:** 2026-05-03
**Status:** Approved (pending implementation)
**Predecessor:** P3 (Cooptation), P4a/b/c (Public Surface)
**Successor:** P5 (Mémoire seed)

---

## Goal

Make it easier for parrains to find and respond to pending cooptation requests. Two independent additions, no schema changes, no new emails, no migrations.

- **(A)** New member-only page listing the current user's pending vouches, plus a nav link with optional count badge.
- **(B)** Session lifetime bumped from Django default (2 weeks) to 90 days with sliding expiry, so once a parrain logs in to vouch they stay logged in across all subsequent email clicks.

## Non-goals (explicit YAGNI)

- No new email about the dashboard. Existing `parrain_invitation` email stays as-is; the per-token CTA still works.
- No "recently answered" history section. If a parrain wants to see what they vouched on, it's still in the admin.
- No notification preferences for the dashboard. Passive surface only.
- No pagination. A parrain with more than ~10 pending requests is itself a signal something's wrong.
- No analogous admin-side helper for ghost-list signoffs. The existing `GhostStatusFilter` "Brouillons" bucket already shows single-signoff entries; admins live in the admin daily.

## Naming distinction (load-bearing)

Two existing features could be confused with this work; they are NOT touched:

| Feature | Audience | URL | Data |
|---|---|---|---|
| **"Anciens à retrouver"** (ghost list, P4a/b/c) | Anonymous public visitors | `/`, `/retrait/<token>/` | `PublicSearchEntry`, `RemovalRequest` |
| **"Parrain invitation"** (cooptation, P3) | Members named as parrains | `/cooptation/<token>/` (email link) | `CooptationRequest`, `AdminApplication` |
| **NEW: "Cooptations à valider"** (this spec) | Members named as parrains | `/cooptations-a-valider/` (nav link) | `CooptationRequest` (read-only listing) |

The new page is a member-discoverable index over the same data the per-token email link already exposes one-at-a-time. It does not replace or modify the per-token vouch page — it links to it.

---

## Component A — Pending-vouches dashboard

### URL

Added to `cooptation/urls.py`:

```python
path("cooptations-a-valider/", views.parrain_dashboard_view, name="parrain_dashboard"),
```

URL slug is French-facing; URL name (`cooptation:parrain_dashboard`) stays English/internal.

### View

`cooptation/views.py:parrain_dashboard_view`:

```python
@login_required
@require_http_methods(["GET"])
def parrain_dashboard_view(request):
    member = getattr(request.user, "member", None)
    pending = []
    if member is not None:
        pending = list(
            CooptationRequest.objects
            .filter(parrain=member, response="pending", expires_at__gt=timezone.now())
            .select_related("application")
            .order_by("expires_at")
        )
    return render(request, "cooptation/parrain_dashboard.html", {"pending": pending})
```

**Filtering rules** (deliberate):
- Only `response == "pending"` — already-answered requests aren't actionable.
- Only `expires_at > now()` — expired requests already 410 from the per-token page; hiding them avoids click-to-dead-end.
- Scoped to `parrain == request.user.member` — full identity isolation.
- Authenticated users without a Member (e.g., admins with no Member profile) get an empty list, not an error.
- Ordered by `expires_at` ascending — most urgent first.

### Template

`templates/cooptation/parrain_dashboard.html` extends `base.html`. Structure:

- H1: **"Cooptations en attente de votre validation"**
- Subtitle line explaining the page in one sentence.
- If `pending` is empty: empty-state copy — **"Vous n'avez aucune cooptation en attente. Merci de votre vigilance."**
- Otherwise: card list, one card per request. Each card shows:
  - Candidate `application.full_name`
  - `application.years_attended` (formatted "1980 — 1985")
  - `application.city` and `application.country`
  - Days remaining until `expires_at` (computed in template via `timeuntil` filter)
  - Primary CTA **"Répondre →"** linking to `{% url 'cooptation:parrain_vouch' request_obj.token %}`

Visual style follows existing card patterns (rounded, surface bg, secondary border) — no new design tokens.

### Auth gating

The page requires login (`@login_required`) — member-only by design. It does NOT need to be added to `LOGIN_REQUIRED_WHITELIST` or the basic-auth bypass list.

---

## Component B — Nav integration

### Context processor

New file `cooptation/context_processors.py`:

```python
from django.utils import timezone
from .models import CooptationRequest


def pending_vouches_count(request):
    if not request.user.is_authenticated:
        return {"pending_vouches_count": 0}
    member = getattr(request.user, "member", None)
    if member is None:
        return {"pending_vouches_count": 0}
    count = CooptationRequest.objects.filter(
        parrain=member,
        response="pending",
        expires_at__gt=timezone.now(),
    ).count()
    return {"pending_vouches_count": count}
```

Registered in `alumni/settings/base.py` under `TEMPLATES[0]["OPTIONS"]["context_processors"]`.

**Cost note:** One indexed query per request for authenticated members. The FK `parrain_id` column is auto-indexed by Django (PostgreSQL b-tree), and `CooptationRequest` row count stays small. No caching for v1; revisit only if metrics show it as a hot spot.

### Nav link in `templates/base.html`

Both desktop nav (`<header>` desktop block) and mobile nav get a new entry **between "Annuaire" and "Mon profil"**:

- Label: **"Cooptations à valider"** (or shortened to **"À valider"** on mobile if width is constrained — implementer's call based on visual fit).
- Always rendered for authenticated members. Only the badge is conditional.
- When `pending_vouches_count > 0`, append a small numeric pill (e.g., `<span class="ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-tertiary px-1.5 text-xs font-semibold text-on-tertiary">{{ pending_vouches_count }}</span>`).

The link is always clickable; the badge is the only conditional element. Anonymous visitors don't see the auth nav at all.

---

## Component C — Session lifetime

In `alumni/settings/base.py`:

```python
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90 days
SESSION_SAVE_EVERY_REQUEST = True       # sliding expiry
```

**Why:** Once a parrain logs in to vouch, they stay logged in across all subsequent email clicks for ~3 months of activity. `SESSION_SAVE_EVERY_REQUEST=True` slides the expiry forward on every request, so active members never get logged out unexpectedly.

**Trade-off accepted:** One extra session-row write per request. Negligible at our scale (low hundreds of members, low daily request volume).

**Security posture unchanged:**
- `SESSION_COOKIE_SECURE=True` (staging/prod) — cookie still HTTPS-only.
- `SESSION_COOKIE_SAMESITE="Lax"` — cross-site request protections unchanged.
- HttpOnly defaults — JS still cannot read the cookie.
- This change only affects lifetime, not protections.

**Migration impact:** None. Applies to all current sessions on next request — nobody gets logged out by the change.

---

## Test coverage (~11 tests)

### `cooptation/tests/test_parrain_dashboard.py`

1. Anonymous visitor → 302 redirect to allauth login.
2. Authenticated user with no Member → 200, empty-state copy visible.
3. Authenticated member with zero pending → 200, empty-state copy visible.
4. Authenticated member with two pending → both candidates' names visible, ordered by `expires_at` ascending.
5. Identity isolation: member A's request hidden from member B (only B's requests render).
6. Already-answered requests (response=accepted/refused) not shown.
7. Expired requests (`expires_at <= now`) not shown.
8. Each row links to the correct `{% url 'cooptation:parrain_vouch' request_obj.token %}`.

### `cooptation/tests/test_pending_vouches_count.py`

9. Context processor returns `0` for anonymous users, `0` for authenticated user without Member, correct integer count for member with N pending.
10. Numeric badge appears in nav HTML when count > 0; absent when count == 0.

### `alumni/tests/test_session_settings.py` (new file or extend existing settings test)

11. `SESSION_COOKIE_AGE == 60 * 60 * 24 * 90` and `SESSION_SAVE_EVERY_REQUEST is True`.

---

## Risk / migration notes

- **No DB migration.** No schema change, no data backfill.
- **No new dependency.**
- **Session bump applies to all current users on next request** — nobody gets logged out.
- **The dashboard is a brand-new URL** — no risk to existing flows.
- **Context processor adds one query per authenticated request.** Acceptable at current scale; revisit if profiling flags it.

---

## File touch list

**Create:**
- `cooptation/context_processors.py`
- `cooptation/templates/cooptation/parrain_dashboard.html` (or `templates/cooptation/parrain_dashboard.html` per existing convention)
- `cooptation/tests/test_parrain_dashboard.py`
- `cooptation/tests/test_pending_vouches_count.py`
- `alumni/tests/test_session_settings.py` (or extend an existing test file)

**Modify:**
- `cooptation/urls.py` — add `parrain_dashboard` route
- `cooptation/views.py` — add `parrain_dashboard_view`
- `templates/base.html` — add nav link + badge in both desktop and mobile nav
- `alumni/settings/base.py` — add `SESSION_COOKIE_AGE`, `SESSION_SAVE_EVERY_REQUEST`, register context processor

**Touched but unchanged:**
- All P3/P4 code paths. The new page only reads `CooptationRequest`; it doesn't mutate anything.
