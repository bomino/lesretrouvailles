"""Tests for the backup_media management command."""

from __future__ import annotations

from datetime import date
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.fixture
def fake_clients(settings):
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    settings.STORAGE_CLIENT_PATH = "alumni.storage.FakeStorage"


@pytest.fixture(autouse=True)
def reset_fakes():
    from alumni import cloudinary as cloud_mod
    from alumni import storage as storage_mod

    storage_mod.reset_fake_client()
    cloud_mod.reset_fake_client()


def _make_admin():
    User = get_user_model()  # noqa: N806
    return User.objects.create_user(
        username="admin",
        email="admin@test",
        password="x",
        is_staff=True,
        is_superuser=True,
    )


def _make_member(slug_suffix, photo_public_id=""):
    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username=f"u{slug_suffix}",
        email=f"u{slug_suffix}@test",
        password="x",
    )
    return Member.objects.create(
        user=user,
        first_name=f"M{slug_suffix}",
        last_name="Member",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
        status="active",
        photo_public_id=photo_public_id,
    )


def _make_memory(admin, photo_public_id):
    from memoires.models import Memory

    return Memory.objects.create(
        photo_public_id=photo_public_id,
        caption="x",
        status="published",
        created_by=admin,
    )


def _make_inmemoriam(admin, photo_public_id):
    from memoriam.models import InMemoriamEntry

    return InMemoriamEntry.objects.create(
        full_name="X",
        years_attended=[1980],
        classes=["6e"],
        tribute="x",
        family_consent_giver="x",
        family_consent_date=date(2026, 1, 1),
        family_consent_canal="email",
        status="published",
        created_by=admin,
        photo_public_id=photo_public_id,
    )


@pytest.mark.django_db
def test_walks_all_three_model_sources(fake_clients):
    """Member, Memory, and InMemoriamEntry public_ids all enumerated and uploaded."""
    from alumni import storage as storage_mod

    admin = _make_admin()
    _make_member(1, photo_public_id="members/m1/photo")
    _make_memory(admin, "memoires/foo")
    _make_inmemoriam(admin, "memoriam/bar")

    out = StringIO()
    call_command("backup_media", stdout=out)

    storage = storage_mod.get_client()
    paths = sorted(call["path"] for call in storage.upload_calls)
    assert paths == ["members/m1/photo", "memoires/foo", "memoriam/bar"]
    assert "3 uploaded" in out.getvalue()


@pytest.mark.django_db
def test_skips_when_storage_already_has_path(fake_clients):
    """If head_file returns a record, the photo is skipped (no Cloudinary download, no upload)."""
    from alumni import cloudinary as cloud_mod
    from alumni import storage as storage_mod

    _make_member(1, photo_public_id="members/m1/photo")

    storage = storage_mod.get_client()
    storage.upload_file("members/m1/photo", b"already-backed-up")

    cloud = cloud_mod.get_client()
    cloud.download_calls.clear()
    storage.upload_calls.clear()

    out = StringIO()
    call_command("backup_media", stdout=out)

    assert cloud.download_calls == []
    assert storage.upload_calls == []
    assert "1 skipped" in out.getvalue()


@pytest.mark.django_db
def test_uploads_when_head_returns_none(fake_clients):
    """Path absent from storage -> command downloads from Cloudinary and uploads."""
    from alumni import cloudinary as cloud_mod
    from alumni import storage as storage_mod

    _make_member(1, photo_public_id="members/m1/photo")

    out = StringIO()
    call_command("backup_media", stdout=out)

    cloud = cloud_mod.get_client()
    storage = storage_mod.get_client()
    assert cloud.download_calls == ["members/m1/photo"]
    assert len(storage.upload_calls) == 1
    assert storage.upload_calls[0]["path"] == "members/m1/photo"


@pytest.mark.django_db
def test_continues_on_per_photo_failure(fake_clients):
    """A single Cloudinary failure doesn't abort the run; others still upload."""
    from alumni import cloudinary as cloud_mod
    from alumni import storage as storage_mod

    _make_member(1, photo_public_id="members/good/photo")
    _make_member(2, photo_public_id="members/bad/photo")

    cloud = cloud_mod.get_client()
    real_download = cloud.download

    def flaky_download(public_id):
        if "bad" in public_id:
            raise RuntimeError("simulated cloudinary 503")
        return real_download(public_id)

    with patch.object(cloud, "download", side_effect=flaky_download):
        out = StringIO()
        # 1/2 succeeded = 50%, below the 95% threshold -> SystemExit(1).
        # Wrapping here keeps the *continuation* assertion below valid: the
        # second photo must still have been processed before the exit fires.
        with pytest.raises(SystemExit):
            call_command("backup_media", stdout=out)

    storage = storage_mod.get_client()
    paths = sorted(call["path"] for call in storage.upload_calls)
    assert paths == ["members/good/photo"]
    assert "1 uploaded" in out.getvalue()
    assert "1 failed" in out.getvalue()


@pytest.mark.django_db
def test_exits_nonzero_when_success_rate_below_95(fake_clients):
    """If <95% of attempts succeed, the command exits with code 1."""
    from alumni import cloudinary as cloud_mod

    _make_member(1, photo_public_id="members/bad/photo")

    cloud = cloud_mod.get_client()

    def always_fail(public_id):
        raise RuntimeError("simulated total outage")

    with patch.object(cloud, "download", side_effect=always_fail):
        with pytest.raises(SystemExit) as exc_info:
            call_command("backup_media", stdout=StringIO())

    assert exc_info.value.code == 1


@pytest.mark.django_db
def test_empty_db_exits_silently_zero(fake_clients):
    """An empty DB is not an error: log + exit 0."""
    from alumni import storage as storage_mod

    out = StringIO()
    call_command("backup_media", stdout=out)

    storage = storage_mod.get_client()
    assert storage.upload_calls == []
    output = out.getvalue()
    assert "0 attempted" in output
