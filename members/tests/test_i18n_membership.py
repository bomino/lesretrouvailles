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
    return client


@pytest.mark.django_db
def test_directory_renders_french_strings(consenting_client):
    response = consenting_client.get("/annuaire/")
    body = response.content.decode("utf-8")
    assert "Annuaire" in body
    assert "Rechercher" in body or "recherch" in body.lower()


@pytest.mark.django_db
def test_profile_edit_renders_french_strings(consenting_client):
    response = consenting_client.get("/profil/")
    body = response.content.decode("utf-8")
    assert "Mon profil" in body
    assert "Enregistrer" in body


@pytest.mark.django_db
def test_charter_renders_french_accept_button(consenting_client):
    response = consenting_client.get("/charte/")
    body = response.content.decode("utf-8")
    assert "J'accepte" in body
