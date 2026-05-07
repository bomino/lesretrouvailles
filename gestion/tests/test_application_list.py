"""Phase 4 — /gestion/cooptations/ list view."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_application_list_anon_redirects(client):
    response = client.get("/gestion/cooptations/", follow=False)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_application_list_non_staff_blocked(client, regular_member_user):
    client.force_login(regular_member_user)
    response = client.get("/gestion/cooptations/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_application_list_default_shows_awaiting_admin(client, coadmin_user, make_application):
    """Default filter is 'à traiter' = applications awaiting admin review.
    Cooptation-pending (still being voted on by parrains) and approved ones
    aren't actionable, so they're hidden by default."""
    make_application(full_name="Awaiting Admin", status="awaiting_admin")
    make_application(full_name="Cooptation Pending", status="cooptation_pending")
    make_application(full_name="Already Approved", status="approved")
    client.force_login(coadmin_user)
    response = client.get("/gestion/cooptations/")
    assert b"Awaiting Admin" in response.content
    assert b"Cooptation Pending" not in response.content
    assert b"Already Approved" not in response.content


@pytest.mark.django_db
def test_application_list_status_pending_filter(client, coadmin_user, make_application):
    """status=pending shows BOTH awaiting_admin and cooptation_pending —
    everything still in flight."""
    make_application(full_name="Awaiting Admin", status="awaiting_admin")
    make_application(full_name="Cooptation Pending", status="cooptation_pending")
    make_application(full_name="Already Approved", status="approved")
    client.force_login(coadmin_user)
    response = client.get("/gestion/cooptations/?status=pending")
    assert b"Awaiting Admin" in response.content
    assert b"Cooptation Pending" in response.content
    assert b"Already Approved" not in response.content


@pytest.mark.django_db
def test_application_list_status_all_filter(client, coadmin_user, make_application):
    make_application(full_name="Awaiting Admin", status="awaiting_admin")
    make_application(full_name="Already Approved", status="approved")
    make_application(full_name="Was Rejected", status="rejected")
    client.force_login(coadmin_user)
    response = client.get("/gestion/cooptations/?status=all")
    assert b"Awaiting Admin" in response.content
    assert b"Already Approved" in response.content
    assert b"Was Rejected" in response.content


@pytest.mark.django_db
def test_application_list_excludes_purged_by_default(client, coadmin_user, make_application):
    """Purged applications (PII cleared, retention expired) shouldn't clutter
    the queue even on status=all. The /admin/ purge action handled them."""
    make_application(full_name="Awaiting Admin", status="awaiting_admin")
    purged = make_application(full_name="To Purge", status="awaiting_admin")
    purged.purge()  # sets status='purged' + clears PII
    client.force_login(coadmin_user)
    response = client.get("/gestion/cooptations/?status=all")
    assert b"Awaiting Admin" in response.content
    assert b"To Purge" not in response.content


@pytest.mark.django_db
def test_application_list_links_to_detail(client, coadmin_user, make_application):
    app = make_application(status="awaiting_admin")
    client.force_login(coadmin_user)
    response = client.get("/gestion/cooptations/")
    assert f"/gestion/cooptations/{app.pk}/".encode() in response.content
