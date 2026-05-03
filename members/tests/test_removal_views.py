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


@pytest.mark.django_db
def test_confirm_valid_pending_executes_removal(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from django.contrib.auth import get_user_model

    from alumni.email import FakeResendBackend
    from members.models import RemovalRequest

    User = get_user_model()  # noqa: N806
    User.objects.create_user(
        username="staff", email="staff@example.test", password="x", is_staff=True
    )

    rreq = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    FakeResendBackend.sent_messages.clear()

    response = client.get(f"/retrait/confirme/{rreq.confirm_token}/")
    assert response.status_code == 200

    entry.refresh_from_db()
    rreq.refresh_from_db()
    assert entry.removed_at is not None
    assert rreq.status == "confirmed"
    assert rreq.confirmed_at is not None

    # 2 emails sent: requester + admin
    recipients = [tuple(m["to"]) for m in FakeResendBackend.sent_messages]
    assert ("x@y.test",) in recipients
    assert ("staff@example.test",) in recipients


@pytest.mark.django_db
def test_confirm_writes_two_audit_entries(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import AuditLog, RemovalRequest

    rreq = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    AuditLog.objects.filter(
        action__in=["ghost.removal.confirmed", "ghost.removal.executed"]
    ).delete()

    client.get(f"/retrait/confirme/{rreq.confirm_token}/")
    assert AuditLog.objects.filter(action="ghost.removal.confirmed").count() == 1
    assert AuditLog.objects.filter(action="ghost.removal.executed").count() == 1


@pytest.mark.django_db
def test_confirm_already_confirmed_is_idempotent(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from django.utils import timezone

    from alumni.email import FakeResendBackend
    from members.models import RemovalRequest

    rreq = RemovalRequest.objects.create(
        entry=entry,
        requester_email="x@y.test",
        status="confirmed",
        confirmed_at=timezone.now(),
    )
    entry.removed_at = timezone.now()
    entry.save()
    FakeResendBackend.sent_messages.clear()

    response = client.get(f"/retrait/confirme/{rreq.confirm_token}/")
    assert response.status_code == 200
    # No second-execution side effects: no new email
    assert len(FakeResendBackend.sent_messages) == 0


@pytest.mark.django_db
def test_confirm_expired_marks_status_and_renders_expired_page(client, entry, settings):
    from datetime import timedelta

    from django.utils import timezone

    from members.models import RemovalRequest

    rreq = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    # Backdate so expires_at is in the past
    rreq.expires_at = timezone.now() - timedelta(days=1)
    rreq.save()

    response = client.get(f"/retrait/confirme/{rreq.confirm_token}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "expir" in body.lower()

    rreq.refresh_from_db()
    assert rreq.status == "expired"
    entry.refresh_from_db()
    assert entry.removed_at is None  # not removed


@pytest.mark.django_db
def test_confirm_unknown_token_renders_expired_page(client):
    response = client.get("/retrait/confirme/this-token-does-not-exist/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "expir" in body.lower() or "invalide" in body.lower()


@pytest.mark.django_db
def test_entry_not_in_public_queryset_after_confirm(client, entry, settings, db):
    """Once removed, the entry must disappear from the public ghost queryset."""
    from django.contrib.auth import get_user_model
    from django.db.models import Count

    from members.models import PublicSearchEntry, RemovalRequest

    User = get_user_model()  # noqa: N806
    e = entry
    a, b = (
        User.objects.create_user(
            username=f"a{i}", email=f"a{i}@x.test", password="x", is_staff=True
        )
        for i in range(2)
    )
    e.added_by_admins.add(a, b)

    # Verify visible before removal
    qs = (
        PublicSearchEntry.objects.filter(removed_at__isnull=True)
        .annotate(n=Count("added_by_admins"))
        .filter(n__gte=2)
    )
    assert e in qs

    rreq = RemovalRequest.objects.create(entry=e, requester_email="x@y.test")
    client.get(f"/retrait/confirme/{rreq.confirm_token}/")

    # Verify gone after removal
    qs = (
        PublicSearchEntry.objects.filter(removed_at__isnull=True)
        .annotate(n=Count("added_by_admins"))
        .filter(n__gte=2)
    )
    assert e not in qs


@pytest.mark.django_db
def test_form_post_rate_limited_after_5_per_hour(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.RATELIMIT_ENABLE = True
    from django.core.cache import cache

    cache.clear()
    for i in range(5):
        client.post(
            f"/retrait/{entry.removal_token}/",
            {"email": f"r{i}@x.test"},
        )
    response = client.post(
        f"/retrait/{entry.removal_token}/",
        {"email": "r6@x.test"},
    )
    assert response.status_code == 429
