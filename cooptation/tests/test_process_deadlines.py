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
