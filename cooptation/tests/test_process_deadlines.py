from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone


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


@pytest.mark.django_db
def test_j7_reminder_sends_once(make_cooptation_request, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    req = make_cooptation_request(
        expires_at=timezone.now() + timedelta(days=7) - timedelta(hours=1),
    )
    FakeResendBackend.sent_messages.clear()

    call_command("process_cooptation_deadlines")
    req.refresh_from_db()
    assert req.reminder_sent_at is not None
    assert len(FakeResendBackend.sent_messages) == 1

    # Re-run is idempotent — no second reminder
    FakeResendBackend.sent_messages.clear()
    call_command("process_cooptation_deadlines")
    assert len(FakeResendBackend.sent_messages) == 0


@pytest.mark.django_db
def test_j14_expiry_transitions_application(make_cooptation_request, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"

    req = make_cooptation_request(expires_at=timezone.now() - timedelta(hours=1))
    app = req.application

    call_command("process_cooptation_deadlines")
    app.refresh_from_db()
    assert app.cooptation_outcome == "expired"
    assert app.questionnaire_token  # auto-generated for the fallback


@pytest.mark.django_db
def test_retention_purge_runs_after_six_months(make_application, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from datetime import timedelta as td

    app = make_application(
        full_name="Should Be Purged",
        email="purge@example.test",
        status="rejected",
    )
    app.rejected_at = timezone.now() - td(days=200)
    app.retention_until = timezone.now() - td(days=20)
    app.save()

    call_command("process_cooptation_deadlines")
    app.refresh_from_db()
    assert app.status == "purged"
    assert app.full_name == ""
    assert app.email == ""


@pytest.mark.django_db
def test_j14_expiry_email_not_resent_on_subsequent_runs(make_cooptation_request, settings):
    """Regression: once we've sent the cooptation_expired email and stamped
    cooptation_expired_at, the next cron run must not re-send it."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    req = make_cooptation_request(expires_at=timezone.now() - timedelta(hours=1))
    app = req.application
    FakeResendBackend.sent_messages.clear()

    call_command("process_cooptation_deadlines")
    app.refresh_from_db()
    assert app.cooptation_expired_at is not None
    first_run_emails = sum(1 for m in FakeResendBackend.sent_messages if m["to"] == [app.email])
    assert first_run_emails == 1

    FakeResendBackend.sent_messages.clear()
    call_command("process_cooptation_deadlines")
    second_run_emails = sum(1 for m in FakeResendBackend.sent_messages if m["to"] == [app.email])
    assert second_run_emails == 0


@pytest.mark.django_db
def test_stale_questionnaire_pushed_to_admin_after_grace(make_cooptation_request, settings):
    """Regression: a candidate who never submits the questionnaire must not
    sit in cooptation_pending forever. After the grace window the cron pushes
    the application to awaiting_admin so the admin sees something actionable."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"

    req = make_cooptation_request(expires_at=timezone.now() - timedelta(hours=1))
    app = req.application

    # First run: emit the questionnaire link.
    call_command("process_cooptation_deadlines")
    app.refresh_from_db()
    assert app.status == "cooptation_pending"
    assert app.cooptation_outcome == "expired"

    # Backdate the expired stamp to simulate the grace window having passed.
    app.cooptation_expired_at = timezone.now() - timedelta(days=8)
    app.save()

    call_command("process_cooptation_deadlines")
    app.refresh_from_db()
    assert app.status == "awaiting_admin"
    assert app.cooptation_outcome == "expired"


@pytest.mark.django_db
def test_stale_sweep_skips_when_questionnaire_submitted(make_cooptation_request, settings, db):
    """Submitting the questionnaire keeps the app in cooptation_pending until
    the questionnaire view itself transitions it; the stale sweep must not
    pre-empt that path."""
    from cooptation.models import KnowledgeQuestion, QuestionnaireResponse

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"

    req = make_cooptation_request(expires_at=timezone.now() - timedelta(hours=1))
    app = req.application

    call_command("process_cooptation_deadlines")
    app.refresh_from_db()

    # Candidate submitted at least one answer → no longer "stale".
    q = KnowledgeQuestion.objects.create(
        position=1, kind="closed", text="Q?", answer_keys=["a"], is_active=True
    )
    QuestionnaireResponse.objects.create(application=app, question=q, candidate_answer="a")

    app.cooptation_expired_at = timezone.now() - timedelta(days=8)
    app.save()

    call_command("process_cooptation_deadlines")
    app.refresh_from_db()
    assert app.status == "cooptation_pending"


@pytest.mark.django_db
def test_email_pacing_sleeps_between_sends(make_cooptation_request, settings, monkeypatch):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    sleeps = []
    import time as time_mod

    monkeypatch.setattr(time_mod, "sleep", lambda s: sleeps.append(s))

    # Two reminders firing in one run
    make_cooptation_request(expires_at=timezone.now() + timedelta(days=7) - timedelta(hours=1))
    make_cooptation_request(expires_at=timezone.now() + timedelta(days=7) - timedelta(hours=1))

    call_command("process_cooptation_deadlines")
    # At least 1 sleep call between sends
    assert any(s == 0.5 for s in sleeps)


@pytest.mark.django_db
def test_purge_stale_ghosts_removes_entries_older_than_365_days(make_admin, settings):
    """Published entries (2+ cosigners) with added_at > 365 days ago get
    removed_at set + 'Périmée — non renouvelée par les admins' reason +
    a ghost.entry.purged AuditLog row with date-only metadata."""
    from freezegun import freeze_time

    from members.models import AuditLog, PublicSearchEntry

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    a, b = make_admin(), make_admin()

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
    assert not AuditLog.objects.filter(action="ghost.entry.purged", target_id=str(e.pk)).exists()


@pytest.mark.django_db
def test_purge_stale_ghosts_skips_drafts_with_under_2_signoffs(make_admin, settings):
    """Master spec: 'listed' = 2+ signoffs. Drafts/pending entries are
    not subject to the 12-month sweep."""
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

    with freeze_time("2026-04-01"):
        call_command("process_cooptation_deadlines")
    first_count = AuditLog.objects.filter(action="ghost.entry.purged", target_id=str(e.pk)).count()
    assert first_count == 1

    with freeze_time("2026-04-02"):
        call_command("process_cooptation_deadlines")
    second_count = AuditLog.objects.filter(action="ghost.entry.purged", target_id=str(e.pk)).count()
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

    digests = [m for m in FakeResendBackend.sent_messages if "Revue trimestrielle" in m["subject"]]
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

    digests = [m for m in FakeResendBackend.sent_messages if "Revue trimestrielle" in m["subject"]]
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
            m for m in FakeResendBackend.sent_messages if "Revue trimestrielle" in m["subject"]
        ]
        assert digests == [], f"Digest fired on {date_str}, should not have"


@pytest.mark.django_db
def test_digest_no_op_when_no_recent_purges(make_admin, settings):
    """Apr 1 with empty AuditLog → 0 emails (no spam during quiet quarters)."""
    from freezegun import freeze_time

    from alumni.email import FakeResendBackend
    from members.models import AuditLog

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    make_admin()  # ensure at least 1 staff
    AuditLog.objects.filter(action="ghost.entry.purged").delete()

    FakeResendBackend.sent_messages.clear()
    with freeze_time("2026-04-01"):
        call_command("process_cooptation_deadlines")

    digests = [m for m in FakeResendBackend.sent_messages if "Revue trimestrielle" in m["subject"]]
    assert digests == []


@pytest.mark.django_db
def test_digest_no_op_with_no_staff(settings):
    """0 staff users → no crash, no digest sent (mirrors send_admin_removal_notification)."""
    from freezegun import freeze_time

    from alumni.email import FakeResendBackend
    from members.models import AuditLog

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
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

    digests = [m for m in FakeResendBackend.sent_messages if "Revue trimestrielle" in m["subject"]]
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

    digests = [m for m in FakeResendBackend.sent_messages if "Revue trimestrielle" in m["subject"]]
    assert len(digests) == 1
    body = digests[0]["text"]
    assert "ActiveOne" in body
    assert "A." in body
    # Age in months from Sep 2025 → Jan 2026 should be ~4 months (allow 3-5 for rounding)
    assert "4 mois" in body or "3 mois" in body or "5 mois" in body
