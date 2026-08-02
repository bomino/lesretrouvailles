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


@pytest.mark.django_db
def test_suspend_rolls_back_completely_if_audit_write_fails(
    client, coadmin_user, make_member, monkeypatch
):
    """M2 (2026-08-01 review): Member.status and User.is_active were saved in
    separate non-atomic writes — a failure between them left a 'suspended'
    member whose account could still log in (or the inverse). The whole
    status change must commit or roll back as one unit."""
    from members.models import AuditLog

    member = make_member(status="active")
    client.force_login(coadmin_user)

    def boom(*args, **kwargs):
        raise RuntimeError("db hiccup")

    monkeypatch.setattr(AuditLog.objects, "create", boom)

    with pytest.raises(RuntimeError):
        client.post(
            f"/gestion/membres/{member.slug}/statut/",
            {"target_status": "suspended"},
        )

    member.refresh_from_db()
    member.user.refresh_from_db()
    assert member.status == "active"  # rolled back together...
    assert member.user.is_active is True  # ...not half-applied


@pytest.mark.django_db
def test_member_edit_rolls_back_email_change_if_audit_write_fails(
    client, coadmin_user, make_member, monkeypatch
):
    """Same bug class in MemberAdminEditForm.save_with_audit: member save,
    user email save, and the audit row must be one transaction."""
    from members.models import AuditLog

    member = make_member(status="active")
    old_email = member.user.email
    client.force_login(coadmin_user)

    def boom(*args, **kwargs):
        raise RuntimeError("db hiccup")

    monkeypatch.setattr(AuditLog.objects, "create", boom)

    with pytest.raises(RuntimeError):
        client.post(
            f"/gestion/membres/{member.slug}/modifier/",
            {
                "first_name": member.first_name,
                "last_name": member.last_name,
                "nickname": "",
                "years_attended": "1980, 1981, 1982, 1983",
                "classes": "6e, 5e, 4e, 3e",
                "city": member.city,
                "country": member.country or "Niger",
                "profession": "",
                "email": "changed@example.test",
                "whatsapp": "",
            },
        )

    member.refresh_from_db()
    member.user.refresh_from_db()
    assert member.user.email == old_email  # user write rolled back with the rest
