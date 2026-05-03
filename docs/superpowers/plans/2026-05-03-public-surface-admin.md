# P4c — Public Surface Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the spec-mandated 12-month auto-remove governance sweep + quarterly admin digest + a 5-bucket admin list filter so the public ghost list never becomes a *cimetière numérique*.

**Architecture:** Two new handler methods added to the existing `process_cooptation_deadlines` daily cron (purely additive — the existing 4 handlers and their cron service are untouched). Daily auto-remove + quarterly digest (Jan/Apr/Jul/Oct day 1). One new email template family + one new sender function. One new `SimpleListFilter` on `PublicSearchEntryAdmin`. No migrations, no schema changes — reuses P4b's `AuditLog.ghost.entry.purged` action and existing `PublicSearchEntry` fields.

**Tech Stack:** Django 5 · pytest + pytest-django + freezegun (already in dev deps) · Postgres · Resend SDK (already wired).

**Spec reference:** `docs/superpowers/specs/2026-05-03-public-surface-admin-design.md`.

---

## File map

**Files to MODIFY:**
- `cooptation/management/commands/process_cooptation_deadlines.py` — add 4 module-level constants, 2 cross-app imports, 2 handler methods (`_purge_stale_ghosts`, `_send_quarterly_ghost_digest`), update `handle()` to call them and extend the output line, update module docstring
- `members/admin.py` — add `GhostStatusFilter` class, wire into `PublicSearchEntryAdmin.list_filter`
- `members/emails.py` — append `send_admin_quarterly_ghost_digest` function
- `cooptation/tests/test_process_deadlines.py` — append ~11 cron handler + digest tests

**Files to CREATE:**
- `members/templates/emails/members/admin_stale_ghost_digest.subject.txt`
- `members/templates/emails/members/admin_stale_ghost_digest.txt`
- `members/templates/emails/members/admin_stale_ghost_digest.html`
- `members/tests/test_admin_filters.py` — 1 parametrized test (5 cases) for `GhostStatusFilter`

**No new migrations.** P4b's `AuditLog.ACTION_CHOICES` already includes `ghost.entry.purged`. `PublicSearchEntry` fields (`added_at`, `removed_at`, `removed_reason`) cover everything needed.

---

## Task 1: Stale-ghost auto-remove handler

**Files:**
- Modify: `cooptation/management/commands/process_cooptation_deadlines.py`
- Modify: `cooptation/tests/test_process_deadlines.py` (append 5 tests)

- [ ] **Step 1: Write the failing tests**

Append to `cooptation/tests/test_process_deadlines.py`:

