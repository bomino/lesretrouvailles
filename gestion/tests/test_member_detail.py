"""Phase 2 — /gestion/membres/<slug>/ detail page."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_member_detail_anon_redirects(client, make_member):
    member = make_member()
    response = client.get(f"/gestion/membres/{member.slug}/", follow=False)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_member_detail_non_staff_blocked(client, regular_member_user, make_member):
    member = make_member()
    client.force_login(regular_member_user)
    response = client.get(f"/gestion/membres/{member.slug}/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_member_detail_renders_all_fields(client, coadmin_user, make_member):
    member = make_member(
        first_name="Idrissa",
        last_name="Saidou",
        nickname="Driss",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e", "5eA", "4eB", "3eC"],
        city="Niamey",
        country="Niger",
        profession="Médecin",
    )
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Idrissa" in body
    assert "Saidou" in body
    assert "Driss" in body
    assert "1980" in body
    assert "6e" in body
    assert "Niamey" in body
    assert "Médecin" in body


@pytest.mark.django_db
def test_member_detail_404_for_unknown_slug(client, coadmin_user):
    import uuid

    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{uuid.uuid4()}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_member_detail_active_shows_suspend_button(client, coadmin_user, make_member):
    member = make_member(status="active")
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/")
    assert b"Suspendre" in response.content
    assert b"R\xc3\xa9activer" not in response.content


@pytest.mark.django_db
def test_member_detail_suspended_shows_reactivate_button(client, coadmin_user, make_member):
    member = make_member(status="suspended")
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/")
    assert b"R\xc3\xa9activer" in response.content
    assert b"Suspendre" not in response.content


@pytest.mark.django_db
def test_member_suspend_confirm_does_not_interpolate_member_name(client, coadmin_user, make_member):
    """Stored-XSS / broken-dialog regression: member names routinely contain
    apostrophes (N'Diaye) and originate from the public signup form for
    coopted members. Inside an inline onclick attribute, HTML-escaping does
    not protect a JS string — the name must not be interpolated at all."""
    member = make_member(first_name="N'Diaye", last_name="Amadou", status="active")
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/")
    body = response.content.decode("utf-8")
    assert "confirm('Suspendre ce membre ?" in body
    assert "confirm('Suspendre N" not in body


@pytest.mark.django_db
def test_member_detail_links_to_edit(client, coadmin_user, make_member):
    member = make_member()
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/")
    edit_url = f"/gestion/membres/{member.slug}/modifier/"
    assert edit_url.encode() in response.content
