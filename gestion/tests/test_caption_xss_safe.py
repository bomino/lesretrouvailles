"""Regression: Memory.caption is ALWAYS plain text. Never markdown, never HTML.

If a future PR adds markdown rendering of captions, these tests catch it
before it ships.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

XSS_CAPTION = "<script>alert('xss')</script>"


def test_caption_escaped_on_public_souvenirs(client, regular_member_user, make_memory):
    make_memory(caption=XSS_CAPTION, status="published")
    client.force_login(regular_member_user)
    resp = client.get("/souvenirs/")
    body = resp.content.decode()
    assert "<script>alert" not in body
    assert "&lt;script&gt;" in body or "&lt;script" in body


def test_caption_escaped_on_gestion_list_alt(client, coadmin_user, make_memory):
    make_memory(caption=XSS_CAPTION, status="published")
    client.force_login(coadmin_user)
    resp = client.get("/gestion/souvenirs/")
    body = resp.content.decode()
    assert "<script>alert" not in body


def test_caption_escaped_on_gestion_edit(client, coadmin_user, make_memory):
    m = make_memory(caption=XSS_CAPTION, status="published")
    client.force_login(coadmin_user)
    resp = client.get(f"/gestion/souvenirs/{m.pk}/modifier/")
    body = resp.content.decode()
    # In a <textarea>, the content is auto-escaped by Django.
    assert "<script>alert" not in body
    # The escaped variant must be present somewhere (form value or img alt).
    assert "&lt;script" in body
