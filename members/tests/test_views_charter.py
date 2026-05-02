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
    return client


@pytest.mark.django_db
def test_charter_get_renders_markdown_for_logged_in_member(member_client):
    response = member_client.get("/charte/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Charte de la Communauté" in body
    assert "<h1" in body  # Markdown rendered to HTML


@pytest.mark.django_db
def test_charter_post_records_consent_and_redirects(member_client):
    response = member_client.post("/charte/?next=/admin/")
    assert response.status_code == 302
    assert response["Location"] == "/admin/"
    rec = ConsentRecord.objects.get(member=member_client.member)
    assert rec.charter_version == CHARTER_CURRENT_VERSION
    assert rec.ip_address == "127.0.0.1"


@pytest.mark.django_db
def test_charter_post_default_redirect_is_root(member_client):
    response = member_client.post("/charte/")
    assert response.status_code == 302
    assert response["Location"] == "/"


@pytest.mark.django_db
def test_charter_post_requires_login():
    response = Client().post("/charte/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_charter_get_includes_noindex_meta(member_client):
    response = member_client.get("/charte/")
    assert b'<meta name="robots" content="noindex"' in response.content


@pytest.mark.django_db
def test_charter_post_blocks_external_redirect(member_client):
    response = member_client.post("/charte/?next=https://evil.example.com/path")
    assert response.status_code == 302
    assert response["Location"] == "/"
