import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def member_client(make_member, make_user):
    user = make_user(password="testpass123")
    member = make_member(user=user)
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    client.user = user
    return client


@pytest.mark.django_db
def test_logged_in_member_without_consent_is_redirected_to_charter(member_client):
    response = member_client.get("/admin/")
    assert response.status_code == 302
    assert "/charte/" in response["Location"]
    assert "next=" in response["Location"]


@pytest.mark.django_db
def test_logged_in_member_with_current_consent_passes(member_client):
    ConsentRecord.objects.create(
        member=member_client.member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    # Pre-warm the session: middleware will record the consent in session on first hit
    response = member_client.get("/admin/")
    # /admin/ requires staff but middleware should NOT bounce to /charte/
    assert "/charte/" not in response.get("Location", "")


@pytest.mark.django_db
def test_charter_path_is_skipped_by_consent_middleware(member_client):
    response = member_client.get("/charte/")
    # Path itself isn't implemented yet (Task 12), but middleware must not loop
    assert response.status_code in (200, 404, 405)


@pytest.mark.django_db
def test_logout_path_is_skipped_by_consent_middleware(member_client):
    response = member_client.post("/accounts/logout/")
    # We just want to assert no /charte/ redirect
    assert "/charte/" not in response.get("Location", "")


@pytest.mark.django_db
def test_consent_state_is_cached_in_session(member_client):
    ConsentRecord.objects.create(
        member=member_client.member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    member_client.get("/admin/")
    session = member_client.session
    assert session.get("consent_ok_for") == CHARTER_CURRENT_VERSION
