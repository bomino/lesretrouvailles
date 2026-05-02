import pytest
from bs4 import BeautifulSoup
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
def test_profile_edit_form_has_label_for_each_text_input(consenting_client):
    response = consenting_client.get("/profil/")
    soup = BeautifulSoup(response.content, "html.parser")
    text_inputs = soup.find_all("input", {"type": ["text", "email"]})
    label_for = {label.get("for") for label in soup.find_all("label")}
    for inp in text_inputs:
        if inp.get("type") == "hidden":
            continue
        assert inp.get("id") in label_for, f"Input {inp} has no associated <label>"


@pytest.mark.django_db
def test_directory_pagination_has_aria_label(consenting_client, make_member):
    for i in range(25):
        make_member(first_name=f"P{i}", last_name="X")
    response = consenting_client.get("/annuaire/")
    soup = BeautifulSoup(response.content, "html.parser")
    nav = soup.find("nav", {"aria-label": True})
    assert nav is not None


@pytest.mark.django_db
def test_directory_results_use_aria_live(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    response = consenting_client.get("/annuaire/")
    soup = BeautifulSoup(response.content, "html.parser")
    live = soup.find(attrs={"aria-live": True})
    assert live is not None


@pytest.mark.django_db
def test_avatar_initials_have_aria_label(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    response = consenting_client.get("/annuaire/")
    soup = BeautifulSoup(response.content, "html.parser")
    initials = soup.find(class_="avatar-initials")
    if initials is not None:
        assert initials.get("aria-label")
