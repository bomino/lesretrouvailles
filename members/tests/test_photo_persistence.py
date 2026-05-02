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
def test_photo_persists_when_public_id_in_correct_folder(consenting_client):
    member = consenting_client.member
    new_id = f"members/{member.slug}/photo_xyz"
    response = consenting_client.post(
        "/profil/",
        {
            "nickname": "",
            "city": "Niamey",
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
            "photo_public_id": new_id,
        },
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.photo_public_id == new_id


@pytest.mark.django_db
def test_photo_rejected_when_public_id_outside_member_folder(consenting_client):
    response = consenting_client.post(
        "/profil/",
        {
            "nickname": "",
            "city": "Niamey",
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
            "photo_public_id": "evil/path/photo",
        },
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_old_photo_deleted_on_replacement(consenting_client, monkeypatch):
    from alumni.cloudinary import FakeCloudinary
    from members import views as members_views

    member = consenting_client.member
    member.photo_public_id = f"members/{member.slug}/old_photo"
    member.save()

    fake = FakeCloudinary()
    monkeypatch.setattr(members_views, "get_client", lambda: fake)

    new_id = f"members/{member.slug}/new_photo"
    consenting_client.post(
        "/profil/",
        {
            "nickname": "",
            "city": "Niamey",
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
            "photo_public_id": new_id,
        },
    )
    member.refresh_from_db()
    assert member.photo_public_id == new_id
    assert f"members/{member.slug}/old_photo" in fake.delete_calls
