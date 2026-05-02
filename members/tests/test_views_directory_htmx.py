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
def test_full_response_extends_base_template(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    response = consenting_client.get("/annuaire/")
    assert b"<html" in response.content


@pytest.mark.django_db
def test_htmx_response_returns_partial_only(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    response = consenting_client.get("/annuaire/", HTTP_HX_REQUEST="true")
    assert b"<html" not in response.content
    assert b"member-card" in response.content


@pytest.mark.django_db
def test_htmx_response_respects_filters(consenting_client, make_member):
    make_member(first_name="Idrissa", last_name="X")
    make_member(first_name="Beta", last_name="Y")
    response = consenting_client.get("/annuaire/?q=idris", HTTP_HX_REQUEST="true")
    assert b"Idrissa" in response.content
    assert b"Beta" not in response.content