```python
@pytest.mark.django_db
def test_purge_stale_ghosts_removes_entries_older_than_365_days(make_admin, settings):
    """Published entries (2+ cosigners) with added_at > 365 days ago get
    removed_at set + 'Périmée — non renouvelée par les admins' reason +
    a ghost.entry.purged AuditLog row with date-only metadata."""
    from datetime import timedelta
    from django.utils import timezone
    from freezegun import freeze_time

    from members.models import AuditLog, PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()

    # Create a stale entry by manually backdating added_at
    with freeze_time("2025-04-15"):
        e = PublicSearchEntry.objects.create(
            first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
        )
        e.added_by_admins.add(a, b)

    AuditLog.objects.filter(action="ghost.entry.purged").delete()

    with freeze_time("2026-04-16"):  # 366 days later
        call_command("process_cooptation_deadlines")

    e.refresh_from_db()
    assert e.removed_at is not None
    assert e.removed_reason == "Périmée — non renouvelée par les admins"

    log = AuditLog.objects.get(action="ghost.entry.purged", target_id=str(e.pk))
    assert log.metadata["first_name"] == "Idrissa"
    assert log.metadata["last_name_initial"] == "S."
    # Date-only strings, not full ISO datetimes
    assert log.metadata["added_at"] == "2025-04-15"
    assert log.metadata["auto_removed_at"] == "2026-04-16"


@pytest.mark.django_db
def test_purge_stale_ghosts_skips_entries_under_365_days(make_admin, settings):
    """Entries 364 days old should NOT be auto-removed."""
    from freezegun import freeze_time

    from members.models import AuditLog, PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()

    with freeze_time("2025-04-17"):
        e = PublicSearchEntry.objects.create(
            first_name="X", last_name_initial="X.", years_at_ceg=[1980]
        )
        e.added_by_admins.add(a, b)

    AuditLog.objects.filter(action="ghost.entry.purged").delete()

    with freeze_time("2026-04-16"):  # 364 days later
        call_command("process_cooptation_deadlines")

    e.refresh_from_db()
    assert e.removed_at is None
    assert not AuditLog.objects.filter(
        action="ghost.entry.purged", target_id=str(e.pk)
    ).exists()


@pytest.mark.django_db
def test_purge_stale_ghosts_skips_drafts_with_under_2_signoffs(make_admin, settings):
    """Master spec: 'listed' = 2+ signoffs. Drafts/pending entries are
    not subject to the 12-month sweep."""
    from datetime import timedelta
    from django.utils import timezone
    from freezegun import freeze_time

    from members.models import AuditLog, PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a = make_admin()

    with freeze_time("2025-01-01"):
        e_draft = PublicSearchEntry.objects.create(
            first_name="Draft", last_name_initial="D.", years_at_ceg=[1980]
        )  # 0 cosigners
        e_pending = PublicSearchEntry.objects.create(
            first_name="Pending", last_name_initial="P.", years_at_ceg=[1980]
        )
        e_pending.added_by_admins.add(a)  # 1 cosigner

    AuditLog.objects.filter(action="ghost.entry.purged").delete()

    with freeze_time("2026-04-01"):  # 455 days later
        call_command("process_cooptation_deadlines")

    e_draft.refresh_from_db()
    e_pending.refresh_from_db()
    assert e_draft.removed_at is None
    assert e_pending.removed_at is None
    assert AuditLog.objects.filter(action="ghost.entry.purged").count() == 0


@pytest.mark.django_db
def test_purge_stale_ghosts_skips_already_removed_entries(make_admin, settings):
    """Idempotent: re-running the cron on an already-removed entry does
    NOT write a second ghost.entry.purged AuditLog row."""
    from freezegun import freeze_time

    from members.models import AuditLog, PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()

    with freeze_time("2025-01-01"):
        e = PublicSearchEntry.objects.create(
            first_name="Already", last_name_initial="R.", years_at_ceg=[1980]
        )
        e.added_by_admins.add(a, b)

    # First sweep removes
    with freeze_time("2026-04-01"):
        call_command("process_cooptation_deadlines")
    first_count = AuditLog.objects.filter(
        action="ghost.entry.purged", target_id=str(e.pk)
    ).count()
    assert first_count == 1

    # Second sweep next day: no new audit row
    with freeze_time("2026-04-02"):
        call_command("process_cooptation_deadlines")
    second_count = AuditLog.objects.filter(
        action="ghost.entry.purged", target_id=str(e.pk)
    ).count()
    assert second_count == 1


@pytest.mark.django_db
def test_purge_stale_ghosts_audit_metadata_uses_date_strings(make_admin, settings):
    """Regression: metadata stores YYYY-MM-DD, not full ISO datetimes,
    so the digest template doesn't need to slice."""
    import re
    from freezegun import freeze_time

    from members.models import AuditLog, PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()

    with freeze_time("2025-01-01"):
        e = PublicSearchEntry.objects.create(
            first_name="X", last_name_initial="X.", years_at_ceg=[1980]
        )
        e.added_by_admins.add(a, b)

    with freeze_time("2026-04-01"):
        call_command("process_cooptation_deadlines")

    log = AuditLog.objects.get(action="ghost.entry.purged", target_id=str(e.pk))
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    assert date_re.match(log.metadata["added_at"]), log.metadata["added_at"]
    assert date_re.match(log.metadata["auto_removed_at"]), log.metadata["auto_removed_at"]
```

If `make_admin` isn't available in `cooptation/tests/test_process_deadlines.py`, add this fixture at the top of the file (next to existing fixtures):

```python
@pytest.fixture
def make_admin(db):
    from django.contrib.auth import get_user_model
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
```

