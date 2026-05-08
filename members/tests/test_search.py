"""Tests for members.search.search_members and the directory empty-state.

The existing single-token / accent-insensitive / facet-filter behavior is
already covered by `test_views_directory_search.py`. These tests focus on
the new behaviors added in P8: multi-token AND, year-token expansion,
trigram fallback, no-results AuditLog write, and empty-state suggestions.
"""

from __future__ import annotations

import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import AuditLog, ConsentRecord, Member
from members.search import search_members


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


# ---------- search_members function ----------


@pytest.mark.django_db
def test_search_empty_query_returns_unchanged_qs(make_member):
    make_member(first_name="Alpha", last_name="One")
    qs = Member.objects.filter(status="active")
    result = search_members(qs, "")
    assert result.count() == 1


@pytest.mark.django_db
def test_search_whitespace_query_returns_unchanged_qs(make_member):
    make_member(first_name="Alpha", last_name="One")
    qs = Member.objects.filter(status="active")
    result = search_members(qs, "   ")
    assert result.count() == 1


@pytest.mark.django_db
def test_search_single_token_substring(make_member):
    make_member(first_name="Idrissa", last_name="Saidou", city="Niamey")
    make_member(first_name="Beta", last_name="Other", city="Cotonou")
    qs = Member.objects.filter(status="active")
    result = search_members(qs, "idris")
    names = [m.first_name for m in result]
    assert "Idrissa" in names
    assert "Beta" not in names


@pytest.mark.django_db
def test_search_multitoken_and_combines_blocks(make_member):
    """Both tokens must match independently across the union of the six fields."""
    make_member(first_name="Alpha", last_name="X", city="Niamey", profession="Médecin")
    make_member(first_name="Beta", last_name="Y", city="Niamey", profession="Enseignant")
    make_member(first_name="Gamma", last_name="Z", city="Cotonou", profession="Médecin")
    qs = Member.objects.filter(status="active")
    result = search_members(qs, "niamey medecin")
    names = {m.first_name for m in result}
    assert names == {"Alpha"}


@pytest.mark.django_db
def test_search_year_token_expands_to_years_attended(make_member):
    """A pure-numeric token in 1980-1985 also tries years_attended__contains
    inside its block, so '1983 niamey' finds members in 1983 + Niamey."""
    make_member(
        first_name="Alpha",
        last_name="X",
        years_attended=[1983, 1984],
        city="Niamey",
    )
    make_member(
        first_name="Beta",
        last_name="Y",
        years_attended=[1985],
        city="Niamey",
    )
    make_member(
        first_name="Gamma",
        last_name="Z",
        years_attended=[1983],
        city="Cotonou",
    )
    qs = Member.objects.filter(status="active")
    result = search_members(qs, "1983 niamey")
    names = {m.first_name for m in result}
    assert names == {"Alpha"}


@pytest.mark.django_db
def test_search_year_token_alone_matches_year(make_member):
    make_member(first_name="Alpha", last_name="X", years_attended=[1980, 1981])
    make_member(first_name="Beta", last_name="Y", years_attended=[1984])
    qs = Member.objects.filter(status="active")
    result = search_members(qs, "1981")
    names = {m.first_name for m in result}
    assert names == {"Alpha"}


@pytest.mark.django_db
def test_search_year_out_of_range_does_not_expand(make_member):
    make_member(first_name="Alpha", last_name="X", years_attended=[1980])
    qs = Member.objects.filter(status="active")
    # 1999 is numeric but outside VALID_YEARS, so the token is treated as
    # substring only (and won't match Alpha's name/city/etc).
    result = search_members(qs, "1999")
    assert result.count() == 0


@pytest.mark.django_db
def test_search_multitoken_no_match_falls_back_to_trigram(make_member):
    """Typo 'Naimey' (transposition of 'Niamey') should still surface
    Niamey-based members via trigram similarity fallback."""
    make_member(first_name="Alpha", last_name="One", city="Niamey")
    make_member(first_name="Beta", last_name="Two", city="Cotonou")
    qs = Member.objects.filter(status="active")
    result = list(search_members(qs, "Naimey"))
    names = {m.first_name for m in result}
    assert "Alpha" in names, "trigram fallback should surface Niamey-based Alpha for query 'Naimey'"


