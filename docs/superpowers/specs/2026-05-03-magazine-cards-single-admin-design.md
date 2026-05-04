# P4d — Magazine Ghost Cards + Single-Admin Governance (Design Spec)

**Date:** 2026-05-03
**Status:** Approved (pending implementation)
**Predecessors:** P4a (Public Surface), P4b (Public Surface Governance), P4c (Public Surface Admin)
**Successor:** P5 (Mémoire seed)

---

## Goal

Two coupled changes to the public ghost-list surface on the landing page:

- **(A)** Redesign the ghost cards with magazine warmth — monogram circle avatar, gold accent bar, warmer chrome — to replace the plain compact style currently on `style/landing-ghost-cards-magazine` (uncommitted).
- **(B)** Drop the 2-signoff publication requirement so a single admin's add immediately publishes the entry, with a tripwire FYI email to all other admins on creation.

No DB schema changes. No migrations. ~7 new tests, ~3 updates, 1 deletion. Single phase.

## Non-goals (explicit YAGNI)

- No new "ghost reviewer" role/group — all `is_staff=True, is_active=True` users receive the notification.
- No approval-queue UI — the create-publishes-immediately flow is the whole point.
- No timed grace period (e.g., "publishes in 24h after add") — adds operational complexity for marginal safety.
- No HTML editor for the `note` field — keep it plain text.
- No member-facing ghost-add path — admins only via Django admin.
- No "request removal" rebrand for the new card; the existing `RemovalRequest` flow (P4b) is unchanged.

---

## A. Card redesign

Visual direction: **(d) monogram circle + gold accent bar** (per brainstorming).

### Visual specification

