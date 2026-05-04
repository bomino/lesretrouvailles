"""Tests for memoriam.admin — save_model behavior."""

from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory


def _admin_request(user):
    rf = RequestFactory()
    req = rf.post("/admin/")
    req.user = user
    return req


@pytest.fixture
def fake_cloudinary(settings):
    from alumni.cloudinary import reset_fake_client

    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    reset_fake_client()


@pytest.mark.django_db
def test_save_model_uploads_photo_and_stores_public_id(
    fake_cloudinary, make_admin_user, make_memoriam_entry
):
    from memoriam.admin import InMemoriamEntryAdmin
    from memoriam.forms import InMemoriamEntryAdminForm
    from memoriam.models import InMemoriamEntry

    admin = InMemoriamEntryAdmin(InMemoriamEntry, AdminSite())
    user = make_admin_user()
    entry = make_memoriam_entry()

    upload = SimpleUploadedFile("photo.jpg", b"fakebytes", content_type="image/jpeg")
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
            "status": entry.status,
        },
        files={"upload": upload},
    )
    assert form.is_valid(), form.errors

    admin.save_model(_admin_request(user), entry, form, change=True)
    entry.refresh_from_db()
    assert entry.photo_public_id.startswith("memoriam/fake-")


@pytest.mark.django_db
def test_save_model_deletes_old_public_id_on_replacement(
    fake_cloudinary, make_admin_user, make_memoriam_entry
):
    from alumni.cloudinary import get_client
    from memoriam.admin import InMemoriamEntryAdmin
    from memoriam.forms import InMemoriamEntryAdminForm
    from memoriam.models import InMemoriamEntry

    admin = InMemoriamEntryAdmin(InMemoriamEntry, AdminSite())
    user = make_admin_user()
    entry = make_memoriam_entry(photo_public_id="memoriam/old-id")

    upload = SimpleUploadedFile("new.jpg", b"newbytes", content_type="image/jpeg")
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
            "status": entry.status,
        },
        files={"upload": upload},
    )
    assert form.is_valid(), form.errors
    admin.save_model(_admin_request(user), entry, form, change=True)

    client = get_client()
    assert "memoriam/old-id" in client.delete_calls


@pytest.mark.django_db
def test_save_model_bumps_version_on_text_change(
    fake_cloudinary, make_admin_user, make_memoriam_entry
):
    from memoriam.admin import InMemoriamEntryAdmin
    from memoriam.forms import InMemoriamEntryAdminForm
    from memoriam.models import InMemoriamEntry

    admin = InMemoriamEntryAdmin(InMemoriamEntry, AdminSite())
    user = make_admin_user()
    entry = make_memoriam_entry(approved_content_version=3)

    form = InMemoriamEntryAdminForm(
        instance=entry,
        data={
            "full_name": entry.full_name,
            "nickname": "",
            "years_attended": "1980,1981",
            "classes": "6e,5e",
            "tribute": "DIFFERENT TRIBUTE TEXT",
            "family_consent_giver": entry.family_consent_giver,
            "family_consent_date": entry.family_consent_date,
            "family_consent_canal": entry.family_consent_canal,
            "status": entry.status,
        },
    )
    assert form.is_valid(), form.errors

    admin.save_model(_admin_request(user), entry, form, change=True)
    entry.refresh_from_db()
    assert entry.approved_content_version == 4


@pytest.mark.skip(reason="emails module added in task 9; un-skip there")
@pytest.mark.django_db
def test_save_model_sets_published_at_on_first_publish(
    fake_cloudinary, make_admin_user, make_memoriam_entry
):
    from memoriam.admin import InMemoriamEntryAdmin
    from memoriam.forms import InMemoriamEntryAdminForm
    from memoriam.models import InMemoriamEntry

    admin = InMemoriamEntryAdmin(InMemoriamEntry, AdminSite())
    user = make_admin_user()
    entry = make_memoriam_entry(status="draft")
    assert entry.published_at is None

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

    admin.save_model(_admin_request(user), entry, form, change=True)
    entry.refresh_from_db()
    assert entry.status == "published"
    assert entry.published_at is not None


@pytest.mark.django_db
def test_save_model_autostamps_created_by_on_new(fake_cloudinary, make_admin_user):
    from memoriam.admin import InMemoriamEntryAdmin
    from memoriam.forms import InMemoriamEntryAdminForm
    from memoriam.models import InMemoriamEntry

    admin = InMemoriamEntryAdmin(InMemoriamEntry, AdminSite())
    user = make_admin_user()

    upload = SimpleUploadedFile("p.jpg", b"x", content_type="image/jpeg")
    form = InMemoriamEntryAdminForm(
        data={
            "full_name": "Mariama Diallo",
            "nickname": "",
            "years_attended": "1980",
            "classes": "6e",
            "tribute": "Hommage.",
            "family_consent_giver": "Sa fille",
            "family_consent_date": "2026-01-01",
            "family_consent_canal": "whatsapp",
            "status": "draft",
        },
        files={"upload": upload},
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    admin.save_model(_admin_request(user), obj, form, change=False)
    obj.refresh_from_db()
    assert obj.created_by_id == user.pk


@pytest.mark.django_db
def test_nomination_admin_prohibits_add(make_admin_user):
    from django.contrib.admin.sites import AdminSite

    from memoriam.admin import InMemoriamNominationAdmin
    from memoriam.models import InMemoriamNomination

    admin = InMemoriamNominationAdmin(InMemoriamNomination, AdminSite())
    req = _admin_request(make_admin_user())
    assert admin.has_add_permission(req) is False
