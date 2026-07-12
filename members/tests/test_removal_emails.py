"""Tests that the 3 P4b email templates render and contain the right data."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def fake_backend(settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.DEFAULT_FROM_EMAIL = "smoke@example.test"
    settings.SITE_URL = "https://prod.example.test"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    return FakeResendBackend


@pytest.fixture
def removal_request(db):
    from members.models import PublicSearchEntry, RemovalRequest

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa",
        last_name_initial="S.",
        years_at_ceg=[1980, 1981, 1982, 1983],
    )
    return RemovalRequest.objects.create(
        entry=e,
        requester_email="candidate@example.test",
        reason="Je veux disparaître",
    )


@pytest.mark.django_db
def test_removal_confirmation_pending_contains_confirm_url(fake_backend, removal_request):
    from members.emails import send_removal_confirmation_pending

    send_removal_confirmation_pending(removal_request)
    msg = fake_backend.sent_messages[0]
    assert msg["to"] == ["candidate@example.test"]
    expected_url = f"https://prod.example.test/retrait/confirme/{removal_request.confirm_token}/"
    assert expected_url in msg["text"]
    assert "Idrissa" in msg["text"]
    assert "S." in msg["text"]


@pytest.mark.django_db
def test_removal_completed_acknowledges_entry(fake_backend, removal_request):
    from members.emails import send_removal_completed

    send_removal_completed(removal_request)
    msg = fake_backend.sent_messages[0]
    assert msg["to"] == ["candidate@example.test"]
    assert "Idrissa" in msg["text"]
    assert "S." in msg["text"]


@pytest.mark.django_db
def test_admin_removal_notification_to_all_staff(fake_backend, removal_request):
    User = get_user_model()  # noqa: N806
    User.objects.create_user(
        username="staff1", email="staff1@example.test", password="x", is_staff=True
    )
    User.objects.create_user(
        username="staff2", email="staff2@example.test", password="x", is_staff=True
    )
    User.objects.create_user(
        username="user1", email="user1@example.test", password="x"
    )  # not staff

    from members.emails import send_admin_removal_notification

    send_admin_removal_notification(removal_request)
    msg = fake_backend.sent_messages[0]
    assert sorted(msg["to"]) == ["staff1@example.test", "staff2@example.test"]


@pytest.mark.django_db
def test_admin_removal_notification_no_op_with_no_staff(fake_backend, removal_request):
    """No staff users → don't send (and don't crash)."""
    from members.emails import send_admin_removal_notification

    send_admin_removal_notification(removal_request)
    assert len(fake_backend.sent_messages) == 0


@pytest.mark.django_db
def test_all_three_templates_use_french(fake_backend, removal_request):
    User = get_user_model()  # noqa: N806
    User.objects.create_user(
        username="staff", email="staff@example.test", password="x", is_staff=True
    )
    from members.emails import (
        send_admin_removal_notification,
        send_removal_completed,
        send_removal_confirmation_pending,
    )

    send_removal_confirmation_pending(removal_request)
    send_removal_completed(removal_request)
    send_admin_removal_notification(removal_request)
    french_markers = ["bonjour", "votre", "retrait", "demande", "merci", "équipe"]
    for m in fake_backend.sent_messages:
        body = m["text"].lower()
        assert any(marker in body for marker in french_markers), m["subject"]


@pytest.mark.django_db
def test_admin_removal_notification_filters_blank_staff_emails(fake_backend, removal_request):
    """~80% of this platform's users (including plausible co-admins) have no
    email. A blank string in the Resend 'to' list fails the API call every
    time, 500ing the removal-confirm view AFTER the removal committed and
    silencing the only admin tripwire on the public removal flow."""
    from members.emails import send_admin_removal_notification

    User = get_user_model()  # noqa: N806
    User.objects.create_user(username="22790000001", email="", password="x", is_staff=True)
    User.objects.create_user(
        username="coadmin@example.test", email="coadmin@example.test", password="x", is_staff=True
    )

    send_admin_removal_notification(removal_request)
    assert len(fake_backend.sent_messages) == 1
    assert fake_backend.sent_messages[0]["to"] == ["coadmin@example.test"]


@pytest.mark.django_db
def test_admin_removal_notification_noop_when_only_blank_email_staff(fake_backend, removal_request):
    from members.emails import send_admin_removal_notification

    User = get_user_model()  # noqa: N806
    User.objects.create_user(username="22790000001", email="", password="x", is_staff=True)

    send_admin_removal_notification(removal_request)
    assert fake_backend.sent_messages == []


@pytest.mark.django_db
def test_quarterly_ghost_digest_filters_blank_staff_emails(fake_backend):
    from django.utils import timezone

    from members.emails import send_admin_quarterly_ghost_digest

    User = get_user_model()  # noqa: N806
    User.objects.create_user(username="22790000002", email="", password="x", is_staff=True)
    User.objects.create_user(
        username="digest@example.test", email="digest@example.test", password="x", is_staff=True
    )

    send_admin_quarterly_ghost_digest(purged_logs=[], currently_listed=[], since=timezone.now())
    assert len(fake_backend.sent_messages) == 1
    assert fake_backend.sent_messages[0]["to"] == ["digest@example.test"]
