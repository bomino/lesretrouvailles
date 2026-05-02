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
def test_sign_endpoint_requires_login():
    response = Client().post("/api/cloudinary/sign/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_sign_endpoint_returns_signature_pinned_to_member_folder(consenting_client):
    response = consenting_client.post("/api/cloudinary/sign/", {"folder": "ATTACK/path"})
    assert response.status_code == 200
    body = response.json()
    assert body["folder"] == f"members/{consenting_client.member.slug}/"
    assert body["signature"]
    assert body["timestamp"]
    assert body["max_file_size"] == 5 * 1024 * 1024
    assert body["allowed_formats"] == ["jpg", "jpeg", "png", "webp"]


@pytest.mark.django_db
def test_sign_endpoint_rate_limit_kicks_in_after_10_per_min(consenting_client, settings):
    # The limit is 10/m/user. The 11th request gets 429.
    for _ in range(10):
        ok = consenting_client.post("/api/cloudinary/sign/")
        assert ok.status_code == 200
    blocked = consenting_client.post("/api/cloudinary/sign/")
    assert blocked.status_code == 429
