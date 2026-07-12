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
    assert r2.status_code == 429  # French rate-limit page, not a bare English 403
    assert "réessayer demain" in r2.content.decode("utf-8")


@pytest.mark.django_db
def test_thanks_page_renders(authed_member_client):
    client, _ = authed_member_client
    resp = client.get("/in-memoriam/nominer/merci/")
    assert resp.status_code == 200
    assert b"Merci" in resp.content


@pytest.mark.django_db
def test_invalid_nomination_post_does_not_consume_daily_quota(authed_member_client, fake_email):
    """One typo plus a retry used to lock the member out for 24h: the
    counter incremented on every POST, valid or not. Only a successful
    save may consume the 1/d quota."""
    client, _ = authed_member_client

    bad = {
        "proposed_name": "Foo",
        "proposed_nickname": "",
        "proposed_years": "1980",
        "personal_memory": "",  # required — form invalid
        "family_contact_hint": "",
    }
    r1 = client.post("/in-memoriam/nominer/", bad)
    assert r1.status_code == 200  # re-rendered with errors

    good = {**bad, "personal_memory": "Un souvenir précis."}
    r2 = client.post("/in-memoriam/nominer/", good)
    assert r2.status_code == 302  # the retry succeeds


@pytest.mark.django_db
def test_nomination_admin_email_failure_does_not_500_after_save(
    authed_member_client, fake_email, monkeypatch, settings
):
    """The nomination is saved before the admin alert goes out; a Resend
    outage must not show the member an error for a recorded nomination."""
    from memoriam.models import InMemoriamNomination

    client, _ = authed_member_client
    settings.MEMORIAM_ADMIN_EMAILS = ["admin1@test"]

    def _boom(*args, **kwargs):
        raise RuntimeError("resend down")

    monkeypatch.setattr("memoriam.views.send_nomination_received_to_admins", _boom)

    payload = {
        "proposed_name": "Résilient",
        "proposed_nickname": "",
        "proposed_years": "1980",
        "personal_memory": "Mémoire.",
        "family_contact_hint": "",
    }
    response = client.post("/in-memoriam/nominer/", payload)
    assert response.status_code == 302
    assert InMemoriamNomination.objects.filter(proposed_name="Résilient").exists()
