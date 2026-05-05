"""Tests for the In Memoriam nomination form + view."""

from __future__ import annotations

import pytest


@pytest.fixture
def fake_email(settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages = []
    return FakeResendBackend


@pytest.fixture(autouse=True)
def reset_ratelimit_cache(settings):
    """django-ratelimit uses Django cache; clear before each test."""
    from django.core.cache import cache

    cache.clear()


@pytest.mark.django_db
def test_nomination_get_returns_200(authed_member_client):
    client, _ = authed_member_client
    resp = client.get("/in-memoriam/nominer/")
    assert resp.status_code == 200
    assert b"Nominer" in resp.content


@pytest.mark.django_db
def test_nomination_post_creates_pending_nomination(authed_member_client, fake_email, settings):
    settings.MEMORIAM_ADMIN_EMAILS = ["admin@example.test"]
    client, member = authed_member_client

    resp = client.post(
        "/in-memoriam/nominer/",
        {
            "proposed_name": "Camarade Disparu",
            "proposed_nickname": "",
            "proposed_years": "1980,1981",
            "personal_memory": "Souvenir partagé avec elle.",
            "family_contact_hint": "Sa fille au +227 90 00 00 00.",
        },
    )
    assert resp.status_code == 302
    assert resp["Location"] == "/in-memoriam/nominer/merci/"

    from memoriam.models import InMemoriamNomination

    nom = InMemoriamNomination.objects.get(proposed_name="Camarade Disparu")
    assert nom.status == "pending"
    assert nom.nominator_id == member.pk
    assert nom.proposed_years == [1980, 1981]

    # Admin alert email fired.
    assert any("Camarade Disparu" in m["subject"] for m in fake_email.sent_messages)


@pytest.mark.django_db
def test_nomination_rate_limit_blocks_second_post_within_24h(authed_member_client, fake_email):
    client, _ = authed_member_client

    payload = {
        "proposed_name": "Foo",
        "proposed_nickname": "",
        "proposed_years": "1980",
        "personal_memory": "Mémoire.",
        "family_contact_hint": "",
    }
    r1 = client.post("/in-memoriam/nominer/", payload)
    assert r1.status_code == 302  # success

    r2 = client.post("/in-memoriam/nominer/", {**payload, "proposed_name": "Bar"})
    assert r2.status_code == 403  # ratelimit blocks


@pytest.mark.django_db
def test_thanks_page_renders(authed_member_client):
    client, _ = authed_member_client
    resp = client.get("/in-memoriam/nominer/merci/")
    assert resp.status_code == 200
    assert b"Merci" in resp.content
