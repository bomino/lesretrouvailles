"""Tests for POST /gestion/souvenirs/<pk>/statut/ — memory status toggle."""

from __future__ import annotations

import pytest

from members.models import AuditLog

pytestmark = pytest.mark.django_db


class TestMemoryStatusPermissions:
    def test_anon_redirected(self, client, make_memory):
        m = make_memory()
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "draft"})
        assert resp.status_code == 302

    def test_non_staff_403(self, client, regular_member_user, make_memory):
        m = make_memory()
        client.force_login(regular_member_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "draft"})
        assert resp.status_code == 403

    def test_get_405(self, client, coadmin_user, make_memory):
        m = make_memory()
        client.force_login(coadmin_user)
        resp = client.get(f"/gestion/souvenirs/{m.pk}/statut/")
        assert resp.status_code == 405

    def test_unknown_pk_404(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.post("/gestion/souvenirs/999999/statut/", data={"target_status": "draft"})
        assert resp.status_code == 404


class TestMemoryStatusToggle:
    def test_publish_a_draft(self, client, coadmin_user, make_memory):
        m = make_memory(status="draft")
        client.force_login(coadmin_user)
        resp = client.post(
            f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "published"}
        )
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=published"
        m.refresh_from_db()
        assert m.status == "published"
        row = AuditLog.objects.get(action="memoires.memory.published")
        assert row.metadata["previous_status"] == "draft"
        assert row.metadata["public_id"] == m.photo_public_id

    def test_unpublish_a_published(self, client, coadmin_user, make_memory):
        m = make_memory(status="published")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "draft"})
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=unpublished"
        m.refresh_from_db()
        assert m.status == "draft"
        row = AuditLog.objects.get(action="memoires.memory.unpublished")
        assert row.metadata["previous_status"] == "published"

    def test_target_equals_current_is_noop(self, client, coadmin_user, make_memory):
        m = make_memory(status="published")
        client.force_login(coadmin_user)
        resp = client.post(
            f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "published"}
        )
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=noop"
        m.refresh_from_db()
        assert m.status == "published"
        assert AuditLog.objects.filter(target_id=str(m.pk)).count() == 0

    def test_bad_target_status(self, client, coadmin_user, make_memory):
        m = make_memory(status="draft")
        client.force_login(coadmin_user)
        resp = client.post(f"/gestion/souvenirs/{m.pk}/statut/", data={"target_status": "archived"})
        assert resp.status_code == 302
        assert resp.url == "/gestion/souvenirs/?flash=bad_status"
        m.refresh_from_db()
        assert m.status == "draft"
        assert AuditLog.objects.filter(target_id=str(m.pk)).count() == 0
