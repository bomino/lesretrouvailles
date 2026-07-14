"""Tech-debt items F-12, F-23, F-24, F-26 (see TECH_DEBT_AUDIT.md)."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO

import pytest
from django.core.management import call_command
from PIL import Image

# ---------- F-12: is_published still encodes a dead two-admin rule ----------


@pytest.mark.django_db
def test_is_published_matches_the_one_admin_rule_actually_in_force(make_user):
    """The landing page, the admin filter, the stale-ghost cron and the launch
    audit all publish at >= 1 signoff (P4d single-admin governance). Only
    `is_published` still said >= 2, so any future caller reading the property
    would get the opposite answer from the page it is meant to describe."""
    from members.models import PublicSearchEntry

    entry = PublicSearchEntry.objects.create(
        first_name="Ghost", last_name_initial="G", years_at_ceg=[1980]
    )
    assert entry.is_published is False, "zero signoffs is a draft"

    entry.added_by_admins.add(make_user(is_staff=True))
    assert entry.is_published is True, "one signoff publishes — that is the live rule"


@pytest.mark.django_db
def test_removed_entry_never_publishes(make_user):
    from django.utils import timezone

    from members.models import PublicSearchEntry

    entry = PublicSearchEntry.objects.create(
        first_name="Ghost", last_name_initial="G", years_at_ceg=[1980], removed_at=timezone.now()
    )
    entry.added_by_admins.add(make_user(is_staff=True))
    assert entry.is_published is False


# ---------- F-23: roster import rejects pasted phone formats ----------


def _roster_csv(tmp_path, **row):
    fields = [
        "first_name",
        "last_name",
        "whatsapp",
        "email",
        "years_attended",
        "city",
        "photo_filename",
    ]
    base = {
        "first_name": "Awa",
        "last_name": "Diallo",
        "whatsapp": "+227 90 00 01 23",
        "email": "",
        "years_attended": "1980",
        "city": "Niamey",
        "photo_filename": "",
    }
    base.update(row)
    path = tmp_path / "roster.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerow(base)
    return path


@pytest.mark.django_db
def test_roster_import_accepts_a_pasted_whatsapp_number(tmp_path, settings):
    """F-23: the validator ran on the RAW string, so a number copied off a
    WhatsApp contact card ("+227 90 00 01 23") was rejected as invalid — while
    every gestion form strips punctuation before validating. The operator had to
    hand-clean 200 rows."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    from members.models import Member

    call_command(
        "import_whatsapp_roster",
        str(_roster_csv(tmp_path)),
        "--magic-links-out",
        str(tmp_path / "links.csv"),
        stdout=StringIO(),
    )

    member = Member.objects.get(user__username="22790000123")
    assert member.whatsapp == "22790000123"


@pytest.mark.django_db
def test_roster_import_still_rejects_a_real_non_number(tmp_path, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import Member

    out = StringIO()
    call_command(
        "import_whatsapp_roster",
        str(_roster_csv(tmp_path, whatsapp="pas-un-numero")),
        "--dry-run",
        "--magic-links-out",
        str(tmp_path / "links.csv"),
        stdout=out,
    )
    assert "not a valid phone number" in out.getvalue()
    assert Member.objects.count() == 0


# ---------- F-24: roster photo import mislabels every file as JPEG ----------


@pytest.mark.django_db
def test_roster_photo_upload_passes_the_real_content_type(tmp_path, settings):
    """F-24: the raw file handle carried no content_type, so _strip_exif_metadata
    defaulted to image/jpeg and would try to re-encode a PNG as JPEG."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    from alumni import cloudinary as cloud_mod

    cloud_mod.reset_fake_client()

    photos = tmp_path / "photos"
    photos.mkdir()
    buf = BytesIO()
    Image.new("RGBA", (20, 20), (0, 200, 0, 255)).save(buf, format="PNG")
    (photos / "awa.png").write_bytes(buf.getvalue())

    call_command(
        "import_whatsapp_roster",
        str(_roster_csv(tmp_path, photo_filename="awa.png")),
        "--photos-dir",
        str(photos),
        "--magic-links-out",
        str(tmp_path / "links.csv"),
        stdout=StringIO(),
    )

    call = cloud_mod.get_client().upload_calls[-1]
    # The bytes that reached Cloudinary must still be a PNG, not a mangled JPEG.
    assert Image.open(BytesIO(call["file_bytes"])).format == "PNG"


# ---------- F-26: a Cloudinary outage must not 500 a saved profile ----------


@pytest.mark.django_db
def test_profile_save_survives_a_failed_old_photo_delete(consenting_client, monkeypatch, settings):
    """F-26: the old photo was deleted synchronously AFTER the DB save. A
    Cloudinary failure therefore 500'd the member on an edit that had already
    succeeded."""
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    from alumni import cloudinary as cloud_mod

    member = consenting_client.member
    member.photo_public_id = "members/old/photo"
    member.save()

    def _boom(public_id):
        raise RuntimeError("cloudinary down")

    monkeypatch.setattr(cloud_mod.get_client(), "delete", _boom)

    response = consenting_client.post(
        "/profil/",
        {
            "first_name": member.first_name,
            "last_name": member.last_name,
            "nickname": "",
            "years_attended": "1980,1981",
            "classes": "6e",
            "city": "Niamey",
            "country": "Niger",
            "profession": "Nouvelle profession",
            "photo_public_id": "",
        },
    )

    assert response.status_code == 302, "the profile edit must not 500 on a delete failure"
    member.refresh_from_db()
    assert member.profession == "Nouvelle profession"