- **Monogram circle** — 48×48px disc on the left of the card.
  - Background: `bg-ceremonial-gold/20` (existing alumni theme token, very light warm tint).
  - Initials: `font-display`, bold, `text-primary` color (or `text-ceremonial-gold` for stronger contrast — implementer's call after preview).
  - Initials = first letter of `entry.first_name` + first letter of `entry.last_name_initial` (e.g., "Idrissa S." → "IS"). Computed in template via Django string slicing or a small `{% with %}` block; no model change.
  - 16px font for the initials; matches the small avatar idiom familiar from member-directory cards.
- **Gold accent bar** — `border-l-4 border-ceremonial-gold` on the left edge of each card, full height. Uses existing `ceremonial-gold` color token.
- **Card chrome** — warmer than the rest of the page, but subtle:
  - `bg-ceremonial-gold/5` (very light warm tint as background).
  - `rounded-xl` corners (slightly less rounded than the current `rounded-2xl` for editorial geometry).
  - `border-secondary/15` soft border on right/top/bottom (left edge is the gold bar).
  - `p-6` for generous padding.
  - No shadow — keeps the card flat-elegant rather than card-stacked.
- **Layout** — flex row on desktop, stack on mobile (sm: column, md+: row).
  - Avatar fixed left (with `flex-shrink-0`).
  - Content column flexes right.
  - Inside content column:
    - **Name** — `font-display`, `text-lg`, `text-primary`, bold. (e.g., "Idrissa S.")
    - **Years** — small line below name, `text-sm text-secondary`: `au CEG {first_year}-{last_year}`.
    - **Note** (if present) — italic line, `text-sm text-secondary mt-1`.
    - **Helper line** — `text-sm italic text-secondary mt-3`: "Si vous le connaissez, partagez ce lien." (matches Direction B's exact copy).
    - **Removal link** — small footer line, right-aligned within the content column, `text-xs text-secondary mt-3`: "Retirer mon nom" → existing `{% url 'members:removal_request_form' entry.removal_token %}` (RGPD requirement from P4b, unchanged).
- **Spacing between cards** — `space-y-4` (looser than the current `space-y-3` to match the magazine breathing room).

### Section heading (unchanged)

The "NOUS RECHERCHONS AUSSI…" pill + "Anciens encore à retrouver" h2 above the cards stays as-is. Only the cards themselves change.

### Mobile responsiveness

- Below `md:` breakpoint, the avatar drops above the content column instead of beside it. Avatar centers; rest of content remains left-aligned.
- The accent bar stays on the left at all viewports.
- The removal link wraps below if needed; the right-alignment is `md:` only.

---

## B. Single-admin publication

### View change

`core/views.py:landing_view` — change the publication gate:

**Before:**
```python
ghosts = list(
    PublicSearchEntry.objects.filter(removed_at__isnull=True)
    .annotate(n=Count("added_by_admins"))
    .filter(n__gte=2)
)
```

**After:**
```python
ghosts = list(
    PublicSearchEntry.objects.filter(removed_at__isnull=True)
    .annotate(n=Count("added_by_admins"))
    .filter(n__gte=1)
)
```

The `annotate` + `filter(n__gte=1)` is preserved (rather than dropped entirely) for two reasons: (1) catches the edge case where the auto-add fails for some reason and the entry has zero signoffs — better to hide than show a "ghost ghost", (2) the query plan is identical in cost since the index is already there.

### Auto-add creator on admin save

`members/admin.py:PublicSearchEntryAdmin` — add `save_model`:

```python
def save_model(self, request, obj, form, change):
    super().save_model(request, obj, form, change)
    if not change:
        obj.added_by_admins.add(request.user)
```

`change=False` means this is the initial create. On subsequent edits, the creator is not re-added (already a member of the M2M).

This makes the act of creation simultaneous with the act of vouching. Admins no longer need to remember to check their own name in the M2M widget.

### Admin form copy update

`members/admin.py:PublicSearchEntryAdmin.fieldsets` — rewrite the cosignature section:

**Before:**
```python
(
    "Cosignature (2 admins requis pour publication)",
    {
        "fields": ("added_by_admins",),
        "description": (
            "Ajoutez-vous à la liste pour cosigner. Au moins 2 admins "
            "distincts requis avant que le nom n'apparaisse publiquement."
        ),
    },
),
```

**After:**
```python
(
    "Cosignataires (optionnel)",
    {
        "fields": ("added_by_admins",),
        "description": (
            "Vous êtes ajouté·e automatiquement à l'enregistrement. "
            "D'autres admins peuvent ajouter leur nom pour étoffer la "
            "trace d'audit, mais ce n'est plus requis pour la publication."
        ),
    },
),
```

### `GhostStatusFilter` cleanup

`members/admin.py:GhostStatusFilter` — drop two now-meaningless buckets, simplify the rest.

**Before** (5 buckets):
- `draft` — 0 signatures
- `pending` — 1 signature
- `published` — 2+ signatures (within 12 months)
- `stale` — 2+ signatures, >12 months
- `removed`

**After** (3 buckets):
- `published` — `n >= 1` AND `removed_at IS NULL` AND `added_at > now - 365 days`
- `stale` — `n >= 1` AND `removed_at IS NULL` AND `added_at <= now - 365 days`
- `removed` — `removed_at IS NOT NULL`

The `n=0` case (which `draft` covered) becomes vanishingly rare with auto-add. We don't need a UI bucket for it; if it occurs, the entry simply doesn't show on the landing and admins can find it by clearing the filter.

---

## C. Notification email — "admin_ghost_added"

Single new email, fired once per ghost-entry creation, FYI tone with rich preview.

### Trigger

The email fires from `PublicSearchEntryAdmin.save_model` directly, not from a Django signal. Reasoning: `post_save` fires before the auto-add of the creator to `added_by_admins`, so a signal handler couldn't read `instance.added_by_admins.first()` reliably to identify the creator. Triggering from `save_model` lets us pass `request.user` explicitly and keeps the trigger close to the action.

Updated `save_model` in `members/admin.py:PublicSearchEntryAdmin`:

```python
def save_model(self, request, obj, form, change):
    super().save_model(request, obj, form, change)
    if not change:
        obj.added_by_admins.add(request.user)
        from .emails import send_admin_ghost_added
        send_admin_ghost_added(obj, added_by=request.user)
```

Trade-off: notification is coupled to the admin code path. Acceptable because admins are the only creation surface; if a future phase adds a non-admin creation surface (e.g., a member-side ghost-add form), the call will need to move there too. No signal handler is added in this phase.

### Recipients

All `is_staff=True, is_active=True` users **except** the creator. Different from existing `send_admin_removal_notification` (which includes everyone) — but this email's whole point is "tell other admins what just happened", so the creator already knows.

```python
def send_admin_ghost_added(entry, *, added_by):
    User = get_user_model()
    recipients = list(
        User.objects.filter(is_staff=True, is_active=True)
        .exclude(pk=added_by.pk)
        .values_list("email", flat=True)
    )
    recipients = [e for e in recipients if e]
    if not recipients:
        return
    send_email(
        recipients,
        "members/admin_ghost_added",
        {"entry": entry, "added_by": added_by},
    )
```

### Subject

`Nouvelle fiche fantôme : {{ entry.first_name }} {{ entry.last_name_initial }}`

### Body — HTML and plain-text

Both formats include:
- Greeting + lead: "{{ added_by.get_full_name|default:added_by.username }} vient d'ajouter une fiche à la liste des anciens recherchés."
- Card preview block:
  - Name: `{{ entry.first_name }} {{ entry.last_name_initial }}`
  - Years: `au CEG {{ entry.first_year }}-{{ entry.last_year }}`
  - Note (if present): `Note : {{ entry.note }}`
  - Added at: `Ajoutée le {{ entry.added_at|date:"d M Y à H:i" }}`
- Quick action: "Si cette fiche ne vous semble pas pertinente, vous pouvez la retirer immédiatement via l'admin :" + link to `/admin/members/publicsearchentry/{{ entry.pk }}/change/`
- Footer: link to admin list view + link to public landing page (so the recipient can preview how the card now appears).

### Templates

3 new files in `members/templates/emails/members/`:
- `admin_ghost_added.subject.txt`
- `admin_ghost_added.html`
- `admin_ghost_added.txt`

Pattern matches the existing `admin_removal_notification.*` family.

---

## D. Testing

### New tests (~7)

| Test | File | Purpose |
|---|---|---|
| `test_ghost_card_includes_monogram_initials` | `core/tests/test_landing_view.py` | Card markup contains the computed initials (e.g., "IS" for "Idrissa S.") |
| `test_ghost_card_uses_gold_accent_bar` | `core/tests/test_landing_view.py` | Card markup includes `border-l-4 border-ceremonial-gold` |
| `test_single_signoff_entry_is_visible_on_landing` | `core/tests/test_landing_view.py` | Replaces the now-inverted `test_ghost_section_hides_single_admin_entries` |
| `test_admin_save_auto_adds_creator_to_signoffs` | `members/tests/test_admin_publicsearchentry.py` (new file) | After admin POST to create form, `entry.added_by_admins` includes `request.user` |
| `test_admin_save_does_not_re_add_creator_on_edit` | `members/tests/test_admin_publicsearchentry.py` | After edit, M2M unchanged (no duplicate) |
| `test_notification_sent_to_other_staff_on_entry_create` | `members/tests/test_emails_ghost_added.py` (new file) | After admin save, email fires to all other staff |
| `test_notification_excludes_creator_from_recipients` | `members/tests/test_emails_ghost_added.py` | Creator not in `to:` list |

### Updated tests (~3)

| Test | File | Change |
|---|---|---|
| `test_ghost_section_renders_published_entries` | `core/tests/test_landing_view.py` | Existing 2-admin setup still works (1+ admins satisfies the new rule); assertions stay |
| `test_ghost_status_filter_buckets` (or equivalent) | `members/tests/test_admin_ghost_filter.py` (existing) | Update assertions: only 3 buckets now (`published`, `stale`, `removed`) |
| `test_ghost_card_includes_removal_link_when_flag_on` | `core/tests/test_landing_view.py` | Stays — RGPD link still required and still rendered |

### Deleted tests (1)

| Test | File | Why |
|---|---|---|
| `test_ghost_section_hides_single_admin_entries` | `core/tests/test_landing_view.py` | The behavior it asserted is now wrong by design |

---

## E. RGPD / governance trade-off (explicit, for future operators)

**What we lose**: pre-publication second-pair-of-eyes safety. A single admin acting in bad faith (or by mistake) can immediately publish an entry naming someone, potentially without that person's knowledge.

**What we replace it with** (defense in depth):

1. **Notification tripwire** — every other admin learns about the add within minutes via email and can remove the entry directly from the admin link in the email body. Median time to "any admin sees it" goes from "whenever they next log in" to "next email check."
2. **Existing public removal flow** (P4b) — anyone named on the public list can request removal via the public form (`/retrait/<token>/`); auto-confirms after token verification. No code change.
3. **AuditLog** (P4b) — `ghost.entry.created` records the creator forever; bad-faith adds remain accountable.
4. **Quarterly digest** (P4c) — admins get a quarterly snapshot of all currently-listed entries — another review opportunity.

The trade-off is documented here so future operators understand why the bar moved. If bad-faith adds become a real problem in production, future phases can re-introduce a 24h grace period or a "two-admin lock" for sensitive entries.

---

## F. Phase plan summary

| # | Task | Files | Tests |
|---|------|-------|-------|
| 1 | Drop 2-signoff in view + delete inverted test | `core/views.py`, `core/tests/test_landing_view.py` | 1 deleted |
| 2 | Magazine card redesign | `templates/core/landing.html` | 2 new |
| 3 | Auto-add creator + admin form copy + filter cleanup | `members/admin.py` | 2 new admin tests + 1 filter update |
| 4 | Notification email (templates + sender + trigger) | `members/emails.py` + 3 templates | 2 new |
| 5 | STATUS.md update | `docs/superpowers/STATUS.md` | — |

Estimated: ~half a day of focused work. ~7 new tests, ~3 updates, 1 deletion across ~5 test files.

## G. Migration notes

- **No DB migration.** No schema change.
- **Data migration needed?** No. Existing entries with 2+ signoffs continue to display. Existing entries with 1 signoff become visible (intended). Existing entries with 0 signoffs remain invisible (intended — defensive).
- **Operational ripple**: when this ships, any draft entries currently sitting at 0 signoffs in admin will need a manual "edit and save" by an admin to trigger the auto-add (since `save_model` fires only on save, not on existing rows). Acceptable: there are no such entries in production today.

## H. File touch list

**Create:**
- `members/templates/emails/members/admin_ghost_added.subject.txt`
- `members/templates/emails/members/admin_ghost_added.html`
- `members/templates/emails/members/admin_ghost_added.txt`
- `members/tests/test_admin_publicsearchentry.py`
- `members/tests/test_emails_ghost_added.py`

**Modify:**
- `core/views.py` — landing_view filter change
- `core/tests/test_landing_view.py` — replace 1 test, add 2, delete 1
- `templates/core/landing.html` — new card markup
- `members/admin.py` — `save_model`, fieldsets copy, `GhostStatusFilter` simplification
- `members/emails.py` — add `send_admin_ghost_added`
- `members/tests/test_admin_ghost_filter.py` (existing) — update assertions for 3 buckets
- `docs/superpowers/STATUS.md`

**Touched but unchanged:**
- All P4b removal flow code paths.
- All P4c cron handlers (stale ghost purge still works on `n>=1` entries).
- AuditLog signals — `ghost.entry.created` continues to fire on `post_save`.