- [ ] **Step 2: Run the failing tests**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_process_deadlines.py -k "purge_stale_ghosts" -v 2>&1 | tail -10`

Expected: 5 failures (the handler doesn't exist yet).

- [ ] **Step 3: Update the cron command's docstring + imports + constants**

Open `cooptation/management/commands/process_cooptation_deadlines.py`. Replace the module docstring + imports block at the top with:

```python
"""Daily idempotent cron.

Cooptation handlers (P3): J+7 reminders, J+14 expiry transitions,
stale-questionnaire sweep, 6-month retention purge.

Cross-app housekeeping (P4c): stale-ghost auto-removal, quarterly
admin digest. The 'process_cooptation_deadlines' name is historical;
keeping the existing cron service running this single command is
cheaper than splitting into two services for our scale.

Run via Railway cron service; sharing the app's image and env."""

from __future__ import annotations

import secrets
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from cooptation import emails, services
from cooptation.models import AdminApplication, CooptationRequest

# Cross-app: P4c housekeeping operates on members.PublicSearchEntry.
from members import emails as members_emails
from members.models import AuditLog, PublicSearchEntry

PACING_SECONDS = 0.5
# After both parrains time out and we email the questionnaire link, give the
# candidate this many days to submit it. After that, push the application to
# awaiting_admin so the admin can decide manually instead of letting it rot
# in cooptation_pending forever.
QUESTIONNAIRE_GRACE_DAYS = 7

# P4c: ghost-list governance constants.
GHOST_STALE_THRESHOLD_DAYS = 365
GHOST_DIGEST_LOOKBACK_DAYS = 90
GHOST_DIGEST_QUARTERLY_MONTHS = (1, 4, 7, 10)
GHOST_STALE_REMOVED_REASON = "Périmée — non renouvelée par les admins"
```

- [ ] **Step 4: Update the `handle()` method to call the new handler**

Find the existing `handle()` method (around line 29) and replace it with:

```python
    def handle(self, *args, **opts):
        now = timezone.now()
        sent_reminders = self._send_j7_reminders(now)
        expired_apps = self._expire_j14(now)
        stale_apps = self._sweep_stale_questionnaires(now)
        ghosts_purged = self._purge_stale_ghosts(now)
        digest_sent = 0
        if now.day == 1 and now.month in GHOST_DIGEST_QUARTERLY_MONTHS:
            digest_sent = self._send_quarterly_ghost_digest(now)
        purged_apps = self._purge_old_rejections(now)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. reminders={sent_reminders} expired={expired_apps} "
                f"stale={stale_apps} ghosts_purged={ghosts_purged} "
                f"digest_sent={digest_sent} purged={purged_apps}"
            )
        )
```

- [ ] **Step 5: Add the `_purge_stale_ghosts` method**

Append (before the `_purge_old_rejections` method, near the bottom of the `Command` class):

```python
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
                    "added_at": entry.added_at.date().isoformat(),
                    "auto_removed_at": now.date().isoformat(),
                },
            )
            count += 1
        return count
```

- [ ] **Step 6: Add a stub `_send_quarterly_ghost_digest` to satisfy `handle()`**

Task 2 will fill this in. For now, append a no-op so Task 1's tests pass:

```python
    def _send_quarterly_ghost_digest(self, now) -> int:
        # Filled in by Task 2.
        return 0
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_process_deadlines.py -k "purge_stale_ghosts" -v 2>&1 | tail -15`

Expected: 5 passed.

- [ ] **Step 8: Run the full cooptation test suite to confirm no regression**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_process_deadlines.py -q 2>&1 | tail -3`

Expected: all existing P3/P4b cron tests still pass plus the 5 new P4c ones.

- [ ] **Step 9: Commit**

```bash
git checkout -b feat/public-surface-admin
git add cooptation/management/commands/process_cooptation_deadlines.py cooptation/tests/test_process_deadlines.py
git commit -m "feat(p4c): stale-ghost auto-removal handler in daily cron"
```

---

## Task 2: Quarterly admin digest — handler + email + 3 templates

