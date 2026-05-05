"""Tests for the new download() method on the Cloudinary client."""

from __future__ import annotations

import pytest


@pytest.fixture
def fake_cloudinary(settings):
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"


@pytest.mark.django_db
def test_fake_download_returns_deterministic_bytes(fake_cloudinary):
    from alumni.cloudinary import get_client, reset_fake_client

    reset_fake_client()
    client = get_client()
    a1 = client.download("members/abc/photo")
    a2 = client.download("members/abc/photo")
    b = client.download("members/xyz/photo")

    assert isinstance(a1, bytes)
    assert a1 == a2  # deterministic on public_id
    assert a1 != b  # different public_id -> different bytes


@pytest.mark.django_db
def test_fake_download_records_calls(fake_cloudinary):
    from alumni.cloudinary import get_client, reset_fake_client

    reset_fake_client()
    client = get_client()
    client.download("members/abc/photo")
    client.download("memoires/foo")

    assert client.download_calls == ["members/abc/photo", "memoires/foo"]
