"""Tests for PublicSearchEntryAdmin.save_model — auto-cosign creator and
fire admin_ghost_added notification (P4d)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


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
def test_admin_save_auto_adds_creator_to_signoffs(fake_backend, make_admin):
    """When an admin creates a PublicSearchEntry through the admin form,
    they are automatically added to added_by_admins — no manual checkbox
    required."""
    from members.models import PublicSearchEntry

    creator = make_admin()
    make_admin()  # second admin so the email has a recipient

    client = Client()
    client.force_login(creator)

    response = client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Idrissa",
            "last_name_initial": "S.",
            "years_at_ceg": "1980,1981,1982,1983",
            "note": "",
        },
    )
    assert response.status_code in (302, 200), (
        f"got {response.status_code}, body={response.content[:500]}"
    )

    entry = PublicSearchEntry.objects.get(first_name="Idrissa")
    assert creator in entry.added_by_admins.all()


@pytest.mark.django_db
def test_admin_save_does_not_re_add_creator_on_edit(fake_backend, make_admin):
    """Re-saving an existing entry doesn't re-fire the auto-add logic."""
    from members.models import PublicSearchEntry

    creator = make_admin()
    make_admin()  # second admin so first save's email has a recipient

    client = Client()
    client.force_login(creator)

    # Create
    client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Hamidou",
            "last_name_initial": "A.",
            "years_at_ceg": "1981,1982",
            "note": "",
        },
    )
    entry = PublicSearchEntry.objects.get(first_name="Hamidou")
    initial_count = entry.added_by_admins.count()

    # Edit (changes nothing material, just re-saves)
    client.post(
        f"/admin/members/publicsearchentry/{entry.pk}/change/",
        {
            "first_name": "Hamidou",
            "last_name_initial": "A.",
            "years_at_ceg": "1981,1982",
            "note": "Updated note",
            "added_by_admins": [creator.pk],
        },
    )
    entry.refresh_from_db()
    assert entry.added_by_admins.count() == initial_count


@pytest.mark.django_db
def test_admin_save_fires_notification_email_on_create(fake_backend, make_admin):
    """Creating a new entry through the admin fires the admin_ghost_added
    email to other staff — but not to the creator themselves."""
    from members.models import PublicSearchEntry  # noqa: F401

    creator = make_admin()
    other = make_admin()

    client = Client()
    client.force_login(creator)

    client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Aïssa",
            "last_name_initial": "D.",
            "years_at_ceg": "1982,1983",
            "note": "",
        },
    )
    assert len(fake_backend.sent_messages) == 1
    msg = fake_backend.sent_messages[0]
    assert other.email in msg["to"]
    assert creator.email not in msg["to"]
    assert "Aïssa" in msg["subject"]


@pytest.mark.django_db
def test_admin_save_does_not_fire_email_on_edit(fake_backend, make_admin):
    """Re-saving an existing entry doesn't fire a duplicate notification."""
    from members.models import PublicSearchEntry

    creator = make_admin()
    make_admin()

    client = Client()
    client.force_login(creator)

    client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Aïcha",
            "last_name_initial": "B.",
            "years_at_ceg": "1980",
            "note": "",
        },
    )
    fake_backend.sent_messages.clear()

    entry = PublicSearchEntry.objects.get(first_name="Aïcha")
    client.post(
        f"/admin/members/publicsearchentry/{entry.pk}/change/",
        {
            "first_name": "Aïcha",
            "last_name_initial": "B.",
            "years_at_ceg": "1980,1981",
            "note": "",
            "added_by_admins": [creator.pk],
        },
    )
    assert len(fake_backend.sent_messages) == 0
