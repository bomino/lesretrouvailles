"""Phase 2 — /gestion/membres/<slug>/modifier/ edit form."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_member_edit_anon_redirects(client, make_member):
    member = make_member()
    response = client.get(f"/gestion/membres/{member.slug}/modifier/", follow=False)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_member_edit_non_staff_blocked(client, regular_member_user, make_member):
    member = make_member()
    client.force_login(regular_member_user)
    response = client.get(f"/gestion/membres/{member.slug}/modifier/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_member_edit_get_renders_form_prefilled(client, coadmin_user, make_member):
    member = make_member(first_name="Idrissa", city="Niamey")
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/modifier/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'value="Idrissa"' in body
    assert 'value="Niamey"' in body


@pytest.mark.django_db
def test_member_edit_post_updates_basic_fields(client, coadmin_user, make_member):
    member = make_member(
        first_name="Old",
        last_name="Name",
        years_attended=[1980, 1981],
        classes=["6e"],
        city="OldCity",
        country="Niger",
    )
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/modifier/",
        {
            "first_name": "New",
            "last_name": "Name",
            "nickname": "",
            "years_attended": "1980,1981,1982",
            "classes": "6e,5e",
            "city": "NewCity",
            "country": "Niger",
            "profession": "",
            "email": member.user.email,
        },
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.first_name == "New"
    assert member.years_attended == [1980, 1981, 1982]
    assert member.classes == ["6e", "5e"]
    assert member.city == "Newcity"  # Member.save() title-cases


@pytest.mark.django_db
def test_member_edit_post_updates_email_on_user(client, coadmin_user, make_member):
    member = make_member()
    old_email = member.user.email
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/modifier/",
        {
            "first_name": member.first_name,
            "last_name": member.last_name,
            "nickname": member.nickname,
            "years_attended": ",".join(str(y) for y in member.years_attended),
            "classes": ",".join(member.classes),
            "city": member.city,
            "country": member.country,
            "profession": member.profession,
            "email": "newemail@example.test",
        },
    )
    assert response.status_code == 302
    member.user.refresh_from_db()
    assert member.user.email == "newemail@example.test"
    assert member.user.email != old_email


@pytest.mark.django_db
def test_member_edit_post_writes_audit_with_changed_fields(client, coadmin_user, make_member):
    from members.models import AuditLog

    member = make_member(first_name="Old", city="Niamey")
    client.force_login(coadmin_user)
    client.post(
        f"/gestion/membres/{member.slug}/modifier/",
        {
            "first_name": "New",
            "last_name": member.last_name,
            "nickname": member.nickname,
            "years_attended": ",".join(str(y) for y in member.years_attended),
            "classes": ",".join(member.classes),
            "city": "Cotonou",
            "country": member.country,
            "profession": member.profession,
            "email": member.user.email,
        },
    )
    log = AuditLog.objects.filter(
        action="gestion.member.edited",
        target_id=str(member.pk),
    ).first()
    assert log is not None
    assert log.actor == coadmin_user
    assert "first_name" in log.metadata.get("changed_fields", [])
    assert "city" in log.metadata.get("changed_fields", [])


@pytest.mark.django_db
def test_member_edit_post_no_change_writes_no_audit(client, coadmin_user, make_member):
    """Submitting the form without changing anything should NOT create an
    audit row — keeps the log readable."""
    from members.models import AuditLog

    member = make_member()
    client.force_login(coadmin_user)
    client.post(
        f"/gestion/membres/{member.slug}/modifier/",
        {
            "first_name": member.first_name,
            "last_name": member.last_name,
            "nickname": member.nickname,
            "years_attended": ",".join(str(y) for y in member.years_attended),
            "classes": ",".join(member.classes),
            "city": member.city,
            "country": member.country,
            "profession": member.profession,
            "email": member.user.email,
        },
    )
    assert (
        AuditLog.objects.filter(action="gestion.member.edited", target_id=str(member.pk)).count()
        == 0
    )


@pytest.mark.django_db
def test_member_edit_rejects_bad_year(client, coadmin_user, make_member):
    member = make_member()
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/modifier/",
        {
            "first_name": member.first_name,
            "last_name": member.last_name,
            "nickname": "",
            "years_attended": "1979,1980",  # 1979 out of range
            "classes": "6e",
            "city": member.city,
            "country": member.country,
            "profession": "",
            "email": member.user.email,
        },
    )
    # Form re-rendered with error, no redirect
    assert response.status_code == 200
    assert b"1979" in response.content


@pytest.mark.django_db
def test_member_edit_rejects_bad_class(client, coadmin_user, make_member):
    member = make_member()
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/modifier/",
        {
            "first_name": member.first_name,
            "last_name": member.last_name,
            "nickname": "",
            "years_attended": "1980",
            "classes": "2nde",  # high school grade — out of range
            "city": member.city,
            "country": member.country,
            "profession": "",
            "email": member.user.email,
        },
    )
    assert response.status_code == 200
    assert b"2nde" in response.content
