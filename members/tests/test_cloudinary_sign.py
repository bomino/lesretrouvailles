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


@pytest.mark.django_db
def test_sign_endpoint_returns_400_when_user_has_no_member(make_user):
    """An authenticated user without a Member row (anomaly during P2 dev)
    must get a structured 400, not a 500 or successful sign for a stranger."""
    user = make_user(password="testpass123")
    # Deliberately do NOT create a Member for this user.
    client = Client()
    client.login(username=user.username, password="testpass123")
    response = client.post("/api/cloudinary/sign/")
    assert response.status_code == 400


@pytest.mark.django_db
def test_sign_endpoint_rate_limit_is_per_user_not_global(make_member, make_user):
    """Two different users each get their own 10/m budget. Verifies the
    decorator's `key='user'` is honored end-to-end."""
    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord

    def make_consenting(user_pw):
        user = make_user(password=user_pw)
        member = make_member(user=user)
        ConsentRecord.objects.create(
            member=member,
            charter_version=CHARTER_CURRENT_VERSION,
            ip_address="127.0.0.1",
        )
        c = Client()
        c.login(username=user.username, password=user_pw)
        return c

    # User A: burn the entire budget.
    a = make_consenting("aaa-pw")
    for _ in range(10):
        assert a.post("/api/cloudinary/sign/").status_code == 200
    # User A is now rate-limited.
    assert a.post("/api/cloudinary/sign/").status_code == 429

    # User B starts fresh — must NOT be affected by A's budget.
    b = make_consenting("bbb-pw")
    assert b.post("/api/cloudinary/sign/").status_code == 200
