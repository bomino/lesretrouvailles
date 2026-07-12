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
def test_search_matches_city(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One", city="Niamey")
    make_member(first_name="Beta", last_name="Two", city="Cotonou")
    response = consenting_client.get("/annuaire/?q=niamey")
    assert b"Alpha One" in response.content
    assert b"Beta Two" not in response.content


@pytest.mark.django_db
def test_search_matches_profession(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One", profession="Médecin")
    make_member(first_name="Beta", last_name="Two", profession="Enseignant")
    response = consenting_client.get("/annuaire/?q=medecin")
    assert b"Alpha One" in response.content
    assert b"Beta Two" not in response.content


@pytest.mark.django_db
def test_search_matches_country(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One", country="France")
    make_member(first_name="Beta", last_name="Two", country="Niger")
    response = consenting_client.get("/annuaire/?q=france")
    assert b"Alpha One" in response.content
    assert b"Beta Two" not in response.content


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


@pytest.mark.django_db
def test_search_empty_query_returns_all_active_members(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One")
    make_member(first_name="Beta", last_name="Two")
    response = consenting_client.get("/annuaire/?q=")
    assert b"Alpha One" in response.content
    assert b"Beta Two" in response.content


@pytest.mark.django_db
def test_search_query_with_only_whitespace_returns_all(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One")
    make_member(first_name="Beta", last_name="Two")
    response = consenting_client.get("/annuaire/?q=%20%20%20")
    assert b"Alpha One" in response.content
    assert b"Beta Two" in response.content


@pytest.mark.django_db
def test_search_query_with_percent_chars_does_not_break(consenting_client, make_member):
    """Postgres `%` is a LIKE wildcard. `Value(q)` must parameterize so a
    raw `%` in user input doesn't match every row or break the query."""
    make_member(first_name="Alpha", last_name="One")
    response = consenting_client.get("/annuaire/?q=%25%25%25%25")  # %%% URL-encoded
    assert response.status_code == 200
    # Literal '%' is not in any seeded name, so result should be empty.
    assert b"Alpha One" not in response.content


@pytest.mark.django_db
def test_search_query_with_sql_injection_attempt_is_safe(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One")
    # Classic injection attempt; ORM must parameterize.
    response = consenting_client.get("/annuaire/?q=%27%3B+DROP+TABLE+members_member%3B--")
    assert response.status_code == 200
    # Confirm the table still exists by re-querying.
    from members.models import Member

    assert Member.objects.filter(first_name="Alpha").exists()


@pytest.mark.django_db
def test_show_city_false_excludes_member_from_city_filter(consenting_client, make_member):
    """Privacy regression: the card and profile hide the city when
    show_city=False, but ?city=X filtered over ALL members — probing ~6
    plausible cities disclosed exactly what the toggle promised to hide."""
    hidden = make_member(first_name="Discret", city="Niamey", show_city=False, status="active")
    shown = make_member(first_name="Ouvert", city="Niamey", show_city=True, status="active")

    body = consenting_client.get("/annuaire/?city=Niamey").content.decode("utf-8")
    assert shown.first_name in body
    assert hidden.first_name not in body


@pytest.mark.django_db
def test_show_city_false_excludes_member_from_city_search(consenting_client, make_member):
    """Same inference via ?q= — search matched city_lc/country_lc for every
    member regardless of the flag."""
    hidden = make_member(first_name="Discret", city="Zinder", show_city=False, status="active")

    body = consenting_client.get("/annuaire/?q=Zinder").content.decode("utf-8")
    assert hidden.first_name not in body


@pytest.mark.django_db
def test_pagination_links_urlencode_filter_values(consenting_client, make_member):
    """The paginator hand-rolled '&{{k}}={{v}}' with HTML-escaping, not
    URL-encoding: q=M&M rendered '?page=2&q=M&amp;M', which the browser
    decodes to a truncated filter plus a bogus param."""
    for i in range(25):
        make_member(first_name=f"Paginated{i}", city="M&M", status="active")

    body = consenting_client.get("/annuaire/?city=M%26M").content.decode("utf-8")
    assert "page=2" in body, "sanity: the filtered result set must paginate"
    # HTML-escaped (&amp;) means the browser will decode it to a raw & and
    # truncate the filter; the value must be percent-encoded instead.
    assert "city=M&amp;M" not in body
    assert "city=M%26M" in body
