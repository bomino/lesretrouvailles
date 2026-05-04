"""Tests for the admin_ghost_added FYI email (P4d)."""

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
def test_notification_sent_to_other_staff_on_entry_create(fake_backend, make_admin):
    from members.emails import send_admin_ghost_added
    from members.models import PublicSearchEntry

    creator = make_admin()
    other_admin = make_admin()

    entry = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    send_admin_ghost_added(entry, added_by=creator)

    assert len(fake_backend.sent_messages) == 1
    msg = fake_backend.sent_messages[0]
    assert other_admin.email in msg["to"]
    assert "Idrissa" in msg["subject"]
    assert "Idrissa" in msg["text"]
    assert "S." in msg["text"]


@pytest.mark.django_db
def test_notification_excludes_creator_from_recipients(fake_backend, make_admin):
    from members.emails import send_admin_ghost_added
    from members.models import PublicSearchEntry

    creator = make_admin()
    other_admin = make_admin()

    entry = PublicSearchEntry.objects.create(
        first_name="Hamidou", last_name_initial="A.", years_at_ceg=[1981, 1982]
    )
    send_admin_ghost_added(entry, added_by=creator)

    msg = fake_backend.sent_messages[0]
    assert creator.email not in msg["to"]
    assert other_admin.email in msg["to"]


@pytest.mark.django_db
def test_notification_no_op_when_no_other_staff(fake_backend, make_admin):
    """If the creator is the only staff user, send no email (and no error)."""
    from members.emails import send_admin_ghost_added
    from members.models import PublicSearchEntry

    creator = make_admin()  # Only staff user

    entry = PublicSearchEntry.objects.create(
        first_name="Solo", last_name_initial="X.", years_at_ceg=[1980]
    )
    send_admin_ghost_added(entry, added_by=creator)

    assert len(fake_backend.sent_messages) == 0
