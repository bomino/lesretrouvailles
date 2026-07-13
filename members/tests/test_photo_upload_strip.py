"""F-03: profile photos must go through the server-side EXIF strip.



Profile photos used to go browser -> Cloudinary directly via a signed upload,

bypassing `_strip_exif_metadata` entirely — so a photo taken at home kept its

GPS coordinates in the stored original, while the FAQ told members the

metadata was removed. CLAUDE.md states the doctrine plainly: a new uploader

that talks to Cloudinary directly reopens the privacy hole.



The upload now goes through Django, which strips via Pillow and then uploads.

The signed direct-upload endpoint is GONE — leaving it would keep the bypass

one curl away.

"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

# The JPEG APP1/Exif segment marker: b'Exif' + two NUL bytes. Built with
# bytes(2) rather than a source escape so no tooling can mangle it.
EXIF_MARKER = b"Exif" + bytes(2)


def _jpeg_with_exif(size=(40, 30)) -> bytes:
    """A JPEG carrying real EXIF, in the same APP1 segment GPS lives in.



    Pillow will not serialize a nested GPS IFD on save, so rather than fake one

    we assert something stronger downstream: that the whole APP1/Exif segment is

    gone from the stripped bytes. GPS coordinates live inside that segment — no

    segment, no GPS. That is airtight and does not depend on Pillow's writer.

    """

    img = Image.new("RGB", size, color="green")

    exif = img.getexif()

    exif[0x010E] = "taken at home"  # ImageDescription

    exif[0x010F] = "TestPhone"  # Make

    exif[0x0132] = "2026:07:12 20:00:00"  # DateTime

    buf = BytesIO()

    img.save(buf, format="JPEG", exif=exif)

    raw = buf.getvalue()

    assert EXIF_MARKER in raw, "fixture must actually carry an EXIF segment"

    return raw


def _upload(client, raw: bytes, name="photo.jpg", content_type="image/jpeg", **extra):

    return client.post(
        "/api/photo/upload/",
        {"file": SimpleUploadedFile(name, raw, content_type=content_type), **extra},
    )


@pytest.mark.django_db
def test_the_signed_direct_upload_endpoint_is_gone(consenting_client):
    """The bypass must not merely be unused — it must not exist."""

    response = consenting_client.post("/api/cloudinary/sign/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_uploaded_photo_reaches_cloudinary_without_exif(consenting_client, settings):

    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"

    from alumni import cloudinary as cloud_mod

    cloud_mod.reset_fake_client()

    response = _upload(consenting_client, _jpeg_with_exif())

    assert response.status_code == 200

    assert response.json()["public_id"]

    # The bytes that reached Cloudinary must carry NO EXIF segment at all.

    # GPS coordinates live in that segment, so its absence is the guarantee.

    sent = cloud_mod.get_client().upload_calls[-1]["file_bytes"]

    assert EXIF_MARKER not in sent, "the EXIF/APP1 segment (where GPS lives) survived"

    roundtrip = Image.open(BytesIO(sent))

    assert dict(roundtrip.getexif()) == {}, "EXIF tags survived the upload path"

    assert roundtrip.size == (40, 30), "the photo itself must be intact"


@pytest.mark.django_db
def test_upload_pins_the_folder_to_the_requesting_member(consenting_client, settings):

    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"

    from alumni import cloudinary as cloud_mod

    cloud_mod.reset_fake_client()

    _upload(consenting_client, _jpeg_with_exif())

    folder = cloud_mod.get_client().upload_calls[-1]["folder"]

    assert folder == f"members/{consenting_client.member.slug}/"


@pytest.mark.django_db
def test_upload_rejects_oversize_file_server_side(consenting_client, settings):
    """Enforced by the server now, not by a client-side check a member can skip."""

    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"

    big = b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 1)

    response = _upload(consenting_client, big)

    assert response.status_code == 400


@pytest.mark.django_db
def test_upload_rejects_non_image_content_type(consenting_client, settings):

    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"

    response = _upload(
        consenting_client, b"%PDF-1.4 not an image", name="x.pdf", content_type="application/pdf"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_upload_requires_login(client):

    response = client.post("/api/photo/upload/")

    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_non_staff_cannot_upload_on_behalf_of_another_member(
    consenting_client, make_member, settings
):
    """member_slug is the admin-on-behalf-of path — a member must not be able to

    overwrite someone else's photo with it."""

    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"

    from alumni import cloudinary as cloud_mod

    cloud_mod.reset_fake_client()

    victim = make_member()

    _upload(consenting_client, _jpeg_with_exif(), member_slug=str(victim.slug))

    folder = cloud_mod.get_client().upload_calls[-1]["folder"]

    assert folder == f"members/{consenting_client.member.slug}/", "folder must ignore member_slug"
