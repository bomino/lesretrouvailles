"""Tests for POST /gestion/souvenirs/nouveau/ — memory create view."""

from __future__ import annotations

from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from members.models import AuditLog
from memoires.models import Memory

pytestmark = pytest.mark.django_db


def _make_upload(*, size_bytes: int = 1024, content_type: str = "image/jpeg") -> SimpleUploadedFile:
    return SimpleUploadedFile("test.jpg", b"x" * size_bytes, content_type=content_type)


class TestMemoryCreatePermissions:
    def test_anon_redirected(self, client):
        resp = client.get("/gestion/souvenirs/nouveau/")
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_non_staff_403(self, client, regular_member_user):
        client.force_login(regular_member_user)
        resp = client.get("/gestion/souvenirs/nouveau/")
        assert resp.status_code == 403

    def test_coadmin_get_200(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/nouveau/")
        assert resp.status_code == 200

    def test_superadmin_get_200(self, client, superadmin_user):
        client.force_login(superadmin_user)
        resp = client.get("/gestion/souvenirs/nouveau/")
        assert resp.status_code == 200


class TestMemoryCreateHappyPath:
    def test_create_draft_persists_memory(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client

        reset_fake_client()
        client.force_login(coadmin_user)
        # Django's test client auto-encodes multipart when an UploadedFile is
        # present in data — do NOT pass files= or format= kwargs.
        resp = client.post(
            "/gestion/souvenirs/nouveau/",
            data={
                "caption": "Sortie 1983",
                "taken_at": "",
                "location": "Birni",
                "status": "draft",
                "upload": _make_upload(),
            },
        )
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=created"
        memory = Memory.objects.get(caption="Sortie 1983")
        assert memory.status == "draft"
        assert memory.location == "Birni"
        assert memory.created_by == coadmin_user
        assert memory.photo_public_id.startswith("memoires/")

    def test_create_emits_one_audit_row_for_draft(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client

        reset_fake_client()
        client.force_login(coadmin_user)
        client.post(
            "/gestion/souvenirs/nouveau/",
            data={
                "caption": "Draft photo",
                "location": "",
                "status": "draft",
                "taken_at": "",
                "upload": _make_upload(),
            },
        )
        rows = list(AuditLog.objects.filter(action="memoires.memory.created"))
        assert len(rows) == 1
        assert rows[0].metadata["initial_status"] == "draft"
        assert rows[0].metadata["caption_preview"] == "Draft photo"
        assert rows[0].metadata["public_id"].startswith("memoires/")
        # No standalone .published row for create-draft
        assert not AuditLog.objects.filter(action="memoires.memory.published").exists()

    def test_create_emits_one_audit_row_for_published(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client

        reset_fake_client()
        client.force_login(coadmin_user)
        client.post(
            "/gestion/souvenirs/nouveau/",
            data={
                "caption": "Published from create",
                "location": "",
                "status": "published",
                "taken_at": "",
                "upload": _make_upload(),
            },
        )
        created_rows = list(AuditLog.objects.filter(action="memoires.memory.created"))
        assert len(created_rows) == 1
        assert created_rows[0].metadata["initial_status"] == "published"
        # Key contract: NO separate .published row at create time.
        assert not AuditLog.objects.filter(action="memoires.memory.published").exists()


class TestMemoryCreateValidation:
    def test_no_upload_re_renders_with_error(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.post(
            "/gestion/souvenirs/nouveau/",
            data={
                "caption": "x",
                "location": "",
                "status": "draft",
                "taken_at": "",
            },
        )
        assert resp.status_code == 200
        assert Memory.objects.count() == 0
        assert not AuditLog.objects.filter(action="memoires.memory.created").exists()

    def test_oversize_upload_re_renders_with_error(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        client.force_login(coadmin_user)
        big = _make_upload(size_bytes=9 * 1024 * 1024)
        resp = client.post(
            "/gestion/souvenirs/nouveau/",
            data={
                "caption": "x",
                "location": "",
                "status": "draft",
                "taken_at": "",
                "upload": big,
            },
        )
        assert resp.status_code == 200
        assert Memory.objects.count() == 0

    def test_cloudinary_failure_surfaces_to_form(self, client, coadmin_user, settings):
        settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
        from alumni.cloudinary import reset_fake_client

        reset_fake_client()
        client.force_login(coadmin_user)
        with mock.patch(
            "alumni.cloudinary.FakeCloudinary.upload_file",
            side_effect=RuntimeError("simulated cloudinary outage"),
        ):
            resp = client.post(
                "/gestion/souvenirs/nouveau/",
                data={
                    "caption": "x",
                    "location": "",
                    "status": "draft",
                    "taken_at": "",
                    "upload": _make_upload(),
                },
            )
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Échec" in body or "réessayez" in body.lower()
        assert Memory.objects.count() == 0
        assert not AuditLog.objects.filter(action="memoires.memory.created").exists()
