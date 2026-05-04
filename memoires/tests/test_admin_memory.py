"""Tests for MemoryAdmin — admin form upload, save_model auto-stamp,
Cloudinary upload integration via FakeCloudinary."""

from __future__ import annotations

import io

import pytest
from django.test import Client


@pytest.fixture
def fake_cloudinary(settings):
    """Force the Cloudinary client to FakeCloudinary for these tests so we
    can inspect upload_calls. The dev/test settings already point here, but
    being explicit makes the test self-contained."""
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"


def _image_file(name: str = "photo.jpg") -> io.BytesIO:
    """Build a minimal in-memory file-like object for upload testing."""
    f = io.BytesIO(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    f.name = name
    return f


@pytest.mark.django_db
def test_admin_create_uploads_to_cloudinary_and_stamps_creator(fake_cloudinary, make_admin_user):
    """Creating a Memory via /admin/memoires/memory/add/ uploads the file
    to Cloudinary (FakeCloudinary records the call), writes the resulting
    public_id into Memory.photo_public_id, and stamps created_by."""
    from memoires.models import Memory

    creator = make_admin_user()
    client = Client()
    client.force_login(creator)

    response = client.post(
        "/admin/memoires/memory/add/",
        {
            "upload": _image_file("souvenir.jpg"),
            "caption": "Cours de récréation, 1983.",
            "taken_at": "1983-04-15",
            "location": "Birni",
            "status": "draft",
        },
    )
    assert response.status_code == 302, f"got {response.status_code}, body={response.content[:500]}"

    m = Memory.objects.get(caption="Cours de récréation, 1983.")
    assert m.photo_public_id.startswith("memoires/fake-")  # FakeCloudinary stub
    assert m.created_by == creator


@pytest.mark.django_db
def test_admin_edit_without_new_upload_keeps_existing_photo(fake_cloudinary, make_admin_user):
    """On edit, leaving the upload field blank must preserve the existing
    photo_public_id rather than blanking it."""
    from memoires.models import Memory

    creator = make_admin_user()
    client = Client()
    client.force_login(creator)

    # First create via admin to get a real photo_public_id from FakeCloudinary
    client.post(
        "/admin/memoires/memory/add/",
        {
            "upload": _image_file("first.jpg"),
            "caption": "Original caption",
            "status": "draft",
        },
    )
    m = Memory.objects.get(caption="Original caption")
    original_public_id = m.photo_public_id

    # Now edit without uploading a new file
    response = client.post(
        f"/admin/memoires/memory/{m.pk}/change/",
        {
            "upload": "",  # no new file
            "caption": "Updated caption",
            "status": "published",
        },
    )
    assert response.status_code == 302, (
        f"expected 302 (admin redirect after save), got {response.status_code}, "
        f"body={response.content[:500]}"
    )
    m.refresh_from_db()
    assert m.photo_public_id == original_public_id  # unchanged
    assert m.caption == "Updated caption"


@pytest.mark.django_db
def test_admin_edit_with_new_upload_replaces_photo_and_deletes_old(
    fake_cloudinary, make_admin_user
):
    """Replacing the photo on an edit triggers a new Cloudinary upload and
    writes a different public_id into photo_public_id.

    Note: get_client() returns a fresh FakeCloudinary instance each call, so
    delete_calls cannot be inspected across the create and edit requests. We
    assert the visible outcome instead: photo_public_id changes to a value
    derived from the new filename (FakeCloudinary is deterministic on name)."""
    from memoires.models import Memory

    creator = make_admin_user()
    client = Client()
    client.force_login(creator)

    # Create with "first.jpg"
    client.post(
        "/admin/memoires/memory/add/",
        {
            "upload": _image_file("first.jpg"),
            "caption": "Before replace",
            "status": "draft",
        },
    )
    m = Memory.objects.get(caption="Before replace")
    original_public_id = m.photo_public_id

    # Edit with "replacement.jpg" — different name → different deterministic public_id
    response = client.post(
        f"/admin/memoires/memory/{m.pk}/change/",
        {
            "upload": _image_file("replacement.jpg"),
            "caption": "Before replace",
            "status": "draft",
        },
    )
    assert response.status_code == 302, (
        f"expected 302, got {response.status_code}, body={response.content[:500]}"
    )

    m.refresh_from_db()
    assert m.photo_public_id != original_public_id, "photo_public_id should change after re-upload"
    assert m.photo_public_id.startswith("memoires/fake-")  # still a FakeCloudinary value