**Files:**
- Modify: `cooptation/management/commands/process_cooptation_deadlines.py` (replace the stub `_send_quarterly_ghost_digest`)
- Modify: `members/emails.py` (append `send_admin_quarterly_ghost_digest`)
- Create: `members/templates/emails/members/admin_stale_ghost_digest.subject.txt`
- Create: `members/templates/emails/members/admin_stale_ghost_digest.txt`
- Create: `members/templates/emails/members/admin_stale_ghost_digest.html`
- Modify: `cooptation/tests/test_process_deadlines.py` (append 6 digest tests)

- [ ] **Step 1: Write the failing tests**

Append to `cooptation/tests/test_process_deadlines.py`:

```python
@pytest.mark.django_db
def test_digest_fires_on_jan_1_when_purges_in_window(make_admin, settings):
    """On Jan 1 (quarterly trigger), if there's been any auto-removal in
    the last 90 days, email the admin staff a digest."""
    from freezegun import freeze_time

    from alumni.email import FakeResendBackend
    from members.models import PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()  # 2 staff users

    with freeze_time("2025-12-15"):
        e = PublicSearchEntry.objects.create(
            first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
        )
        e.added_by_admins.add(a, b)
        # Backdate added_at via raw save so it's already stale
        PublicSearchEntry.objects.filter(pk=e.pk).update(
            added_at=timezone.now() - timedelta(days=400)
        )

    FakeResendBackend.sent_messages.clear()
    with freeze_time("2026-01-01"):
        call_command("process_cooptation_deadlines")

    # 1 digest email to the 2 staff
    digests = [
        m for m in FakeResendBackend.sent_messages
        if "Revue trimestrielle" in m["subject"]
    ]
    assert len(digests) == 1
    assert sorted(digests[0]["to"]) == sorted([a.email, b.email])
    assert "Idrissa" in digests[0]["text"]
    assert "S." in digests[0]["text"]


@pytest.mark.django_db
def test_digest_does_not_fire_on_other_days(make_admin, settings):
    """Jan 2 must not fire the digest even with recent purges."""
    from freezegun import freeze_time

    from alumni.email import FakeResendBackend
    from members.models import PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()
    with freeze_time("2025-12-15"):
        e = PublicSearchEntry.objects.create(
            first_name="X", last_name_initial="X.", years_at_ceg=[1980]
        )
        e.added_by_admins.add(a, b)
        PublicSearchEntry.objects.filter(pk=e.pk).update(
            added_at=timezone.now() - timedelta(days=400)
        )

    FakeResendBackend.sent_messages.clear()
    with freeze_time("2026-01-02"):
        call_command("process_cooptation_deadlines")

    digests = [
        m for m in FakeResendBackend.sent_messages
        if "Revue trimestrielle" in m["subject"]
    ]
    assert digests == []


@pytest.mark.django_db
def test_digest_does_not_fire_on_first_of_non_quarterly_months(make_admin, settings):
    """Feb 1, Mar 1, May 1 etc. — only Jan/Apr/Jul/Oct day 1 fires the digest."""
    from freezegun import freeze_time

    from alumni.email import FakeResendBackend
    from members.models import PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()
    with freeze_time("2025-12-15"):
        e = PublicSearchEntry.objects.create(
            first_name="X", last_name_initial="X.", years_at_ceg=[1980]
        )
        e.added_by_admins.add(a, b)
        PublicSearchEntry.objects.filter(pk=e.pk).update(
            added_at=timezone.now() - timedelta(days=400)
        )

    for date_str in ("2026-02-01", "2026-03-01", "2026-05-01", "2026-06-01"):
        FakeResendBackend.sent_messages.clear()
        with freeze_time(date_str):
            call_command("process_cooptation_deadlines")
        digests = [
            m for m in FakeResendBackend.sent_messages
            if "Revue trimestrielle" in m["subject"]
        ]
        assert digests == [], f"Digest fired on {date_str}, should not have"


@pytest.mark.django_db
def test_digest_no_op_when_no_recent_purges(make_admin, settings):
    """Apr 1 with empty AuditLog → 0 emails (no spam during quiet quarters)."""
    from freezegun import freeze_time

    from alumni.email import FakeResendBackend
    from members.models import AuditLog

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    make_admin()  # ensure at least 1 staff (so it's not the no-staff branch)
    AuditLog.objects.filter(action="ghost.entry.purged").delete()

    FakeResendBackend.sent_messages.clear()
    with freeze_time("2026-04-01"):
        call_command("process_cooptation_deadlines")

    digests = [
        m for m in FakeResendBackend.sent_messages
        if "Revue trimestrielle" in m["subject"]
    ]
    assert digests == []


@pytest.mark.django_db
def test_digest_no_op_with_no_staff(settings):
    """0 staff users → no crash, no digest sent (mirrors send_admin_removal_notification)."""
    from freezegun import freeze_time

    from alumni.email import FakeResendBackend
    from members.models import AuditLog, PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    # Manually create a purged AuditLog row so the digest would fire if there were staff
    AuditLog.objects.create(
        actor=None,
        action="ghost.entry.purged",
        target_type="members.PublicSearchEntry",
        target_id="999",
        metadata={
            "first_name": "X",
            "last_name_initial": "X.",
            "added_at": "2025-01-01",
            "auto_removed_at": "2026-01-01",
        },
    )

    FakeResendBackend.sent_messages.clear()
    with freeze_time("2026-04-01"):
        call_command("process_cooptation_deadlines")

    digests = [
        m for m in FakeResendBackend.sent_messages
        if "Revue trimestrielle" in m["subject"]
    ]
    assert digests == []  # no staff → no digest


@pytest.mark.django_db
def test_digest_includes_currently_listed_snapshot(make_admin, settings):
    """Beyond the removal log, the digest lists currently-listed entries
    with their age in months so admins see runway."""
    from freezegun import freeze_time

    from alumni.email import FakeResendBackend
    from members.models import PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()

    # 1 stale entry to trigger the digest
    with freeze_time("2025-12-15"):
        e_stale = PublicSearchEntry.objects.create(
            first_name="StaleOne", last_name_initial="S.", years_at_ceg=[1980]
        )
        e_stale.added_by_admins.add(a, b)
        PublicSearchEntry.objects.filter(pk=e_stale.pk).update(
            added_at=timezone.now() - timedelta(days=400)
        )

    # 1 currently-listed entry (4 months old)
    with freeze_time("2025-09-01"):
        e_active = PublicSearchEntry.objects.create(
            first_name="ActiveOne", last_name_initial="A.", years_at_ceg=[1980]
        )
        e_active.added_by_admins.add(a, b)

    FakeResendBackend.sent_messages.clear()
    with freeze_time("2026-01-01"):
        call_command("process_cooptation_deadlines")

    digests = [
        m for m in FakeResendBackend.sent_messages
        if "Revue trimestrielle" in m["subject"]
    ]
    assert len(digests) == 1
    body = digests[0]["text"]
    assert "ActiveOne" in body
    assert "A." in body
    # The age of the active entry is ~4 months from Sep 2025 → Jan 2026
    assert "4 mois" in body or "3 mois" in body or "5 mois" in body
```

