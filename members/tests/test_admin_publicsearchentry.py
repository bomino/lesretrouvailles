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
    assert response.status_code == 302, (
        f"expected 302 (redirect after save), got {response.status_code},"
        f" body={response.content[:500]}"
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


@pytest.mark.django_db
def test_ghost_added_email_failure_does_not_break_entry_creation(
    fake_backend, make_admin, monkeypatch
):
    """The FYI email is best-effort: a Resend outage during the admin create
    must not roll back the entry or 500 the changeform."""
    from members import admin as members_admin
    from members.models import PublicSearchEntry

    creator = make_admin()
    make_admin()  # second admin so a recipient exists

    def _boom(*args, **kwargs):
        raise RuntimeError("resend down")

    monkeypatch.setattr(members_admin, "send_admin_ghost_added", _boom)

    client = Client()
    client.force_login(creator)
    response = client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Aissa",
            "last_name_initial": "K.",
            "years_at_ceg": "1980,1981",
            "note": "",
        },
    )
    assert response.status_code == 302
    assert PublicSearchEntry.objects.filter(first_name="Aissa").exists()


@pytest.mark.django_db
def test_removal_request_status_is_readonly_in_admin(make_admin):
    """Flipping status by hand either lies about a removal that never
    happened, or skips the pre_delete audit hook that records a cancelled
    pending request."""
    from django.contrib.admin.sites import AdminSite

    from members.admin import RemovalRequestAdmin
    from members.models import RemovalRequest

    admin_obj = RemovalRequestAdmin(RemovalRequest, AdminSite())
    assert "status" in admin_obj.readonly_fields
