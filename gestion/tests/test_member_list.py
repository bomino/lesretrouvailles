"""Phase 2 — /gestion/membres/ directory."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_member_list_anon_redirects(client):
    response = client.get("/gestion/membres/", follow=False)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_member_list_non_staff_blocked(client, regular_member_user):
    client.force_login(regular_member_user)
    response = client.get("/gestion/membres/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_member_list_staff_sees_200(client, coadmin_user, make_member):
    make_member(first_name="Idrissa", last_name="Saidou")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/")
    assert response.status_code == 200
    assert b"Idrissa" in response.content


@pytest.mark.django_db
def test_member_list_default_filter_excludes_suspended(client, coadmin_user, make_member):
    make_member(first_name="Aktif", last_name="One", status="active")
    make_member(first_name="Suspended", last_name="Two", status="suspended")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/")
    assert b"Aktif" in response.content
    assert b"Suspended" not in response.content


@pytest.mark.django_db
def test_member_list_status_suspended_filter(client, coadmin_user, make_member):
    make_member(first_name="Aktif", last_name="One", status="active")
    make_member(first_name="Suspendido", last_name="Two", status="suspended")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/?status=suspended")
    assert b"Suspendido" in response.content
    assert b"Aktif" not in response.content


@pytest.mark.django_db
def test_member_list_status_all_filter(client, coadmin_user, make_member):
    make_member(first_name="Active", last_name="A", status="active")
    make_member(first_name="Suspendu", last_name="S", status="suspended")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/?status=all")
    assert b"Active" in response.content
    assert b"Suspendu" in response.content


@pytest.mark.django_db
def test_member_list_excludes_deleted(client, coadmin_user, make_member):
    make_member(first_name="Active", last_name="One", status="active")
    make_member(first_name="Purged", last_name="X", status="deleted")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/?status=all")
    assert b"Active" in response.content
    assert b"Purged" not in response.content


@pytest.mark.django_db
def test_member_list_search_by_first_name(client, coadmin_user, make_member):
    make_member(first_name="Idrissa", last_name="Saidou")
    make_member(first_name="Awa", last_name="Diallo")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/?q=Idrissa")
    assert b"Idrissa" in response.content
    assert b"Awa" not in response.content


@pytest.mark.django_db
def test_member_list_search_by_last_name(client, coadmin_user, make_member):
    make_member(first_name="Aaa", last_name="Yamoussa")
    make_member(first_name="Bbb", last_name="Diallo")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/?q=yamoussa")
    assert b"Yamoussa" in response.content
    assert b"Diallo" not in response.content


@pytest.mark.django_db
def test_member_list_search_by_city(client, coadmin_user, make_member):
    make_member(first_name="A", last_name="One", city="Niamey")
    make_member(first_name="B", last_name="Two", city="Cotonou")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/?q=cotonou")
    body = response.content.decode("utf-8")
    assert "B" in body and "Two" in body
    # 'A One' should not appear with Niamey in the list
    assert "Niamey" not in body or "A One" not in body


@pytest.mark.django_db
def test_member_list_search_by_username(client, coadmin_user, make_user, make_member):
    user = make_user(username="22790000111")
    make_member(user=user, first_name="Findable", last_name="ByPhone")
    other = make_user(username="22790000222")
    make_member(user=other, first_name="Hidden", last_name="One")
    client.force_login(coadmin_user)
    response = client.get("/gestion/membres/?q=22790000111")
    assert b"Findable" in response.content
    assert b"Hidden" not in response.content


@pytest.mark.django_db
def test_member_list_pagination(client, coadmin_user, make_member):
    """With >20 members, page 1 shows first 20, page 2 shows the rest."""
    for i in range(25):
        make_member(first_name=f"Member{i:02d}", last_name=f"X{i:02d}")
    client.force_login(coadmin_user)
    page1 = client.get("/gestion/membres/")
    assert b"Page 1 / 2" in page1.content
    page2 = client.get("/gestion/membres/?page=2")
    assert b"Page 2 / 2" in page2.content
