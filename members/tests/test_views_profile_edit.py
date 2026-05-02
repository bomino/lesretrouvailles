import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def consenting_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.mark.django_db
def test_profile_edit_get_renders_form(consenting_client):
    response = consenting_client.get("/profil/")
    assert response.status_code == 200
    assert b'name="nickname"' in response.content
    assert b'name="city"' in response.content
    assert b'name="profession"' in response.content


@pytest.mark.django_db
def test_profile_edit_does_not_expose_locked_fields(consenting_client):
    response = consenting_client.get("/profil/")
    body = response.content.decode("utf-8")
    assert 'name="first_name"' not in body
    assert 'name="last_name"' not in body
    assert 'name="years_attended"' not in body
    assert 'name="classes"' not in body
    assert 'name="status"' not in body


@pytest.mark.django_db
def test_profile_edit_post_updates_editable_fields(consenting_client):
    response = consenting_client.post(
        "/profil/",
        {
            "nickname": "Idi",
            "city": "Cotonou",
            "country": "Bénin",
            "profession": "Enseignant",
            "show_email": "on",
            "show_whatsapp": "",  # unchecked
            "show_city": "on",
            "digest_weekly": "",
            "in_memoriam_alerts": "on",
            "event_alerts": "",
            "tag_alerts": "on",
            "data_saver": "",
        },
    )
    assert response.status_code == 302
    consenting_client.member.refresh_from_db()
    assert consenting_client.member.nickname == "Idi"
    assert consenting_client.member.city == "Cotonou"
    assert consenting_client.member.country == "Bénin"
    assert consenting_client.member.show_whatsapp is False
    assert consenting_client.member.preferences.digest_weekly is False


@pytest.mark.django_db
def test_profile_edit_post_does_not_change_locked_fields(consenting_client):
    member = consenting_client.member
    original_first = member.first_name
    response = consenting_client.post(
        "/profil/",
        {
            "first_name": "ATTACK",
            "nickname": "Idi",
            "city": "Cotonou",
            "country": "Niger",
            "profession": "",
            "show_email": "on",
            "show_whatsapp": "on",
            "show_city": "on",
            "digest_weekly": "",
            "in_memoriam_alerts": "on",
            "event_alerts": "",
            "tag_alerts": "on",
            "data_saver": "",
        },
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.first_name == original_first


@pytest.mark.django_db
def test_profile_edit_requires_login():
    response = Client().get("/profil/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
