"""Tests for the S3-compatible storage client wrapper (FakeStorage + get_client)."""

from __future__ import annotations

import pytest


@pytest.fixture
def fake_storage(settings):
    settings.STORAGE_CLIENT_PATH = "alumni.storage.FakeStorage"


@pytest.fixture(autouse=True)
def reset_storage_singleton():
    from alumni.storage import reset_fake_client

    reset_fake_client()


@pytest.mark.django_db
def test_get_client_returns_fake_singleton_in_test_mode(fake_storage):
    from alumni.storage import FakeStorage, get_client

    c1 = get_client()
    c2 = get_client()
    assert isinstance(c1, FakeStorage)
    assert c1 is c2  # singleton across calls within a test


@pytest.mark.django_db
def test_fake_head_file_returns_none_for_unknown_path(fake_storage):
    from alumni.storage import get_client

    client = get_client()
    assert client.head_file("members/abc/photo") is None


@pytest.mark.django_db
def test_fake_upload_file_makes_subsequent_head_succeed(fake_storage):
    from alumni.storage import get_client

    client = get_client()
    file_id = client.upload_file("members/abc/photo", b"abc123")
    assert isinstance(file_id, str) and file_id

    info = client.head_file("members/abc/photo")
    assert info is not None
    assert info["size"] == 6
    assert client.upload_calls == [{"path": "members/abc/photo", "size": 6}]


@pytest.mark.django_db
def test_reset_fake_client_clears_state(fake_storage):
    from alumni.storage import get_client, reset_fake_client

    client = get_client()
    client.upload_file("foo", b"bar")
    assert client.head_file("foo") is not None

    reset_fake_client()
    fresh = get_client()
    assert fresh is not client
    assert fresh.head_file("foo") is None
