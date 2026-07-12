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
def test_import_sets_member_whatsapp_to_digits_only_phone(fake_clients, tmp_path, settings):
    """The roster import must populate Member.whatsapp explicitly (not just
    rely on User.username happening to equal the phone). This decouples
    login identity from messaging identity for everything downstream."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import Member

    csv_path = _write_csv(
        tmp_path / "roster.csv",
        [_row(whatsapp="+22790000314", email="m@example.test")],
    )
    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=out,
    )
    member = Member.objects.get(user__username="22790000314")
    assert member.whatsapp == "22790000314"


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


@pytest.mark.django_db
def test_welcome_email_failure_does_not_abort_and_writes_link_to_csv(
    fake_clients, tmp_path, settings, monkeypatch
):
    """Regression: a single Resend outage mid-import used to crash handle()
    and lose every accumulated magic link. The failed row's URL must land in
    the magic-links CSV so the operator can DM it instead."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import Member

    rows = [
        _row(first_name="Fail", whatsapp="+22790000010", email="fail@example.com"),
        _row(first_name="After", whatsapp="+22790000011", email=""),
    ]
    csv_path = _write_csv(tmp_path / "roster.csv", rows)
    links_path = tmp_path / "magic_links.csv"

    def _flaky(self, member, url, email):
        if email == "fail@example.com":
            raise RuntimeError("resend down")

    monkeypatch.setattr(
        "members.management.commands.import_whatsapp_roster.Command._send_welcome_email",
        _flaky,
    )

    out, err = StringIO(), StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(links_path),
        stdout=out,
        stderr=err,
    )

    # Both members created despite the failed email.
    assert Member.objects.count() == 2
    content = links_path.read_text(encoding="utf-8")
    # The email-less member's link is there AND the failed-email member's
    # link was written as a fallback.
    assert "22790000011" in content
    assert "22790000010" in content


@pytest.mark.django_db
def test_no_emails_flag_writes_email_rows_to_magic_links_csv(fake_clients, tmp_path, settings):
    """--no-emails used to silently drop password-set URLs for email-having
    rows (the promised 'later batch send' command does not exist)."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    csv_path = _write_csv(
        tmp_path / "roster.csv",
        [_row(first_name="Mailed", whatsapp="+22790000020", email="mailed@example.com")],
    )
    links_path = tmp_path / "magic_links.csv"

    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--no-emails",
        "--magic-links-out",
        str(links_path),
        stdout=StringIO(),
    )

    assert FakeResendBackend.sent_messages == []
    content = links_path.read_text(encoding="utf-8")
    assert "22790000020" in content
    assert "/accounts/password/reset/key/" in content


@pytest.mark.django_db
def test_csv_without_classes_column_imports_cleanly(fake_clients, tmp_path, settings):
    """Regression: a CSV omitting the optional 'classes' header validated
    clean in --dry-run but KeyError'd every row at real import."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import Member

    fields = [
        "first_name",
        "last_name",
        "whatsapp",
        "email",
        "years_attended",
        "city",
    ]
    csv_path = tmp_path / "roster.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "first_name": "Sans",
                "last_name": "Classes",
                "whatsapp": "+22790000030",
                "email": "",
                "years_attended": "1980,1981",
                "city": "Niamey",
            }
        )

    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=StringIO(),
    )

    member = Member.objects.get(user__username="22790000030")
    assert member.classes == []


@pytest.mark.django_db
def test_dry_run_predicts_existing_and_duplicate_skips(fake_clients, tmp_path, settings):
    """Regression: --dry-run reported 'valid: N' for rows the real run would
    SKIP (username already exists) or collapse (intra-CSV duplicates after
    digit normalization), giving the operator a wrong plan on re-runs."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"

    User.objects.create_user(username="22790000040", password="x")

    rows = [
        _row(first_name="Existing", whatsapp="+22790000040", email=""),
        _row(first_name="DupA", whatsapp="+22790000041", email=""),
        _row(first_name="DupB", whatsapp="22790000041", email=""),  # same digits
        _row(first_name="Fresh", whatsapp="+22790000042", email=""),
    ]
    csv_path = _write_csv(tmp_path / "roster.csv", rows)

    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--dry-run",
        "--magic-links-out",
        str(tmp_path / "magic_links.csv"),
        stdout=out,
    )
    output = out.getvalue()
    assert "would skip (already exist): 1" in output
    assert "duplicates in CSV:         1" in output
