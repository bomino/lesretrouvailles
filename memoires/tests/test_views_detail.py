"""Tests for the detail view at /souvenirs/<id>/."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_detail_anonymous_redirects_to_login():
    from memoires.models import Memory

    m = Memory.objects.create(photo_public_id="memoires/p", caption="A photo", status="published")

    response = Client().get(f"/souvenirs/{m.pk}/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_detail_member_sees_published_memory(authed_member_client):
    from memoires.models import Memory

    m = Memory.objects.create(
        photo_public_id="memoires/published-detail",
        caption="A full caption with rich detail.",
        location="Birni",
        status="published",
    )

    response = authed_member_client.get(f"/souvenirs/{m.pk}/")
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "A full caption with rich detail." in body
    assert "memoires/published-detail" in body  # full-size URL contains public_id
    assert "Birni" in body


@pytest.mark.django_db
def test_detail_returns_404_on_draft(authed_member_client):
    """Drafts are admin-curation territory; even members see 404."""
    from memoires.models import Memory

    m = Memory.objects.create(
        photo_public_id="memoires/draft",
        caption="A draft photo",
        status="draft",
    )

    response = authed_member_client.get(f"/souvenirs/{m.pk}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_detail_returns_404_on_unknown_pk(authed_member_client):
    response = authed_member_client.get("/souvenirs/99999/")
    assert response.status_code == 404
