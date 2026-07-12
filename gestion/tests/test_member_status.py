"""Phase 2 — /gestion/membres/<slug>/statut/ suspend/reactivate."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_member_status_get_not_allowed(client, coadmin_user, make_member):
    """Status changes are POST-only — GET returns 405."""
    member = make_member()
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/statut/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_member_status_non_staff_blocked(client, regular_member_user, make_member):
    member = make_member()
    client.force_login(regular_member_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/statut/",
        {"target_status": "suspended"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_member_status_suspend_active_member(client, coadmin_user, make_member):
    member = make_member(status="active")
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/statut/",
        {"target_status": "suspended"},
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.status == "suspended"


@pytest.mark.django_db
def test_member_status_reactivate_suspended_member(client, coadmin_user, make_member):
    member = make_member(status="suspended")
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/statut/",
        {"target_status": "active"},
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.status == "active"


@pytest.mark.django_db
def test_member_status_writes_audit_log_on_suspend(client, coadmin_user, make_member):
    from members.models import AuditLog

    member = make_member(status="active", first_name="Idrissa", last_name="Saidou")
    client.force_login(coadmin_user)
    client.post(
        f"/gestion/membres/{member.slug}/statut/",
        {"target_status": "suspended"},
    )
    log = AuditLog.objects.filter(
        action="gestion.member.suspended",
        target_id=str(member.pk),
    ).first()
    assert log is not None
    assert log.actor == coadmin_user
    assert log.metadata.get("previous_status") == "active"
    assert "Idrissa" in log.metadata.get("member_full_name", "")


@pytest.mark.django_db
def test_member_status_writes_audit_log_on_reactivate(client, coadmin_user, make_member):
    from members.models import AuditLog

    member = make_member(status="suspended")
    client.force_login(coadmin_user)
    client.post(
        f"/gestion/membres/{member.slug}/statut/",
        {"target_status": "active"},
    )
    assert AuditLog.objects.filter(
        action="gestion.member.reactivated",
        target_id=str(member.pk),
    ).exists()


@pytest.mark.django_db
def test_member_status_noop_when_target_matches_current(client, coadmin_user, make_member):
    """Submitting target=active when already active should not create an
    audit row and should not raise."""
    from members.models import AuditLog

    member = make_member(status="active")
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/statut/",
        {"target_status": "active"},
    )
    assert response.status_code == 302
    assert (
        AuditLog.objects.filter(
            action__startswith="gestion.member.",
            target_id=str(member.pk),
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_suspend_deactivates_user_and_kills_existing_session(client, coadmin_user, make_member):
    """Security regression: suspension must actually revoke access. The old
    view only flipped Member.status — the member kept their 90-day sliding
    session and full authenticated access to the directory."""
    from django.test import Client

    member = make_member(status="active")
    member.user.set_password("pw-secret-1")
    member.user.save()

    member_client = Client()
    assert member_client.login(username=member.user.username, password="pw-secret-1")
    # Authenticated but charter-unsigned members are redirected to /charte/,
    # NOT to the login page — that distinction is what we assert on below.
    assert "/charte/" in member_client.get("/annuaire/").url

    client.force_login(coadmin_user)
    client.post(f"/gestion/membres/{member.slug}/statut/", {"target_status": "suspended"})

    member.user.refresh_from_db()
    assert member.user.is_active is False

    response = member_client.get("/annuaire/")
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_suspend_deletes_member_db_sessions(client, coadmin_user, make_member):
    """The member's session rows are deleted outright, not just invalidated
    by the is_active check — defence in depth against any auth path that
    skips user_can_authenticate."""
    from django.contrib.sessions.models import Session
    from django.test import Client

    member = make_member(status="active")
    member.user.set_password("pw-secret-1")
    member.user.save()

    member_client = Client()
    assert member_client.login(username=member.user.username, password="pw-secret-1")
    session_key = member_client.session.session_key
    assert Session.objects.filter(session_key=session_key).exists()

    client.force_login(coadmin_user)
    client.post(f"/gestion/membres/{member.slug}/statut/", {"target_status": "suspended"})

    assert not Session.objects.filter(session_key=session_key).exists()


@pytest.mark.django_db
def test_suspended_member_cannot_log_back_in(client, coadmin_user, make_member):
    from django.test import Client

    member = make_member(status="active")
    member.user.set_password("pw-secret-1")
    member.user.save()

    client.force_login(coadmin_user)
    client.post(f"/gestion/membres/{member.slug}/statut/", {"target_status": "suspended"})

    assert not Client().login(username=member.user.username, password="pw-secret-1")


@pytest.mark.django_db
def test_reactivate_restores_login(client, coadmin_user, make_member):
    from django.test import Client

    member = make_member(status="suspended")
    member.user.set_password("pw-secret-1")
    member.user.is_active = False
    member.user.save()

    client.force_login(coadmin_user)
    client.post(f"/gestion/membres/{member.slug}/statut/", {"target_status": "active"})

    member.user.refresh_from_db()
    assert member.user.is_active is True
    assert Client().login(username=member.user.username, password="pw-secret-1")


@pytest.mark.django_db
def test_member_status_rejects_invalid_target(client, coadmin_user, make_member):
    member = make_member(status="active")
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/statut/",
        {"target_status": "deleted"},  # not allowed via this endpoint
    )
    # Redirects with bad_status flash; member status unchanged
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.status == "active"
