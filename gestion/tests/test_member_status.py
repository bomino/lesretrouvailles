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
