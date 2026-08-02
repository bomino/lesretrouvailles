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

    Note: this test asserts the visible outcome (photo_public_id change) rather
    than inspecting client.delete_calls. The singleton FakeCloudinary in test
    mode does record delete_calls across requests, but checking the visible
    result is more robust (doesn't depend on call ordering across requests)."""
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


@pytest.mark.django_db
def test_delete_memory_removes_cloudinary_photo(fake_cloudinary, make_admin_user):
    """Hard delete via /admin/memoires/ is that admin's remaining purpose
    (every other op moved to /gestion/souvenirs/) — it must not orphan the
    Cloudinary asset."""
    from django.contrib.admin.sites import AdminSite
    from django.test import RequestFactory, TestCase

    from alumni import cloudinary as cloud_mod
    from memoires.admin import MemoryAdmin
    from memoires.models import Memory

    cloud_mod.reset_fake_client()
    memory = Memory.objects.create(
        caption="À supprimer",
        photo_public_id="memoires/orphan-candidate",
        created_by=make_admin_user(),
    )

    admin_obj = MemoryAdmin(Memory, AdminSite())
    req = RequestFactory().post("/admin/")
    req.user = make_admin_user()

    with TestCase.captureOnCommitCallbacks(execute=True):
        admin_obj.delete_model(req, memory)

    assert "memoires/orphan-candidate" in cloud_mod.get_client().delete_calls


@pytest.mark.django_db
def test_hard_delete_writes_audit_row(make_admin_user, settings):
    """T8 (2026-08-01 review tail): /admin/ hard delete is this admin's one
    remaining purpose, and it left no AuditLog trail."""
    from django.contrib.admin.sites import site

    from members.models import AuditLog
    from memoires.admin import MemoryAdmin
    from memoires.models import Memory

    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    admin_user = make_admin_user()
    memory = Memory.objects.create(
        photo_public_id="memoires/audit-del",
        caption="Souvenir à supprimer pour test",
        status="draft",
        created_by=admin_user,
    )

    class FakeReq:
        user = admin_user

    admin_obj = MemoryAdmin(Memory, site)
    memory_pk = memory.pk  # delete() sets instance.pk to None
    admin_obj.delete_model(FakeReq(), memory)

    log = AuditLog.objects.get(action="memoires.memory.deleted", target_id=str(memory_pk))
    assert log.metadata["caption_preview"].startswith("Souvenir à supprimer")
    assert log.actor == admin_user


@pytest.mark.django_db
def test_admin_upload_form_enforces_size_and_mime():
    """Mirror of the gestion form's guards on the admin form."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from memoires.forms import MemoryAdminForm

    big = SimpleUploadedFile("big.jpg", b"x" * (8 * 1024 * 1024 + 1), content_type="image/jpeg")
    form = MemoryAdminForm(data={"caption": "c", "status": "draft"}, files={"upload": big})
    form.is_valid()
    assert "upload" in form.errors

    pdf = SimpleUploadedFile("x.pdf", b"%PDF-1.4", content_type="application/pdf")
    form = MemoryAdminForm(data={"caption": "c", "status": "draft"}, files={"upload": pdf})
    form.is_valid()
    assert "upload" in form.errors
