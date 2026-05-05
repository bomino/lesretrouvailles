"""Tests for memoriam views — list + detail."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_list_view_anon_redirects_to_login(client):
    resp = client.get("/in-memoriam/")
    assert resp.status_code in (301, 302)
    assert "/accounts/login/" in resp["Location"]


@pytest.mark.django_db
def test_list_view_member_200(authed_member_client, make_memoriam_entry):
    client, _ = authed_member_client
    make_memoriam_entry(full_name="Aïssa Dembélé")
    resp = client.get("/in-memoriam/")
    assert resp.status_code == 200
    assert b"A\xc3\xafssa Demb\xc3\xa9l\xc3\xa9" in resp.content


@pytest.mark.django_db
def test_list_excludes_drafts_and_archived(authed_member_client, make_memoriam_entry):
    client, _ = authed_member_client
    make_memoriam_entry(status="published", full_name="Visible Name")
    make_memoriam_entry(status="draft", full_name="Hidden Draft")
    make_memoriam_entry(status="archived", full_name="Hidden Archive")

    resp = client.get("/in-memoriam/")
    assert b"Visible Name" in resp.content
    assert b"Hidden Draft" not in resp.content
    assert b"Hidden Archive" not in resp.content


@pytest.mark.django_db
def test_detail_published_200(authed_member_client, make_memoriam_entry):
    client, _ = authed_member_client
    entry = make_memoriam_entry(status="published")
    resp = client.get(f"/in-memoriam/{entry.pk}/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_detail_draft_404(authed_member_client, make_memoriam_entry):
    client, _ = authed_member_client
    entry = make_memoriam_entry(status="draft")
    resp = client.get(f"/in-memoriam/{entry.pk}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_detail_archived_404(authed_member_client, make_memoriam_entry):
    client, _ = authed_member_client
    entry = make_memoriam_entry(status="archived")
    resp = client.get(f"/in-memoriam/{entry.pk}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_detail_strips_script_tags_from_tribute(authed_member_client, make_memoriam_entry):
    """Defense in depth: even if a malicious admin writes <script> in tribute,
    the rendered detail page must not contain executable script tags."""
    client, _ = authed_member_client
    entry = make_memoriam_entry(
        tribute="Hommage. <script>alert('xss')</script> **fin**",
    )
    resp = client.get(f"/in-memoriam/{entry.pk}/")
    assert resp.status_code == 200
    assert b"<script>" not in resp.content
