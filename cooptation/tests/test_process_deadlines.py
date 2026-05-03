from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone


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
