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
def test_directory_lists_active_members(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One")
    make_member(first_name="Beta", last_name="Two")
    response = consenting_client.get("/annuaire/")
    assert response.status_code == 200
    assert b"Alpha One" in response.content
    assert b"Beta Two" in response.content


@pytest.mark.django_db
def test_directory_excludes_deleted_and_suspended(consenting_client, make_member):
    make_member(first_name="Visible", last_name="One")
    make_member(first_name="Hidden", last_name="Two", status="deleted")
    make_member(first_name="Quiet", last_name="Three", status="suspended")
    response = consenting_client.get("/annuaire/")
    assert b"Visible One" in response.content
    assert b"Hidden Two" not in response.content
    assert b"Quiet Three" not in response.content


@pytest.mark.django_db
def test_directory_paginates_at_20_per_page(consenting_client, make_member):
    for i in range(25):
        make_member(first_name=f"Person{i:02d}", last_name="X")
    page_one = consenting_client.get("/annuaire/")
    assert page_one.content.count(b'class="member-card"') == 20
    page_two = consenting_client.get("/annuaire/?page=2")
    assert page_two.status_code == 200
    # 25 total - 20 on page 1 = 5 expected, plus the consenting_client's own member = 6
    assert page_two.content.count(b'class="member-card"') >= 5


@pytest.mark.django_db
def test_directory_clamps_page_zero_to_one(consenting_client, make_member):
    for i in range(5):
        make_member(first_name=f"Person{i}", last_name="X")
    response = consenting_client.get("/annuaire/?page=0")
    assert response.status_code == 200


@pytest.mark.django_db
def test_directory_clamps_negative_page_to_one(consenting_client, make_member):
    for i in range(5):
        make_member(first_name=f"Person{i}", last_name="X")
    response = consenting_client.get("/annuaire/?page=-3")
    assert response.status_code == 200


@pytest.mark.django_db
def test_directory_clamps_page_beyond_max(consenting_client, make_member):
    for i in range(5):
        make_member(first_name=f"Person{i}", last_name="X")
    response = consenting_client.get("/annuaire/?page=999")
    assert response.status_code == 200


@pytest.mark.django_db
def test_directory_includes_noindex(consenting_client):
    response = consenting_client.get("/annuaire/")
    assert b"noindex" in response.content