- [ ] **Step 2: Run the failing tests**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_process_deadlines.py -k "digest" -v 2>&1 | tail -15`

Expected: 6 failures (the digest handler is a stub; the email sender and templates don't exist).

- [ ] **Step 3: Add `send_admin_quarterly_ghost_digest` to `members/emails.py`**

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

- [ ] **Step 4: Create the 3 email template files**

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

- [ ] **Step 5: Replace the stub `_send_quarterly_ghost_digest` with the real implementation**

In `cooptation/management/commands/process_cooptation_deadlines.py`, find the stub:

```python
    def _send_quarterly_ghost_digest(self, now) -> int:
        # Filled in by Task 2.
        return 0
```

Replace with:

```python
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

        currently_listed = list(
            PublicSearchEntry.objects
            .filter(removed_at__isnull=True)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=2)
            .order_by("added_at")
        )
        for e in currently_listed:
            e.age_months = round((now - e.added_at).days / 30)

        members_emails.send_admin_quarterly_ghost_digest(
            purged_logs=purged,
            currently_listed=currently_listed,
            since=since,
        )
        return len(purged)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_process_deadlines.py -k "digest" -v 2>&1 | tail -20`

Expected: 6 passed.

- [ ] **Step 7: Run the full cooptation test suite + members tests to confirm no regression**

Run: `.venv/Scripts/python.exe -m pytest cooptation/ members/ -q 2>&1 | tail -3`

Expected: all existing tests still pass + 11 new (5 from T1 + 6 from T2).

- [ ] **Step 8: Commit**

```bash
git add cooptation/management/commands/process_cooptation_deadlines.py members/emails.py members/templates/emails/members/ cooptation/tests/test_process_deadlines.py
git commit -m "feat(p4c): quarterly admin digest of ghost-list governance"
```

---

## Task 3: GhostStatusFilter on PublicSearchEntryAdmin

**Files:**
- Modify: `members/admin.py`
- Create: `members/tests/test_admin_filters.py`

- [ ] **Step 1: Write the failing test**

Create `members/tests/test_admin_filters.py`:

```python
"""Tests for the GhostStatusFilter applied to PublicSearchEntryAdmin."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone


@pytest.fixture
def make_admin(db):
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


@pytest.mark.django_db
def test_ghost_status_filter_buckets(client, make_admin):
    """Each filter value returns the right entries and excludes the others.

    Buckets:
      draft     — 0 cosigners, not removed
      pending   — 1 cosigner,  not removed
      published — 2+ cosigners, not removed, < 365 days old
      stale     — 2+ cosigners, not removed, >= 365 days old
      removed   — removed_at is set (regardless of cosigners)
    """
    from members.models import PublicSearchEntry

    admin_user = make_admin()
    a, b, c = make_admin(), make_admin(), make_admin()

    # Force-login the staff user so the admin changelist is reachable.
    client.force_login(admin_user)

    e_draft = PublicSearchEntry.objects.create(
        first_name="Draft", last_name_initial="D.", years_at_ceg=[1980]
    )

    e_pending = PublicSearchEntry.objects.create(
        first_name="Pending", last_name_initial="P.", years_at_ceg=[1980]
    )
    e_pending.added_by_admins.add(a)

    e_published = PublicSearchEntry.objects.create(
        first_name="Published", last_name_initial="B.", years_at_ceg=[1980]
    )
    e_published.added_by_admins.add(a, b)

    e_stale = PublicSearchEntry.objects.create(
        first_name="Stale", last_name_initial="T.", years_at_ceg=[1980]
    )
    e_stale.added_by_admins.add(a, b)
    PublicSearchEntry.objects.filter(pk=e_stale.pk).update(
        added_at=timezone.now() - timedelta(days=400)
    )

    e_removed = PublicSearchEntry.objects.create(
        first_name="Removed", last_name_initial="R.", years_at_ceg=[1980]
    )
    e_removed.added_by_admins.add(a, b, c)
    e_removed.removed_at = timezone.now()
    e_removed.save()

    cases = [
        ("draft", "Draft", ["Pending", "Published", "Stale", "Removed"]),
        ("pending", "Pending", ["Draft", "Published", "Stale", "Removed"]),
        ("published", "Published", ["Draft", "Pending", "Stale", "Removed"]),
        ("stale", "Stale", ["Draft", "Pending", "Published", "Removed"]),
        ("removed", "Removed", ["Draft", "Pending", "Published", "Stale"]),
    ]
    for value, expected_present, expected_absent in cases:
        response = client.get(
            f"/admin/members/publicsearchentry/?ghost_status={value}"
        )
        assert response.status_code == 200, f"GET ?ghost_status={value} failed"
        body = response.content.decode("utf-8")
        assert expected_present in body, (
            f"?ghost_status={value} should include {expected_present}"
        )
        for absent in expected_absent:
            assert absent not in body, (
                f"?ghost_status={value} should NOT include {absent}"
            )
```

- [ ] **Step 2: Run the failing test**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_admin_filters.py -v 2>&1 | tail -10`

Expected: failure (no `?ghost_status` filter handler in the admin yet — Django returns the unfiltered list, so all 5 entries are present and the assertions fail).

- [ ] **Step 3: Add `GhostStatusFilter` to `members/admin.py`**

Find the existing imports at the top of `members/admin.py`. Add `from datetime import timedelta` and `from django.db.models import Count` and `from django.utils import timezone` if any are missing.

Then BEFORE the `@admin.register(PublicSearchEntry)` decorator, add:

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

- [ ] **Step 4: Wire the filter on `PublicSearchEntryAdmin`**

In the same file, find `PublicSearchEntryAdmin.list_filter`:

```python
    list_filter = ("removed_at",)
```

Replace with:

```python
    list_filter = (GhostStatusFilter, "removed_at")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_admin_filters.py -v 2>&1 | tail -10`

Expected: 1 passed.

- [ ] **Step 6: Run the full members suite to confirm no regression**

Run: `.venv/Scripts/python.exe -m pytest members/ -q 2>&1 | tail -3`

Expected: all existing members tests still pass + 1 new.

- [ ] **Step 7: Commit**

```bash
git add members/admin.py members/tests/test_admin_filters.py
git commit -m "feat(p4c): GhostStatusFilter on PublicSearchEntryAdmin (5 buckets)"
```

---

## Task 4: Full suite + STATUS update

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest 2>&1 | tail -3`

Expected: ~336 passed (was 324 before P4c; +12 new across 5 cron tests + 6 digest tests + 1 filter test).

- [ ] **Step 2: Manual local smoke**

```powershell
$env:DJANGO_SETTINGS_MODULE='alumni.settings.dev'; & .\.venv\Scripts\python.exe manage.py process_cooptation_deadlines
```

Expected output: `Done. reminders=0 expired=0 stale=0 ghosts_purged=0 digest_sent=0 purged=0`

- [ ] **Step 3: Update `docs/superpowers/STATUS.md`**

In the Phase Index, find the P4c row:

```markdown
| P4c | Public surface — custom admin governance UI + quarterly review automation | Not started | — |
```

Replace with:

```markdown
| P4c | Public surface — quarterly review automation + admin status filter | Complete (tag `v0.4.0c-public-surface-admin`, 2026-MM-DD) | [plan](plans/2026-05-03-public-surface-admin.md) |
```

Append a new P4c section at the bottom of the file (mirror P4a/P4b format):

```markdown
## P4c — Public surface (quarterly review automation + admin status filter)

**Shipped:** 2026-MM-DD (branch `feat/public-surface-admin`, tag `v0.4.0c-public-surface-admin`)
**Plan:** [plans/2026-05-03-public-surface-admin.md](plans/2026-05-03-public-surface-admin.md)
**Spec:** [specs/2026-05-03-public-surface-admin-design.md](specs/2026-05-03-public-surface-admin-design.md)
**Test suite:** ~336 passing (324 from prior phases + 12 new across cron handler, quarterly digest, and admin filter tests).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Stale-ghost auto-removal handler in daily cron | [x] | _SHA_ |
| 2 | Quarterly admin digest — handler + email + 3 templates | [x] | _SHA_ |
| 3 | GhostStatusFilter on PublicSearchEntryAdmin (5 buckets) | [x] | _SHA_ |
| 4 | Full suite + STATUS update | [x] | _this commit_ |
| 5 | Merge, tag, push, deploy | _next commit_ | _pending_ |

**Notable design decisions:**
- Master spec's "Revue trimestrielle" honored as a **quarterly digest** (Jan/Apr/Jul/Oct day 1) — auto-removal itself fires daily so entries never stay public >12 months + 1 day, but the human-facing review cadence is quarterly.
- 12-month boundary uses `added_at` rather than a "first published" date — slightly conservative for entries that took weeks to cosign, but no schema change. P4d adds `published_at` if admins find it annoying.
- New cron handler lives in the existing `process_cooptation_deadlines` command despite the naming mismatch — the cross-app housekeeping is documented in the module docstring; introducing a second cron service would be cheaper than the current overhead but unnecessary at our scale.
- `GhostStatusFilter` uses `Count("added_by_admins")` annotation only when a filter value is selected; default changelist load is unaffected.
- "Custom admin dashboard view" deferred indefinitely — list filter + quarterly digest cover the operational need at our scale.
```

- [ ] **Step 4: Commit STATUS update**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(p4c): mark Public Surface admin complete in STATUS"
```

---

## Task 5: Merge, tag, push, deploy

**Files:** none

- [ ] **Step 1: Merge to main locally**

```bash
git checkout main
git pull --ff-only
git merge --no-ff feat/public-surface-admin -m "Merge branch 'feat/public-surface-admin' into main

P4c Public Surface Admin — quarterly review automation + admin status filter.

Ships the spec-mandated 12-month auto-remove governance sweep so the
public ghost list never becomes a cimetière numérique. Auto-removal
fires daily; human-facing review cadence is a quarterly admin digest
(Jan/Apr/Jul/Oct day 1) listing the last 90 days of removals plus a
snapshot of currently-listed entries with their age in months.

Adds GhostStatusFilter on PublicSearchEntryAdmin — 5 buckets
(Brouillon / En attente / Publiée / Périmée / Retirée) — so admins
can find entries by lifecycle stage with one click.

No migrations, no schema changes — reuses P4b's AuditLog
ghost.entry.purged action and existing PublicSearchEntry fields.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2: Run full suite on merged main**

`.venv/Scripts/python.exe -m pytest 2>&1 | tail -3`

Expected: same ~336 pass count.

- [ ] **Step 3: Tag and push**

```bash
git tag -a v0.4.0c-public-surface-admin -m "P4c Public Surface — quarterly review automation + admin status filter"
git push origin main --follow-tags
git branch -d feat/public-surface-admin
```

- [ ] **Step 4: Verify Railway redeploys cleanly**

Watch Railway dashboard. Both the app service AND the cooptation-cron service should redeploy automatically (~3 min each). Check Deployments tab on each.

- [ ] **Step 5: Post-deploy verification (~5 min)**

From PowerShell:

```powershell
railway service     # pick cooptation-cron
railway run python manage.py process_cooptation_deadlines
```

Expected output line should now include `ghosts_purged=` and `digest_sent=`:

```
Done. reminders=0 expired=0 stale=0 ghosts_purged=0 digest_sent=0 purged=0
```

If you see the new keys, the cron handler is wired in production.

- [ ] **Step 6: Smoke-test the auto-removal end-to-end**

In Django admin → Members → PublicSearchEntries → create a test entry (`first_name="StaleSmoke"`, `last_name_initial="T."`, `years_at_ceg=[1980]`). Add 2 cosigners.

Then in Railway shell:

```powershell
railway ssh
# pick app service
python manage.py shell
```

In the shell:
```python
from datetime import timedelta
from django.utils import timezone
from members.models import PublicSearchEntry
e = PublicSearchEntry.objects.get(first_name="StaleSmoke")
e.added_at = timezone.now() - timedelta(days=400)
e.save(update_fields=["added_at"])
print("Backdated to", e.added_at)
```

Exit the shell, then run the cron once:
```powershell
railway run --service cooptation-cron python manage.py process_cooptation_deadlines
```

Expected output: `ghosts_purged=1 digest_sent=0` (digest only fires on quarterly day 1).

Verify in Django admin: the entry now has `removed_at` set, `removed_reason="Périmée — non renouvelée par les admins"`, and there's a new AuditLog row with `action="ghost.entry.purged"`.

- [ ] **Step 7: Smoke-test the filter**

Open `https://villageretrouvailles.com/admin/members/publicsearchentry/`. The right sidebar should now show "Statut publication" with 5 clickable values. Click each and verify the changelist filters correctly.

- [ ] **Step 8: Clean up the test entry**

Delete the "StaleSmoke" entry from Django admin (or leave it as a documented test artifact — your call).

---

## Done

P4c Public Surface Admin is shipped. The public ghost list now has automated 12-month hygiene, admins get a quarterly digest of governance activity, and the admin changelist has a one-click status filter.

Next phase per `docs/superpowers/STATUS.md`: P5 — Mémoire seed (`Memory` model, Mur des souvenirs admin-only gallery, `InMemoriamEntry`, In Memoriam seed page).
