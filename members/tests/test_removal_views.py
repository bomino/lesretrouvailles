"""Tests for the public 'Retirer mon nom' flow views."""

from __future__ import annotations

import pytest


@pytest.fixture
def entry(db):
    from members.models import PublicSearchEntry

    return PublicSearchEntry.objects.create(
        first_name="Idrissa",
        last_name_initial="S.",
        years_at_ceg=[1980, 1981, 1982, 1983],
    )


@pytest.mark.django_db
def test_form_get_valid_token_returns_200_with_preview(client, entry):
    response = client.get(f"/retrait/{entry.removal_token}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Idrissa" in body
    assert "S." in body
    # Form fields present
    assert 'name="email"' in body
    assert 'name="reason"' in body


@pytest.mark.django_db
def test_form_get_unknown_token_404(client):
    response = client.get("/retrait/unknown-token/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_form_post_creates_request_and_sends_email(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.SITE_URL = "https://prod.example.test"
    from alumni.email import FakeResendBackend
    from members.models import RemovalRequest

    FakeResendBackend.sent_messages.clear()
    response = client.post(
        f"/retrait/{entry.removal_token}/",
        {"email": "candidate@example.test", "reason": "Je veux disparaître"},
        REMOTE_ADDR="203.0.113.7",
    )
    assert response.status_code == 302
    assert response["Location"] == "/retrait/merci/"

    r = RemovalRequest.objects.get(entry=entry, requester_email="candidate@example.test")
    assert r.reason == "Je veux disparaître"
    assert r.requester_ip == "203.0.113.7"
    assert r.status == "pending_confirmation"

    # Email sent
    assert len(FakeResendBackend.sent_messages) == 1
    msg = FakeResendBackend.sent_messages[0]
    assert msg["to"] == ["candidate@example.test"]
    assert r.confirm_token in msg["text"]


@pytest.mark.django_db
def test_form_post_writes_audit_requested(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import AuditLog

    AuditLog.objects.filter(action="ghost.removal.requested").delete()
    client.post(
        f"/retrait/{entry.removal_token}/",
        {"email": "candidate@example.test", "reason": ""},
    )
    log = AuditLog.objects.get(action="ghost.removal.requested")
    assert log.metadata["requester_email"] == "candidate@example.test"


@pytest.mark.django_db
def test_form_post_works_when_flag_off(client, entry, settings):
    """Removal respects consent independent of public visibility."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.PUBLIC_GHOST_LIST_ENABLED = False
    from members.models import RemovalRequest

    response = client.post(
        f"/retrait/{entry.removal_token}/",
        {"email": "candidate@example.test"},
    )
    assert response.status_code == 302
    assert RemovalRequest.objects.filter(entry=entry).exists()


@pytest.mark.django_db
def test_done_page_returns_200(client):
    response = client.get("/retrait/merci/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Vérifiez votre boîte mail" in body or "Vérifiez votre boite mail" in body
