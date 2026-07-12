"""Tests for memoriam email senders."""

from __future__ import annotations

import pytest


@pytest.fixture
def fake_email(settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages = []
    return FakeResendBackend


@pytest.fixture
def fake_cloudinary(settings):
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"


@pytest.mark.django_db
def test_nomination_email_sent_to_admins(fake_email, make_memoriam_nomination, settings):
    from memoriam.emails import send_nomination_received_to_admins

    settings.MEMORIAM_ADMIN_EMAILS = ["admin1@test", "admin2@test"]
    nom = make_memoriam_nomination()
    send_nomination_received_to_admins(nom)
    sent = fake_email.sent_messages
    assert len(sent) == 1
    assert set(sent[0]["to"]) == {"admin1@test", "admin2@test"}
    assert nom.proposed_name in sent[0]["subject"]


@pytest.mark.django_db
def test_publish_email_sent_to_opted_in_active_member(
    fake_email, make_memoriam_entry, authed_member_client
):
    from memoriam.emails import send_fiche_published_to_member

    _client, member = authed_member_client
    # in_memoriam_alerts defaults to True via NotificationPreference auto-create signal.
    assert member.preferences.in_memoriam_alerts is True
    entry = make_memoriam_entry()

    send_fiche_published_to_member(member, entry)
    sent = fake_email.sent_messages
    assert len(sent) == 1
    assert sent[0]["to"] == [member.user.email]
    assert entry.full_name in sent[0]["subject"]


@pytest.mark.django_db
def test_admin_save_model_skips_opted_out_member(
    fake_email, fake_cloudinary, make_admin_user, make_memoriam_entry, authed_member_client
):
    """Full integration: admin transitions draft→published; opted-out
    member must not receive."""
    from django.contrib.admin.sites import AdminSite

    from memoriam.admin import InMemoriamEntryAdmin
    from memoriam.forms import InMemoriamEntryAdminForm
    from memoriam.models import InMemoriamEntry

    _client, member = authed_member_client
    member.preferences.in_memoriam_alerts = False
    member.preferences.save()

    admin = InMemoriamEntryAdmin(InMemoriamEntry, AdminSite())
    user = make_admin_user()
    entry = make_memoriam_entry(status="draft")

    form = InMemoriamEntryAdminForm(
        instance=entry,
        data={
            "full_name": entry.full_name,
            "nickname": "",
            "years_attended": "1980,1981",
            "classes": "6e,5e",
            "tribute": entry.tribute,
            "family_consent_giver": entry.family_consent_giver,
            "family_consent_date": entry.family_consent_date,
            "family_consent_canal": entry.family_consent_canal,
            "status": "published",
        },
    )
    assert form.is_valid(), form.errors

    from django.test import RequestFactory

    rf = RequestFactory()
    req = rf.post("/admin/")
    req.user = user

    admin.save_model(req, entry, form, change=True)
    sent = fake_email.sent_messages
    # Member is opted out → no email.
    assert sent == []


@pytest.mark.django_db
def test_admin_save_model_skips_soft_deleted_member(
    fake_email, fake_cloudinary, make_admin_user, make_memoriam_entry, authed_member_client
):
    from django.contrib.admin.sites import AdminSite

    from memoriam.admin import InMemoriamEntryAdmin
    from memoriam.forms import InMemoriamEntryAdminForm
    from memoriam.models import InMemoriamEntry

    _client, member = authed_member_client
    member.status = "deleted"
    member.save()

    admin = InMemoriamEntryAdmin(InMemoriamEntry, AdminSite())
    user = make_admin_user()
    entry = make_memoriam_entry(status="draft")

    form = InMemoriamEntryAdminForm(
        instance=entry,
        data={
            "full_name": entry.full_name,
            "nickname": "",
            "years_attended": "1980,1981",
            "classes": "6e,5e",
            "tribute": entry.tribute,
            "family_consent_giver": entry.family_consent_giver,
            "family_consent_date": entry.family_consent_date,
            "family_consent_canal": entry.family_consent_canal,
            "status": "published",
        },
    )
    assert form.is_valid(), form.errors

    from django.test import RequestFactory

    rf = RequestFactory()
    req = rf.post("/admin/")
    req.user = user

    admin.save_model(req, entry, form, change=True)
    assert fake_email.sent_messages == []


@pytest.mark.django_db
def test_publish_email_skips_email_less_members_and_sends_after_commit(
    fake_email,
    fake_cloudinary,
    make_admin_user,
    make_memoriam_entry,
    authed_member_client,
    django_capture_on_commit_callbacks,
):
    """~80% of members have no email: they must not produce doomed Resend
    calls, and the fan-out must run after the publish is committed (admin
    wraps save_model in a transaction)."""
    from django.contrib.admin.sites import AdminSite
    from django.contrib.auth import get_user_model
    from django.test import RequestFactory

    from members.models import Member
    from memoriam.admin import InMemoriamEntryAdmin
    from memoriam.forms import InMemoriamEntryAdminForm
    from memoriam.models import InMemoriamEntry

    _client, member_with_email = authed_member_client
    User = get_user_model()  # noqa: N806
    no_mail_user = User.objects.create_user(username="22790000001", email="", password="x")
    Member.objects.create(
        user=no_mail_user,
        first_name="Sans",
        last_name="Email",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
        status="active",
    )

    admin = InMemoriamEntryAdmin(InMemoriamEntry, AdminSite())
    user = make_admin_user()
    entry = make_memoriam_entry(status="draft")

    form = InMemoriamEntryAdminForm(
        instance=entry,
        data={
            "full_name": entry.full_name,
            "nickname": "",
            "years_attended": "1980,1981",
            "classes": "6e,5e",
            "tribute": entry.tribute,
            "family_consent_giver": entry.family_consent_giver,
            "family_consent_date": entry.family_consent_date,
            "family_consent_canal": entry.family_consent_canal,
            "status": "published",
        },
    )
    assert form.is_valid(), form.errors

    req = RequestFactory().post("/admin/")
    req.user = user

    with django_capture_on_commit_callbacks(execute=True):
        admin.save_model(req, entry, form, change=True)

    sent = fake_email.sent_messages
    assert len(sent) == 1
    assert sent[0]["to"] == [member_with_email.user.email]
