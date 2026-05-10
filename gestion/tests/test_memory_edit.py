"""Tests for /gestion/souvenirs/<pk>/modifier/ — memory edit view."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from members.models import AuditLog

pytestmark = pytest.mark.django_db


def _make_upload(content_type: str = "image/jpeg") -> SimpleUploadedFile:
    return SimpleUploadedFile("new.jpg", b"x" * 1024, content_type=content_type)


class TestMemoryEditPermissions:
    def test_anon_redirected(self, client, make_memory):
        m = make_memory()
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        assert resp.status_code == 302

    def test_non_staff_403(self, client, regular_member_user, make_memory):
        m = make_memory()
        client.force_login(regular_member_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        assert resp.status_code == 403

    def test_coadmin_get_200(self, client, coadmin_user, make_memory):
        m = make_memory()
        client.force_login(coadmin_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        assert resp.status_code == 200

    def test_unknown_pk_404(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/999999/modifier/")
        assert resp.status_code == 404


class TestMemoryEditGet:
    def test_get_prefills_form_fields(self, client, coadmin_user, make_memory):
        m = make_memory(caption="Original caption", location="Niamey", status="published")
        client.force_login(coadmin_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        body = resp.content.decode()
        assert "Original caption" in body
        assert "Niamey" in body

    def test_get_renders_photo_preview(self, client, coadmin_user, make_memory):
        m = make_memory()
        client.force_login(coadmin_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
        body = resp.content.decode()
        assert m.photo_public_id in body


class TestMemoryEditFieldsOnly:
    def test_edit_caption_emits_one_edited_row(self, client, coadmin_user, make_memory):
        m = make_memory(caption="Original", status="published")
        client.force_login(coadmin_user)
        resp = client.post(
            f"/gestion/souvenirs/{m.pk}/modifier/",
            data={
                "caption": "Updated caption",
                "location": m.location,
                "status": m.status,
                "taken_at": "",
            },
        )
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=updated"
        m.refresh_from_db()
        assert m.caption == "Updated caption"
        rows = AuditLog.objects.filter(action="memoires.memory.edited")
        assert rows.count() == 1
        assert "caption" in rows.first().metadata["changed_fields"]
        assert rows.first().metadata["photo_replaced"] is False

    def test_edit_no_changes_emits_no_rows(self, client, coadmin_user, make_memory):
        m = make_memory(caption="Same", location="Niamey", status="published")
        client.force_login(coadmin_user)
        resp = client.post(
            f"/gestion/souvenirs/{m.pk}/modifier/",
            data={
                "caption": m.caption,
                "location": m.location,
                "status": m.status,
                "taken_at": "",
            },
        )
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=noop"
        assert AuditLog.objects.filter(action="memoires.memory.edited").count() == 0
        assert AuditLog.objects.filter(action="memoires.memory.published").count() == 0
        assert AuditLog.objects.filter(action="memoires.memory.unpublished").count() == 0


class TestMemoryEditPhotoReplace:
    def test_replace_photo_triggers_old_id_delete(
        self, client, coadmin_user, make_memory, settings
    ):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client

        reset_fake_client()

        m = make_memory(photo_public_id="memoires/old-id-here", status="published")
        old_id = m.photo_public_id
        client.force_login(coadmin_user)
        resp = client.post(
            f"/gestion/souvenirs/{m.pk}/modifier/",
            data={
                "caption": m.caption,
                "location": m.location,
                "status": m.status,
                "taken_at": "",
                "upload": _make_upload(),
            },
        )
        assert resp.status_code == 302
        m.refresh_from_db()
        assert m.photo_public_id != old_id
        # on_commit callbacks don't fire under pytest-django's default test
        # transaction (rollback). The test below uses transaction=True to
        # exercise the on_commit lambda. This test only asserts the audit row.
        # Edited row with photo_replaced=True, changed_fields=[]
        edited = AuditLog.objects.get(action="memoires.memory.edited")
        assert edited.metadata["photo_replaced"] is True
        assert edited.metadata["changed_fields"] == []

    @pytest.mark.django_db(transaction=True)
    def test_replace_photo_triggers_on_commit_delete(
        self, client, coadmin_user, make_memory, settings
    ):
        """Variant of the photo-replace test that uses transaction=True so
        the on_commit callback actually fires (and thus FakeCloudinary
        records the delete call)."""
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import get_client, reset_fake_client

        reset_fake_client()

        m = make_memory(photo_public_id="memoires/old-id-here", status="published")
        old_id = m.photo_public_id
        client.force_login(coadmin_user)
        client.post(
            f"/gestion/souvenirs/{m.pk}/modifier/",
            data={
                "caption": m.caption,
                "location": m.location,
                "status": m.status,
                "taken_at": "",
                "upload": _make_upload(),
            },
        )
        fake = get_client()
        # With transaction=True, the view's atomic block commits, which
        # triggers the on_commit lambda → client.delete(old_id) records.
        assert old_id in fake.delete_calls


class TestMemoryEditStatusFlip:
    def test_status_only_flip_via_edit_form_emits_only_status_row(
        self, client, coadmin_user, make_memory
    ):
        m = make_memory(status="draft")
        client.force_login(coadmin_user)
        resp = client.post(
            f"/gestion/souvenirs/{m.pk}/modifier/",
            data={
                "caption": m.caption,
                "location": m.location,
                "status": "published",
                "taken_at": "",
            },
        )
        assert resp.status_code == 302
        m.refresh_from_db()
        assert m.status == "published"
        # No .edited because only status changed
        assert AuditLog.objects.filter(action="memoires.memory.edited").count() == 0
        assert AuditLog.objects.filter(action="memoires.memory.published").count() == 1

    def test_field_change_plus_status_flip_emits_two_rows(self, client, coadmin_user, make_memory):
        m = make_memory(caption="Old", status="draft")
        client.force_login(coadmin_user)
        client.post(
            f"/gestion/souvenirs/{m.pk}/modifier/",
            data={
                "caption": "New",
                "location": m.location,
                "status": "published",
                "taken_at": "",
            },
        )
        assert AuditLog.objects.filter(action="memoires.memory.edited").count() == 1
        assert AuditLog.objects.filter(action="memoires.memory.published").count() == 1
