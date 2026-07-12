"""Phase 4 — /gestion/cooptations/<id>/ detail with approve/reject."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_application_detail_anon_redirects(client, make_application):
    app = make_application()
    response = client.get(f"/gestion/cooptations/{app.pk}/", follow=False)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_application_detail_non_staff_blocked(client, regular_member_user, make_application):
    app = make_application()
    client.force_login(regular_member_user)
    response = client.get(f"/gestion/cooptations/{app.pk}/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_application_detail_renders_application_data(client, coadmin_user, make_application):
    app = make_application(
        full_name="Idrissa Saidou",
        nickname="Driss",
        years_attended=[1980, 1981, 1982],
        classes=["6e", "5eA"],
        city="Niamey",
        country="Niger",
        email="cand@example.test",
        whatsapp="+22790000111",
    )
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/cooptations/{app.pk}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Idrissa Saidou" in body
    assert "Driss" in body
    assert "1980" in body
    assert "6e" in body
    assert "Niamey" in body
    assert "cand@example.test" in body


@pytest.mark.django_db
def test_application_detail_renders_parrain_panels(client, coadmin_user, make_cooptation_request):
    """Each linked CooptationRequest renders as a collapsible panel
    (HTML <details>) showing parrain name, response, and deadline."""
    req = make_cooptation_request()
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/cooptations/{req.application.pk}/")
    body = response.content.decode("utf-8")
    assert "<details" in body
    # Parrain identity is surfaced
    assert req.parrain.full_name in body


@pytest.mark.django_db
def test_application_detail_404_for_unknown_id(client, coadmin_user):
    client.force_login(coadmin_user)
    response = client.get("/gestion/cooptations/99999/")
    assert response.status_code == 404


# ---------- Approve action ----------


@pytest.mark.django_db
def test_application_approve_creates_member_and_writes_audit(
    client, coadmin_user, make_application, settings
):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from django.contrib.auth import get_user_model

    from members.models import AuditLog, Member

    User = get_user_model()  # noqa: N806
    app = make_application(
        full_name="Idrissa Saidou",
        email="newcandidate@example.test",
        status="awaiting_admin",
    )
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/cooptations/{app.pk}/approuver/",
    )
    assert response.status_code == 302

    app.refresh_from_db()
    assert app.status == "approved"
    assert User.objects.filter(email="newcandidate@example.test").exists()
    assert Member.objects.filter(user__email="newcandidate@example.test").exists()

    log = AuditLog.objects.filter(
        action="gestion.application.approved",
        target_id=str(app.pk),
    ).first()
    assert log is not None
    assert log.actor == coadmin_user


@pytest.mark.django_db
def test_application_approve_sends_email(client, coadmin_user, make_application, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    app = make_application(email="newcandidate@example.test", status="awaiting_admin")
    client.force_login(coadmin_user)
    client.post(f"/gestion/cooptations/{app.pk}/approuver/")
    assert any(m["to"] == ["newcandidate@example.test"] for m in FakeResendBackend.sent_messages)


@pytest.mark.django_db
def test_application_approve_get_not_allowed(client, coadmin_user, make_application):
    """Approve is POST-only — GET returns 405 even for staff."""
    app = make_application()
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/cooptations/{app.pk}/approuver/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_application_approve_non_staff_blocked(client, regular_member_user, make_application):
    app = make_application()
    client.force_login(regular_member_user)
    response = client.post(f"/gestion/cooptations/{app.pk}/approuver/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_application_approve_refused_redirects_with_flash_not_500(
    client, coadmin_user, make_application, settings
):
    """Approving an application the service refuses (already approved, blank
    email, existing user…) must surface a French flash message, not a 500,
    and must not write a gestion.application.approved audit row."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import AuditLog

    app = make_application(email="done@example.test", status="approved")
    client.force_login(coadmin_user)
    response = client.post(f"/gestion/cooptations/{app.pk}/approuver/")
    assert response.status_code == 302
    assert "flash=approve_refused" in response.url

    app.refresh_from_db()
    assert app.status == "approved"
    assert not AuditLog.objects.filter(
        action="gestion.application.approved", target_id=str(app.pk)
    ).exists()

    # The flash renders a French explanation on the detail page.
    follow = client.get(response.url)
    assert b"Approbation impossible" in follow.content


@pytest.mark.django_db
def test_application_approve_confirm_does_not_interpolate_candidate_name(
    client, coadmin_user, make_application
):
    """Stored-XSS regression: full_name comes from the public /inscription/
    form. Inside an inline onclick attribute the browser HTML-decodes
    &#x27; back to a real quote BEFORE the JS engine parses it, so
    HTML-escaping does not protect a JS string. The candidate's name must
    not appear inside the confirm() call at all."""
    app = make_application(
        full_name="x');alert(document.domain);('",
        status="awaiting_admin",
    )
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/cooptations/{app.pk}/")
    body = response.content.decode("utf-8")
    assert "confirm('Approuver cette candidature ?" in body
    assert "confirm('Approuver x" not in body


# ---------- Reject action ----------


@pytest.mark.django_db
def test_application_reject_sets_status_and_writes_audit(
    client, coadmin_user, make_application, settings
):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import AuditLog

    app = make_application(status="awaiting_admin")
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/cooptations/{app.pk}/rejeter/",
        {"reason": "Hors cohorte 1980-1985"},
    )
    assert response.status_code == 302

    app.refresh_from_db()
    assert app.status == "rejected"
    assert app.review_note == "Hors cohorte 1980-1985"
    assert app.retention_until is not None

    log = AuditLog.objects.filter(
        action="gestion.application.rejected",
        target_id=str(app.pk),
    ).first()
    assert log is not None
    assert log.metadata.get("reviewer_note") == "Hors cohorte 1980-1985"


@pytest.mark.django_db
def test_application_reject_requires_non_empty_reason(client, coadmin_user, make_application):
    app = make_application(status="awaiting_admin")
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/cooptations/{app.pk}/rejeter/",
        {"reason": ""},
    )
    # Form re-rendered with error, no redirect
    assert response.status_code == 200
    app.refresh_from_db()
    assert app.status == "awaiting_admin"  # unchanged


@pytest.mark.django_db
def test_application_reject_non_staff_blocked(client, regular_member_user, make_application):
    app = make_application()
    client.force_login(regular_member_user)
    response = client.post(
        f"/gestion/cooptations/{app.pk}/rejeter/",
        {"reason": "x"},
    )
    assert response.status_code == 403
