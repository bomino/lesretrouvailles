"""Tests for /gestion/souvenirs/ — the memory list view."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


class TestMemoryListPermissions:
    def test_anon_redirected_to_login(self, client):
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_regular_member_gets_403(self, client, regular_member_user):
        client.force_login(regular_member_user)
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 403

    def test_coadmin_sees_200(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 200

    def test_superadmin_sees_200(self, client, superadmin_user):
        client.force_login(superadmin_user)
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 200


class TestMemoryListContent:
    def test_lists_all_memories_by_default(self, client, coadmin_user, make_memory):
        make_memory(caption="Photo published one", status="published")
        make_memory(caption="Photo draft one", status="draft")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Photo published one" in body
        assert "Photo draft one" in body

    def test_filter_published(self, client, coadmin_user, make_memory):
        make_memory(caption="P1", status="published")
        make_memory(caption="D1", status="draft")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?status=published")
        body = resp.content.decode()
        assert "P1" in body
        assert "D1" not in body

    def test_filter_draft(self, client, coadmin_user, make_memory):
        make_memory(caption="P1", status="published")
        make_memory(caption="D1", status="draft")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?status=draft")
        body = resp.content.decode()
        assert "D1" in body
        assert "P1" not in body

    def test_bad_status_param_falls_back_to_all(self, client, coadmin_user, make_memory):
        make_memory(caption="P1", status="published")
        make_memory(caption="D1", status="draft")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?status=garbage")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "P1" in body
        assert "D1" in body

    def test_search_caption(self, client, coadmin_user, make_memory):
        make_memory(caption="Sortie à Birni 1983")
        make_memory(caption="Cérémonie de fin d'année")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?q=Birni")
        body = resp.content.decode()
        assert "Sortie à Birni 1983" in body
        assert "Cérémonie" not in body

    def test_search_location(self, client, coadmin_user, make_memory):
        make_memory(caption="Photo 1", location="Niamey")
        make_memory(caption="Photo 2", location="Paris")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?q=Niamey")
        body = resp.content.decode()
        assert "Photo 1" in body
        assert "Photo 2" not in body

    def test_search_accent_insensitive(self, client, coadmin_user, make_memory):
        make_memory(caption="Cérémonie")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?q=ceremonie")
        body = resp.content.decode()
        assert "Cérémonie" in body

    def test_empty_state_when_no_drafts(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/?status=draft")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Aucune photo" in body

    def test_thumbnails_lazy_load(self, client, coadmin_user, make_memory):
        make_memory(caption="Sample")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/")
        body = resp.content.decode()
        assert 'loading="lazy"' in body

    def test_pagination_at_page_size_12(self, client, coadmin_user, make_memory):
        for i in range(13):
            make_memory(caption=f"Photo {i:02d}")
        client.force_login(coadmin_user)
        resp_p1 = client.get("/gestion/souvenirs/?page=1")
        body_p1 = resp_p1.content.decode()
        assert body_p1.count("<figure") >= 12

        resp_p2 = client.get("/gestion/souvenirs/?page=2")
        assert resp_p2.status_code == 200

    def test_orders_by_created_at_descending(self, client, coadmin_user, make_memory):
        make_memory(caption="Early upload")
        make_memory(caption="Recent upload")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/souvenirs/")
        body = resp.content.decode()
        assert body.index("Recent upload") < body.index("Early upload")