@pytest.mark.django_db
def test_search_trigram_skipped_when_token_too_short(make_member):
    """Tokens shorter than 4 chars don't trigger trigram fallback —
    similarity noise is too high at that length."""
    make_member(first_name="Alpha", last_name="One", city="Niamey")
    qs = Member.objects.filter(status="active")
    # 'xyz' is 3 chars and matches no field; result should be empty,
    # NOT a trigram-fuzzy match.
    result = search_members(qs, "xyz")
    assert result.count() == 0


@pytest.mark.django_db
def test_search_trigram_skipped_when_only_numeric_token(make_member):
    """Pure-numeric tokens never drive the trigram fallback (we use the
    longest non-numeric token; if there is none, no fallback)."""
    make_member(first_name="Alpha", last_name="One", years_attended=[1980])
    qs = Member.objects.filter(status="active")
    result = search_members(qs, "9999")
    assert result.count() == 0


# ---------- /annuaire/ end-to-end (view + template) ----------


@pytest.mark.django_db
def test_annuaire_multitoken_search(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="X", years_attended=[1983], city="Niamey")
    make_member(first_name="Beta", last_name="Y", years_attended=[1985], city="Niamey")
    response = consenting_client.get("/annuaire/?q=1983+niamey")
    assert response.status_code == 200
    assert b"Alpha X" in response.content
    assert b"Beta Y" not in response.content


@pytest.mark.django_db
def test_annuaire_trigram_fallback_for_typo(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One", city="Niamey")
    make_member(first_name="Beta", last_name="Two", city="Cotonou")
    response = consenting_client.get("/annuaire/?q=Naimey")
    assert response.status_code == 200
    # Containment, not rank — pg_trgm semantics are implementation-defined.
    assert b"Alpha One" in response.content


@pytest.mark.django_db
def test_annuaire_no_results_writes_auditlog(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One", city="Niamey")
    assert AuditLog.objects.filter(action="directory.query.no_results").count() == 0
    response = consenting_client.get("/annuaire/?q=zzzzznosuchwordzzz")
    assert response.status_code == 200
    rows = AuditLog.objects.filter(action="directory.query.no_results")
    assert rows.count() == 1
    row = rows.first()
    assert row.metadata.get("q") == "zzzzznosuchwordzzz"
    assert row.metadata.get("actor_username") == consenting_client.member.user.username


@pytest.mark.django_db
def test_annuaire_no_results_renders_empty_state_suggestions(consenting_client):
    response = consenting_client.get("/annuaire/?q=zzzzznosuchwordzzz")
    assert response.status_code == 200
    # The hardcoded suggestion chips: at least Niamey + Promotion 1983 + "Tous les membres".
    body = response.content.decode("utf-8")
    assert "Niamey" in body
    assert "Promotion 1983" in body
    assert "Tous les membres" in body


@pytest.mark.django_db
def test_annuaire_empty_filters_zero_members_does_not_log(consenting_client):
    """When there are zero active members AND no filter was applied, don't
    log — that's not a no-results query, that's an empty platform."""
    consenting_client.get("/annuaire/")
    assert AuditLog.objects.filter(action="directory.query.no_results").count() == 0


@pytest.mark.django_db
def test_annuaire_results_present_does_not_log(consenting_client, make_member):
    make_member(first_name="Alpha", last_name="One", city="Niamey")
    consenting_client.get("/annuaire/?q=alpha")
    assert AuditLog.objects.filter(action="directory.query.no_results").count() == 0


@pytest.mark.django_db
def test_annuaire_facet_only_no_results_logs(consenting_client, make_member):
    """A facet filter (city=Made-up-place) returning zero is also worth
    logging — it tells us users are looking for places we don't index."""
    make_member(first_name="Alpha", last_name="One", city="Niamey")
    consenting_client.get("/annuaire/?city=Atlantis")
    rows = AuditLog.objects.filter(action="directory.query.no_results")
    assert rows.count() == 1
    assert rows.first().metadata.get("city") == "Atlantis"
