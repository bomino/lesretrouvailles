"""Tests for the smoke_test_cooptation management command.

The command sends real emails in production (via Resend); tests intercept
them with the FakeResendBackend and assert the pipeline reached approve
without raising.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command


@pytest.fixture
def staff_user(db):
    User = get_user_model()  # noqa: N806
    return User.objects.create_user(
        username="smoke-staff@example.test",
        email="smoke-staff@example.test",
        password="x",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def fake_backend(settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.DEFAULT_FROM_EMAIL = "smoke@example.test"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    return FakeResendBackend


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Pacing sleeps exist for production rate-limit reasons; in tests they
    just slow the suite. Patch them out at the module the command imports."""
    import cooptation.management.commands.smoke_test_cooptation as cmd

    monkeypatch.setattr(cmd.time, "sleep", lambda *_: None)


@pytest.mark.django_db
def test_command_runs_full_pipeline_and_cleans_up(staff_user, fake_backend):
    from cooptation.models import AdminApplication
    from members.models import Member

    out = StringIO()
    call_command(
        "smoke_test_cooptation",
        candidate_email="smoke-candidate@example.test",
        stdout=out,
    )
    output = out.getvalue()

    # Step markers all appear.
    for marker in ("[1/6]", "[2/6]", "[3/6]", "[4/6]", "[5/6]", "[6/6]"):
        assert marker in output

    # Cleanup ran — no smoke-test data left in the DB.
    User = get_user_model()  # noqa: N806
    assert not User.objects.filter(email="smoke-test-parrain1@example.test").exists()
    assert not User.objects.filter(email="smoke-test-parrain2@example.test").exists()
    assert not User.objects.filter(email="smoke-candidate@example.test").exists()
    assert not AdminApplication.objects.filter(email="smoke-candidate@example.test").exists()
    assert not Member.objects.filter(first_name__startswith="SmokeParrain").exists()


@pytest.mark.django_db
def test_command_keep_flag_preserves_records(staff_user, fake_backend):
    from cooptation.models import AdminApplication

    out = StringIO()
    call_command(
        "smoke_test_cooptation",
        candidate_email="smoke-candidate@example.test",
        keep=True,
        stdout=out,
    )

    # With --keep, the candidate user, member, and application persist.
    User = get_user_model()  # noqa: N806
    assert User.objects.filter(email="smoke-candidate@example.test").exists()
    assert AdminApplication.objects.filter(email="smoke-candidate@example.test").exists()


@pytest.mark.django_db
def test_command_is_idempotent_across_runs(staff_user, fake_backend):
    """Running twice with the same email does not error — the pre-flight
    cleanup wipes prior smoke data before the new run starts."""
    out = StringIO()
    call_command(
        "smoke_test_cooptation", candidate_email="smoke-candidate@example.test", stdout=out
    )
    out2 = StringIO()
    call_command(
        "smoke_test_cooptation", candidate_email="smoke-candidate@example.test", stdout=out2
    )
    assert "[6/6]" in out2.getvalue()


@pytest.mark.django_db
def test_command_sends_expected_emails(staff_user, fake_backend):
    out = StringIO()
    call_command(
        "smoke_test_cooptation",
        candidate_email="smoke-candidate@example.test",
        keep=True,
        stdout=out,
    )

    # Build a flat list of (recipient, subject) pairs across all sent messages.
    sent_to = [(tuple(m["to"]), m["subject"]) for m in fake_backend.sent_messages]

    # Candidate inbox should receive 4 (received, requests_sent, 2x accepted) + approved = 5
    candidate_msgs = [s for to, s in sent_to if to == ("smoke-candidate@example.test",)]
    assert len(candidate_msgs) >= 3, (
        f"Expected at least 3 candidate emails, got {len(candidate_msgs)}: {candidate_msgs}"
    )

    # Approved email must include the password-set link (validates the C1 fix
    # path: the URL is built before the email is rendered).
    approved = next(
        (m for m in fake_backend.sent_messages if "/accounts/password/reset/key/" in m["text"]),
        None,
    )
    assert approved is not None, "No application_approved email with password-set URL found"


@pytest.mark.django_db
def test_command_errors_when_no_staff_user_exists(fake_backend):
    with pytest.raises(CommandError, match="No staff users exist"):
        call_command("smoke_test_cooptation", candidate_email="smoke-candidate@example.test")


@pytest.mark.django_db
def test_command_errors_when_admin_email_unknown(staff_user, fake_backend):
    with pytest.raises(CommandError, match="No staff user with email"):
        call_command(
            "smoke_test_cooptation",
            candidate_email="smoke-candidate@example.test",
            admin_email="nobody@example.test",
        )
