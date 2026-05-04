"""Tests for the gallery view at /souvenirs/."""

from __future__ import annotations

import pytest
from django.test import Client

URL = "/souvenirs/"


@pytest.mark.django_db
def test_gallery_anonymous_redirects_to_login():
    response = Client().get(URL)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_gallery_member_sees_published_memories(authed_member_client):
    from memoires.models import Memory

    Memory.objects.create(
        photo_public_id="memoires/published-photo",
        caption="A precious memory from Birni",
        status="published",
    )

    response = authed_member_client.get(URL)
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "A precious memory from Birni" in body
    assert "memoires/published-photo" in body  # thumbnail URL contains public_id


@pytest.mark.django_db
def test_gallery_hides_drafts_from_members(authed_member_client):
    """Drafts are admin-curation territory and must not appear on /souvenirs/."""
    from memoires.models import Memory

    Memory.objects.create(
        photo_public_id="memoires/published",
        caption="VISIBLE PUB",
        status="published",
    )
    Memory.objects.create(
        photo_public_id="memoires/draft",
        caption="HIDDEN DRAFT",
        status="draft",
    )

    response = authed_member_client.get(URL)
    body = response.content.decode("utf-8")
    assert "VISIBLE PUB" in body
    assert "HIDDEN DRAFT" not in body
