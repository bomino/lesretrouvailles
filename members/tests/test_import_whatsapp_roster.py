"""Tests for the import_whatsapp_roster management command (P7)."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

User = get_user_model()


@pytest.fixture
def fake_clients(settings):
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"


@pytest.fixture(autouse=True)
def reset_fakes():
    from alumni import cloudinary as cloud_mod

    cloud_mod.reset_fake_client()


def _write_csv(path: Path, rows: list[dict]) -> Path:
    """Write a roster CSV at `path` from a list of dict rows."""
    fields = [
        "first_name",
        "last_name",
        "nickname",
        "whatsapp",
        "email",
        "years_attended",
        "classes",
        "city",
        "country",
        "profession",
        "photo_filename",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            full = {k: row.get(k, "") for k in fields}
            writer.writerow(full)
    return path


def _row(**overrides) -> dict:
    """Sane defaults for a roster row, override what you want to test."""
    base = {
        "first_name": "Alice",
        "last_name": "Yamoussa",
        "nickname": "",
        "whatsapp": "+22790000001",
        "email": "alice@example.com",
        "years_attended": "1980,1981,1982,1983",
        "classes": "6e,5e,4e,3e",
        "city": "Niamey",
        "country": "Niger",
        "profession": "Médecin",
        "photo_filename": "",
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
def test_dry_run_makes_no_changes(fake_clients, tmp_path, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from members.models import Member

    csv_path = _write_csv(tmp_path / "roster.csv", [_row()])

    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--dry-run",
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=out,
    )

    assert User.objects.count() == 0
    assert Member.objects.count() == 0
    assert FakeResendBackend.sent_messages == []
    output = out.getvalue()
    assert "DRY RUN" in output
    assert "valid:" in output and "1" in output


@pytest.mark.django_db
def test_imports_email_member_and_sends_email(fake_clients, tmp_path, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.SITE_URL = "https://test.villageretrouvailles.local"
    from alumni.email import FakeResendBackend
    from members.models import Member

    FakeResendBackend.sent_messages.clear()
    csv_path = _write_csv(tmp_path / "roster.csv", [_row()])

    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=out,
    )

    assert User.objects.filter(username="22790000001").exists()
    user = User.objects.get(username="22790000001")
    assert user.email == "alice@example.com"
    assert Member.objects.filter(user=user).exists()
    member = Member.objects.get(user=user)
    assert member.first_name == "Alice"
    assert member.years_attended == [1980, 1981, 1982, 1983]
    assert member.classes == ["6e", "5e", "4e", "3e"]

    # Email path → password-set email goes out
    assert any(m["to"] == ["alice@example.com"] for m in FakeResendBackend.sent_messages)


@pytest.mark.django_db
def test_imports_no_email_member_and_writes_magic_link(fake_clients, tmp_path, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.SITE_URL = "https://test.villageretrouvailles.local"
    from alumni.email import FakeResendBackend
    from members.models import Member

    FakeResendBackend.sent_messages.clear()
    magic_path = tmp_path / "magic_links.csv"
    csv_path = _write_csv(
        tmp_path / "roster.csv",
        [_row(whatsapp="+22790000002", email="", first_name="Boubou")],
    )

    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(magic_path),
        stdout=out,
    )

    user = User.objects.get(username="22790000002")
    assert user.email == ""
    assert Member.objects.filter(user=user).exists()

    # No email sent for this row
    assert FakeResendBackend.sent_messages == []

    # magic_links.csv contains the URL
    assert magic_path.exists()
    with magic_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["whatsapp"] == "+22790000002"
    assert rows[0]["full_name"] == "Boubou Yamoussa"
    assert rows[0]["magic_link_url"].startswith(
        "https://test.villageretrouvailles.local/accounts/password/reset/key/",
    )


@pytest.mark.django_db
def test_uploads_photo_when_filename_provided(fake_clients, tmp_path, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni import cloudinary as cloud_mod
    from members.models import Member

    photos = tmp_path / "roster_photos"
    photos.mkdir()
    (photos / "alice.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

    csv_path = _write_csv(
        tmp_path / "roster.csv",
        [_row(photo_filename="alice.jpg")],
    )

    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--photos-dir",
        str(photos),
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=StringIO(),
    )

    member = Member.objects.get(user__username="22790000001")
    assert member.photo_public_id  # set to whatever FakeCloudinary returned

    cloud = cloud_mod.get_client()
    assert len(cloud.upload_calls) == 1
    assert cloud.upload_calls[0]["folder"].startswith("members/")


@pytest.mark.django_db
def test_idempotent_skips_existing_username(fake_clients, tmp_path, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import Member

    User.objects.create_user(
        username="22790000001",
        email="someone@else.com",
        password="x",
    )
    starting_user_count = User.objects.count()
    starting_member_count = Member.objects.count()

    csv_path = _write_csv(tmp_path / "roster.csv", [_row()])

    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=out,
    )

    assert User.objects.count() == starting_user_count
    assert Member.objects.count() == starting_member_count
    assert "skipped" in out.getvalue().lower()


@pytest.mark.django_db
def test_imports_row_with_empty_classes(fake_clients, tmp_path, settings):
    """Many WhatsApp-roster alumni don't recall their grade-by-grade history.
    A row with classes='' must validate and import (Member.classes=[])."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import Member

    csv_path = _write_csv(
        tmp_path / "roster.csv",
        [_row(classes="", whatsapp="+22790000099", email="noclass@example.com")],
    )

    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=out,
    )

    user = User.objects.get(username="22790000099")
    member = Member.objects.get(user=user)
    assert member.classes == []
    assert "1 created" in out.getvalue()


@pytest.mark.django_db
def test_validation_rejects_bad_year_class(fake_clients, tmp_path, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import Member

    csv_path = _write_csv(
        tmp_path / "roster.csv",
        [
            _row(years_attended="1979,1980", whatsapp="+22790000001"),  # bad year
            _row(classes="2nde,1ere", whatsapp="+22790000002"),  # bad class
            _row(whatsapp="+22790000003"),  # valid
        ],
    )

    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=out,
    )

    # Only the valid row imports
    assert Member.objects.count() == 1
    assert User.objects.filter(username="22790000003").exists()
    assert not User.objects.filter(username="22790000001").exists()
    assert not User.objects.filter(username="22790000002").exists()
    output = out.getvalue()
    assert "1 created" in output
    assert "errors" in output.lower()
