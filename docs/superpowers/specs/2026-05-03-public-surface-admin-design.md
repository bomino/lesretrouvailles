# P4c — Public Surface Admin · Design

**Phase:** P4c (third slice of P4 "Public surface" per `docs/superpowers/STATUS.md`).
**Master spec reference:** § 6.5 "Revue trimestrielle" of `2026-05-01-alumni-platform-design.md`.
**P4a/P4b references:**
- `docs/superpowers/specs/2026-05-03-public-surface-design.md` (P4a)
- `docs/superpowers/specs/2026-05-03-public-surface-governance-design.md` (P4b)
**Date:** 2026-05-03.
**Authors:** BMLa + Claude.

---

## 1. Goal & scope

### Goal

Ship the spec-mandated "12 months → auto-remove" governance sweep so the public ghost list never becomes a *cimetière numérique*, plus a light admin list filter so the 5-person admin team can find pending publications and stale entries with one click.

### In scope (P4c)

| Component | Notes |
|----------|-------|
| Stale-ghost auto-removal handler | Added to existing `cooptation/management/commands/process_cooptation_deadlines.py` (despite the misnomer — see § 3 rationale). Daily idempotent sweep of `PublicSearchEntry` rows that are **published** (`added_by_admins.count() >= 2`), **not yet removed** (`removed_at IS NULL`), and **stale** (`added_at <= now - 365 days`). |
| Quarterly admin digest email | Triggers on day 1 of Jan/Apr/Jul/Oct only. Lists the last 90 days of auto-removals **and** a snapshot of currently-listed entries with their age in months — so admins see runway, not just the past. No-op if no purges in window. |
| 1 new email template | `members/templates/emails/members/admin_stale_ghost_digest.{subject.txt,txt,html}` |
| Custom admin list filter | `GhostStatusFilter` on `PublicSearchEntryAdmin`: 5 buckets — *Brouillon (0 signatures)*, *En attente (1 signature)*, *Publiée (2+)*, *Périmée (>12 mois)*, *Retirée*. |
| AuditLog entries | `ghost.entry.purged` (already in P4b's `ACTION_CHOICES` enum — no schema change) on each auto-removal. |

### Out of scope

| Item | Rationale |
|------|-----------|
| Custom Django admin dashboard view | The list filter + quarterly digest cover the operational need at our scale (5 admins, < 100 entries expected). Build only when we know what admins actually want. |
| "Last chance" warning email at 11 months | Master spec doesn't require it; auto-remove + digest is sufficient. Adds an "extend / renew" mechanism we don't need yet. |
| `published_at` field set when M2M count first reaches 2 | Schema change; the current `added_at` boundary is slightly conservative (entries that took weeks to cosign get auto-removed slightly early) but acceptable for our scale. P4d adds it if admins complain. |
| Renewal/extend mechanism | Re-creating with 2 new cosignatures is the documented path. Add a renewal flow only if it becomes painful. |

### Spec interpretation: "Revue trimestrielle"

Master spec § 6.5 says: *"Revue trimestrielle par les Super Admins : toute personne listée depuis plus de 12 mois sans contact entrant est retirée par défaut (la liste n'est pas un cimetière numérique)."*

Two distinct things in that sentence:
- **Review cadence**: quarterly (every 3 months) — performed by admins
- **Auto-removal trigger**: 12 months stale — automatic

Our design honors both:
- The auto-remove sweep runs **daily** (catching entries within 1 day of crossing the 365-day boundary)
- The admin **review** is triggered by a **quarterly digest** (Jan/Apr/Jul/Oct day 1) that gives admins a quarterly read of (a) what was auto-removed in the last 90 days and (b) the current listing with ages

The quarterly cadence on the digest matches the spec verbatim. The daily-vs-quarterly distinction (auto-remove daily, review quarterly) compresses the "human review burden" from a manual quarterly sweep into a 5-minute quarterly read.

### No data model changes

P4b's `AuditLog` model already includes `ghost.entry.purged` in `ACTION_CHOICES`. `PublicSearchEntry.added_at`, `removed_at`, `removed_reason` cover everything we need.

---

## 2. Cron handler + email

### New handler in `cooptation/management/commands/process_cooptation_deadlines.py`

The existing daily cron has 4 handlers (J+7 reminders, J+14 expiry, stale-questionnaire sweep, retention purge). We add a fifth.

> **Naming rationale.** The command is called `process_cooptation_deadlines` for historical reasons (P3). Its cron service on Railway is already running daily and configured with the right env vars. Adding a 5th handler here is cheaper than introducing a second cron service. The new handler operates on `members.PublicSearchEntry`, not cooptation — the module docstring is updated to call out the cross-domain housekeeping.

**Imports added to the top of `process_cooptation_deadlines.py`:**

```python
from datetime import timedelta
from django.db.models import Count

from members.models import AuditLog, PublicSearchEntry  # cross-app: P4c housekeeping
from members import emails as members_emails

GHOST_STALE_THRESHOLD_DAYS = 365
GHOST_DIGEST_LOOKBACK_DAYS = 90
GHOST_DIGEST_QUARTERLY_MONTHS = (1, 4, 7, 10)
GHOST_STALE_REMOVED_REASON = "Périmée — non renouvelée par les admins"
```

**Handler shape:**

```python
class Command(BaseCommand):
    def handle(self, *args, **opts):
        now = timezone.now()
        # ... existing 4 handler calls ...
        ghosts_purged = self._purge_stale_ghosts(now)
        digest_sent = 0
        if now.day == 1 and now.month in GHOST_DIGEST_QUARTERLY_MONTHS:
            digest_sent = self._send_quarterly_ghost_digest(now)
        self.stdout.write(
            f"Done. reminders={n_reminders} expired={n_expired} "
            f"stale={n_stale} ghosts_purged={ghosts_purged} "
            f"digest_sent={digest_sent} purged={n_purged}"
        )

    def _purge_stale_ghosts(self, now) -> int:
        """Auto-remove published ghost entries older than 12 months.

        'Published' = 2+ admin signoffs. 'Stale' = added_at <= now - 365 days
        AND removed_at IS NULL. Removal is recorded via AuditLog
        (ghost.entry.purged) and the entry's removed_at + removed_reason are
        set so the existing public queryset filters it out automatically.
        """
        cutoff = now - timedelta(days=GHOST_STALE_THRESHOLD_DAYS)
        candidates = (
            PublicSearchEntry.objects
            .filter(removed_at__isnull=True, added_at__lte=cutoff)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=2)
        )
        count = 0
        for entry in candidates:
            entry.removed_at = now
            entry.removed_reason = GHOST_STALE_REMOVED_REASON
            entry.save(update_fields=["removed_at", "removed_reason"])
            AuditLog.objects.create(
                actor=None,
                action="ghost.entry.purged",
                target_type="members.PublicSearchEntry",
                target_id=str(entry.pk),
                metadata={
                    "first_name": entry.first_name,
                    "last_name_initial": entry.last_name_initial,
                    "added_at": entry.added_at.date().isoformat(),     # YYYY-MM-DD
                    "auto_removed_at": now.date().isoformat(),         # YYYY-MM-DD
                },
            )
            count += 1
        return count

    def _send_quarterly_ghost_digest(self, now) -> int:
        """Once on day 1 of Jan/Apr/Jul/Oct: email staff a digest of every
        ghost.entry.purged AuditLog entry from the last 90 days, plus a
        snapshot of currently-listed entries with their age in months.

        No-op if zero entries were auto-removed in that window.
        """
        since = now - timedelta(days=GHOST_DIGEST_LOOKBACK_DAYS)
        purged = list(
            AuditLog.objects
            .filter(action="ghost.entry.purged", created_at__gte=since)
            .order_by("-created_at")
        )
        if not purged:
            return 0

        # Currently-listed snapshot — entries that are visible publicly
        # right now, with their age in months for runway awareness.
        currently_listed = list(
            PublicSearchEntry.objects
            .filter(removed_at__isnull=True)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=2)
            .order_by("added_at")
        )
        for e in currently_listed:
            e.age_months = round((now - e.added_at).days / 30)  # display helper

        members_emails.send_admin_quarterly_ghost_digest(
            purged_logs=purged,
            currently_listed=currently_listed,
            since=since,
        )
        return len(purged)
```

The `now.day == 1 and now.month in (1, 4, 7, 10)` guard fires the digest exactly once per quarter. A cron flap that skips that day simply skips the digest until next quarter — no critical state lost since each `ghost.entry.purged` AuditLog row is independently durable.

### New email sender

Append to `members/emails.py`:

```python
def send_admin_quarterly_ghost_digest(*, purged_logs, currently_listed, since) -> None:
    """Quarterly FYI to staff: list of ghost entries auto-removed in the
    last 90 days because they were >12 months old without admin renewal,
    plus a snapshot of the currently-listed entries with their age in
    months. No-op if no staff users (mirrors send_admin_removal_notification)."""
    User = get_user_model()  # noqa: N806
    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True)
        .values_list("email", flat=True)
    )
    if not staff_emails:
        return
    send_email(
        staff_emails,
        "members/admin_stale_ghost_digest",
        {
            "logs": purged_logs,
            "currently_listed": currently_listed,
            "since": since,
            "purged_count": len(purged_logs),
            "listed_count": len(currently_listed),
        },
    )
```

### New email template family — 3 files

`members/templates/emails/members/admin_stale_ghost_digest.subject.txt`:
```
[admin] Revue trimestrielle ghost-list — {{ purged_count }} retrait{{ purged_count|pluralize }} automatique{{ purged_count|pluralize }}
```

`members/templates/emails/members/admin_stale_ghost_digest.txt`:
```
Bonjour,

Revue trimestrielle de la liste publique « Nous recherchons aussi… »

== Retraits automatiques (90 derniers jours) ==

{{ purged_count }} fiche{{ purged_count|pluralize }} ont été automatiquement retirées depuis le {{ since|date:"j F Y" }} (publiées depuis plus de 12 mois sans renouvellement par les admins) :

{% for log in logs %}- {{ log.metadata.first_name }} {{ log.metadata.last_name_initial }} (publiée le {{ log.metadata.added_at }}, retirée le {{ log.metadata.auto_removed_at }})
{% endfor %}

== Liste actuelle ({{ listed_count }} fiche{{ listed_count|pluralize }} publiée{{ listed_count|pluralize }}) ==

{% for entry in currently_listed %}- {{ entry.first_name }} {{ entry.last_name_initial }} — publiée il y a {{ entry.age_months }} mois
{% endfor %}

Si l'une des fiches retirées doit être réinscrite, recréez-la dans l'admin Django avec 2 cosignatures, comme à l'origine.

L'équipe Les Retrouvailles
```

`members/templates/emails/members/admin_stale_ghost_digest.html`:
```html
<!DOCTYPE html>
<html lang="fr">
    <body style="font-family: Inter, system-ui, sans-serif; color: #1a1c1e">
        <p>Bonjour,</p>
        <p>Revue trimestrielle de la liste publique « Nous recherchons aussi… »</p>

        <h2 style="font-size: 16px; margin-top: 24px;">
            Retraits automatiques (90 derniers jours)
        </h2>
        <p>
            <strong>{{ purged_count }} fiche{{ purged_count|pluralize }}</strong>
            ont été automatiquement retirées depuis le
            {{ since|date:"j F Y" }} (publiées depuis plus de 12 mois sans
            renouvellement par les admins) :
        </p>
        <ul>
            {% for log in logs %}
                <li>
                    <strong>{{ log.metadata.first_name }} {{ log.metadata.last_name_initial }}</strong>
                    — publiée le {{ log.metadata.added_at }},
                    retirée le {{ log.metadata.auto_removed_at }}
                </li>
            {% endfor %}
        </ul>

        <h2 style="font-size: 16px; margin-top: 24px;">
            Liste actuelle ({{ listed_count }} fiche{{ listed_count|pluralize }} publiée{{ listed_count|pluralize }})
        </h2>
        <ul>
            {% for entry in currently_listed %}
                <li>
                    <strong>{{ entry.first_name }} {{ entry.last_name_initial }}</strong>
                    — publiée il y a {{ entry.age_months }} mois
                </li>
            {% endfor %}
        </ul>

        <p>
            Si l'une des fiches retirées doit être réinscrite, recréez-la
            dans l'admin Django avec 2 cosignatures, comme à l'origine.
        </p>
        <p>L'équipe Les Retrouvailles</p>
    </body>
</html>
```

---

## 3. Admin list filter

Single new `SimpleListFilter` added to `members/admin.py`, wired into `PublicSearchEntryAdmin.list_filter`. Annotates the queryset on the fly only when the filter is selected — default page load is unaffected.

```python
class GhostStatusFilter(admin.SimpleListFilter):
    """Lifecycle status of a PublicSearchEntry, computed from signoff
    count + removed_at + added_at. Lets admins find entries pending
    cosignature, stale ones approaching auto-removal, etc."""

    title = "Statut publication"
    parameter_name = "ghost_status"

    def lookups(self, request, model_admin):
        return [
            ("draft", "Brouillon (0 signatures)"),
            ("pending", "En attente (1 signature)"),
            ("published", "Publiée (2+)"),
            ("stale", "Périmée (>12 mois)"),
            ("removed", "Retirée"),
        ]

    def queryset(self, request, queryset):
        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        value = self.value()
        if value is None:
            return queryset

        if value == "removed":
            return queryset.filter(removed_at__isnull=False)

        qs = queryset.filter(removed_at__isnull=True).annotate(
            n=Count("added_by_admins")
        )
        if value == "draft":
            return qs.filter(n=0)
        if value == "pending":
            return qs.filter(n=1)
        if value == "published":
            return qs.filter(n__gte=2)
        if value == "stale":
            cutoff = timezone.now() - timedelta(days=365)
            return qs.filter(n__gte=2, added_at__lte=cutoff)
        return queryset
```

Wire it on `PublicSearchEntryAdmin`:

```python
# was: list_filter = ("removed_at",)
list_filter = (GhostStatusFilter, "removed_at")
```

That gives the existing `"removed_at"` sidebar date filter (Today / Past 7 days / This month / Any date) AND the new computed status filter side-by-side. Admins keep their existing toolset; the new filter is additive.

**Filter window for "Périmée".** Once the daily cron runs, stale entries get `removed_at` set and leave this bucket. So in steady state, the "Périmée" filter mostly shows entries that became stale today and haven't been swept yet (often empty). Useful as a documented lifecycle stage; admins can confirm the cron is keeping up.

---

## 4. Testing & rollout

### Test budget — ~12 new tests, total suite reaches ~336

**Cron handler tests** (extending `cooptation/tests/test_process_deadlines.py`)

Tests use **freezegun** (already a dev dependency from P3) to manipulate `timezone.now()` for deterministic 12-month boundary checks.

- `test_purge_stale_ghosts_removes_entries_older_than_365_days`: create entry, set `added_at` to 366d ago, ensure 2 cosigners, run cron → `removed_at` is set, `removed_reason == GHOST_STALE_REMOVED_REASON`, AuditLog `ghost.entry.purged` row exists with the right metadata
- `test_purge_stale_ghosts_skips_entries_under_365_days`: entry at 364d → not removed
- `test_purge_stale_ghosts_skips_drafts_with_under_2_signoffs`: entry at 400d but only 1 cosigner → not removed (master spec: "listed" = 2+ sigs)
- `test_purge_stale_ghosts_skips_already_removed_entries`: entry at 400d with `removed_at` already set → not touched (idempotent — re-running the cron doesn't write a second `ghost.entry.purged` log)
- `test_purge_stale_ghosts_audit_metadata_uses_date_strings`: assert `metadata["added_at"]` matches `^\d{4}-\d{2}-\d{2}$` (proves date-only formatting, not full ISO datetime)

**Quarterly digest tests** (same file)

- `test_digest_fires_on_jan_1_when_purges_in_window`: freeze to Jan 1, create + auto-remove an entry, run cron on Jan 1 → digest email sent to all staff. Body contains the entry's name + initial.
- `test_digest_does_not_fire_on_other_days`: freeze to Jan 2 → no digest even with recent purges
- `test_digest_does_not_fire_on_first_of_non_quarterly_months`: freeze to Feb 1, Mar 1, May 1 → no digest. Only Jan/Apr/Jul/Oct day 1 fires.
- `test_digest_no_op_when_no_recent_purges`: freeze to Apr 1 with empty AuditLog → 0 emails sent
- `test_digest_no_op_with_no_staff`: 0 staff users → no crash, 0 emails (mirrors `send_admin_removal_notification` pattern)
- `test_digest_includes_currently_listed_snapshot`: assert the email body lists not just removed entries but also currently-listed ones with their age in months

**Filter test** (new `members/tests/test_admin_filters.py`)

- `test_ghost_status_filter_buckets`: parametrized over `["draft", "pending", "published", "stale", "removed"]` — for each value, create entries fitting the criteria + entries that don't, query the changelist with `?ghost_status=<value>`, assert the right rows appear and the wrong ones don't. ~5 cases as a single parametrized test.

### Rollout sequence

**Pre-deploy**: nothing content-wise. The new email template ships with the code.

**Code rollout** (mirrors P4b):
1. Branch `feat/public-surface-admin` + plan + execute via `superpowers:subagent-driven-development`
2. Open PR; visual changes are zero (new admin filter is sidebar-only, no template work on the public side)
3. Merge to main → Railway auto-deploys

**Post-deploy ops** (~5 min):
1. Verify Railway → Deployments → green
2. **Verify the cron service picks up the new handler.** From PowerShell:
   ```powershell
   railway service     # pick cooptation-cron
   railway run python manage.py process_cooptation_deadlines
   ```
   Expected output line should now read: `Done. reminders=0 expired=0 stale=0 ghosts_purged=0 digest_sent=0 purged=0`
3. **Smoke-test the auto-removal** by creating a stale entry artificially. In Django admin → PublicSearchEntries → create one with 2 cosigners, then via Django shell:
   ```python
   from datetime import timedelta
   from django.utils import timezone
   from members.models import PublicSearchEntry
   e = PublicSearchEntry.objects.get(pk=<id>)
   e.added_at = timezone.now() - timedelta(days=400)
   e.save(update_fields=["added_at"])
   ```
   Then re-run the cron → entry should now have `removed_at` set + `removed_reason == "Périmée — non renouvelée par les admins"` + new `ghost.entry.purged` AuditLog row.
4. **Smoke-test the filter**: open `/admin/members/publicsearchentry/` → confirm the right sidebar shows "Statut publication" with the 5 buckets. Click each → confirm filtering works.
5. **Tag** `v0.4.0c-public-surface-admin`, push, update STATUS.md.

**No flag flip required.** P4c is purely additive — no env var changes, no operator action beyond the deploy.

**No new env vars.** Reuses everything from P4b.

### Rollback plan

Auto-removal is destructive but reversible: every removal writes a `ghost.entry.purged` AuditLog row with the entry's name + initial + dates. To restore an entry that was wrongly auto-removed:
1. Find the AuditLog row with `action="ghost.entry.purged"` and the matching `target_id`
2. Either:
   - Manually unset `removed_at` and `removed_reason` on the entry via Django admin (preserves the original PK, removal_token, cosignature history)
   - Re-create as a fresh entry with 2 new cosignatures (the standard P4a flow)

If the cron itself misfires (e.g., mass-purges everything due to a bug):
1. `git revert <merge-commit>` on `main` → push → Railway redeploys (~3 min)
2. Restore affected entries by clearing `removed_at` in bulk via Django shell, filtering AuditLog for the bad batch's window

### What does NOT change

- P3 cooptation flow: untouched
- P4a landing page: untouched (existing ghost queryset filter `removed_at__isnull=True` automatically excludes auto-removed entries)
- P4b removal flow: untouched (continues to work for human-initiated removals)
- Cron service config: untouched (handler added to existing command)
- Email infrastructure: untouched (one new template family using existing `alumni.email.send_email`)

---

## 5. Risks & accepted tradeoffs

| Risk | Severity | Mitigation |
|------|----------|------------|
| Auto-remove uses `added_at` instead of "first published" date — entries that took weeks to cosign get auto-removed slightly early | Low | Documented in § 1; P4d adds `published_at` if admins find it annoying |
| Day-1-of-quarter digest skipped if cron service is down on that day | Low | Catches up next quarter; AuditLog is durable so no information is lost — only the email is delayed |
| Multiple digest sends if cron is manually triggered on Jan/Apr/Jul/Oct day 1 | Very Low | Operator-induced; document as known limitation |
| Race: admin opens "Périmée" filter while cron is running, sees an entry that gets removed before they click | Very Low | Refresh shows "Retirée" status; no data corruption |
| N+1 query on `signoff_count` admin display column (pre-existing P4a issue) | Low | Out of P4c scope; revisit when changelist becomes slow |
| Spec says "Revue trimestrielle" but auto-remove fires daily | Low | Documented in § 1; the quarterly digest preserves the spec's review cadence; daily auto-remove just removes the human's role from the removal action itself |

---

## 6. Open content questions (not blocking spec, blocking deploy)

None. P4c reuses P4b's email infrastructure and ships first-draft French copy in templates. Email copy can be refined in a follow-up commit if admins want different wording — no schema or behavior changes required.

---

## 7. References

- Master spec § 6.5: `docs/superpowers/specs/2026-05-01-alumni-platform-design.md`
- P4a spec: `docs/superpowers/specs/2026-05-03-public-surface-design.md`
- P4b spec: `docs/superpowers/specs/2026-05-03-public-surface-governance-design.md`
- P4b plan: `docs/superpowers/plans/2026-05-03-public-surface-governance.md`
- Status tracker: `docs/superpowers/STATUS.md`
- Existing cron command: `cooptation/management/commands/process_cooptation_deadlines.py`
- Existing PublicSearchEntryAdmin: `members/admin.py`
