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
def test_profile_detail_renders_for_active_member(consenting_client, make_member):
    target = make_member(first_name="Fatou", last_name="Diallo", city="Niamey")
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert response.status_code == 200
    assert b"Fatou" in response.content
    assert b"Diallo" in response.content


@pytest.mark.django_db
def test_profile_detail_404_for_deleted(consenting_client, make_member):
    target = make_member(status="deleted")
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_profile_detail_404_for_suspended_to_non_admin(consenting_client, make_member):
    target = make_member(status="suspended")
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_profile_detail_200_for_suspended_to_admin(make_member, make_user):
    admin = make_user(is_staff=True, password="x")
    make_member(user=admin)
    ConsentRecord.objects.create(
        member=admin.member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    target = make_member(status="suspended")
    client = Client()
    client.login(username=admin.username, password="x")
    response = client.get(f"/membres/{target.slug}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_profile_detail_hides_email_when_show_email_false(
    consenting_client, make_member, make_user
):
    user = make_user(email="hidden@example.test")
    target = make_member(user=user, show_email=False)
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert b"hidden@example.test" not in response.content


@pytest.mark.django_db
def test_profile_detail_shows_email_when_show_email_true(consenting_client, make_member, make_user):
    user = make_user(email="visible@example.test")
    target = make_member(user=user, show_email=True)
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert b"visible@example.test" in response.content


@pytest.mark.django_db
def test_profile_detail_hides_city_when_show_city_false(consenting_client, make_member):
    target = make_member(city="Cotonou", show_city=False)
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert b"Cotonou" not in response.content


@pytest.mark.django_db
def test_profile_detail_includes_noindex(consenting_client, make_member):
    target = make_member()
    response = consenting_client.get(f"/membres/{target.slug}/")
    assert b'name="robots"' in response.content
    assert b"noindex" in response.content
