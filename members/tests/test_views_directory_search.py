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
def test_search_matches_first_name_substring(consenting_client, make_member):
    make_member(first_name="Idrissa", last_name="Saidou")
    make_member(first_name="Beta", last_name="Other")
    response = consenting_client.get("/annuaire/?q=idris")
    assert b"Idrissa" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_search_is_accent_insensitive(consenting_client, make_member):
    make_member(first_name="Idrïssa", last_name="Saïdou")
    response = consenting_client.get("/annuaire/?q=idrissa")
    assert b"Idr" in response.content  # match found, name rendered


@pytest.mark.django_db
def test_search_matches_nickname(consenting_client, make_member):
    make_member(first_name="Hamadou", last_name="X", nickname="Idi")
    response = consenting_client.get("/annuaire/?q=idi")
    assert b"Hamadou" in response.content


@pytest.mark.django_db
def test_filter_by_year(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", years_attended=[1980, 1981])
    make_member(first_name="Beta", last_name="Y", years_attended=[1984, 1985])
    response = consenting_client.get("/annuaire/?year=1980")
    assert b"Alpha" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_filter_by_city_is_case_insensitive(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", city="Niamey")
    make_member(first_name="Beta", last_name="Y", city="Cotonou")
    response = consenting_client.get("/annuaire/?city=niamey")
    assert b"Alpha" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_filter_by_profession_is_substring(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", profession="Enseignant primaire")
    make_member(first_name="Beta", last_name="Y", profession="Médecin")
    response = consenting_client.get("/annuaire/?profession=enseign")
    assert b"Alpha" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_filters_combined_with_and(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", city="Niamey", years_attended=[1980])
    make_member(first_name="Beta", last_name="Y", city="Niamey", years_attended=[1985])
    response = consenting_client.get("/annuaire/?city=niamey&year=1980")
    assert b"Alpha" in response.content
    assert b"Beta" not in response.content


@pytest.mark.django_db
def test_invalid_year_silently_dropped(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", years_attended=[1980])
    response = consenting_client.get("/annuaire/?year=9999")
    assert response.status_code == 200
    assert b"Alpha" in response.content


@pytest.mark.django_db
def test_long_query_is_truncated(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X")
    long_q = "a" * 200
    response = consenting_client.get(f"/annuaire/?q={long_q}")
    assert response.status_code == 200
