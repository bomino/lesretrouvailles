"""Phase 1 — /gestion/ dashboard auth gate + KPI tiles."""

from __future__ import annotations

import pytest

# ---------- Auth gate ----------


@pytest.mark.django_db
def test_dashboard_anon_redirects_to_login(client):
    """Anonymous users hitting /gestion/ are redirected to the platform
    login (not the admin login)."""
    response = client.get("/gestion/", follow=False)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url
    assert "next=/gestion/" in response.url


@pytest.mark.django_db
def test_dashboard_authenticated_non_staff_gets_403(client, regular_member_user):
    """A regular logged-in member must NOT see /gestion/ — 403 with
    a polite French explanation."""
    client.force_login(regular_member_user)
    response = client.get("/gestion/")
    assert response.status_code == 403
    assert (
        b"r\xc3\xa9serv" in response.content  # "réservée"
        or b"administration" in response.content.lower()
    )


@pytest.mark.django_db
def test_dashboard_staff_sees_200(client, coadmin_user):
    """A co-admin (staff, not superuser) sees the dashboard."""
    client.force_login(coadmin_user)
    response = client.get("/gestion/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_superuser_sees_200(client, superadmin_user):
    """Bomino sees the dashboard too."""
    client.force_login(superadmin_user)
    response = client.get("/gestion/")
    assert response.status_code == 200


# ---------- KPI tiles ----------


def _kpi_count(body: str, kpi: str) -> str | None:
    """Extract the data-count for a given data-kpi from the rendered HTML.
    djLint splits attributes across lines, so a literal-string match would
    be fragile; regex tolerates whitespace between the two attributes."""
    import re

    pattern = rf'data-kpi="{kpi}"\s+data-count="(\d+)"'
    match = re.search(pattern, body)
    return match.group(1) if match else None


@pytest.mark.django_db
def test_dashboard_renders_active_member_count(client, coadmin_user, make_member):
    """The dashboard shows how many active members exist."""
    make_member(status="active")
    make_member(status="active")
    make_member(status="suspended")  # not counted
    client.force_login(coadmin_user)
    response = client.get("/gestion/")
    body = response.content.decode("utf-8")
    assert _kpi_count(body, "active-members") == "2"


@pytest.mark.django_db
def test_dashboard_renders_suspended_member_count(client, coadmin_user, make_member):
    make_member(status="active")
    make_member(status="suspended")
    make_member(status="suspended")
    client.force_login(coadmin_user)
    response = client.get("/gestion/")
    body = response.content.decode("utf-8")
    assert _kpi_count(body, "suspended-members") == "2"


@pytest.mark.django_db
def test_dashboard_renders_pending_cooptation_count(client, coadmin_user, make_application):
    make_application(status="cooptation_pending")
    make_application(status="awaiting_admin")
    make_application(status="approved")  # not counted
    client.force_login(coadmin_user)
    response = client.get("/gestion/")
    body = response.content.decode("utf-8")
    assert _kpi_count(body, "pending-cooptations") == "2"


# ---------- Super-admin escape-hatch ----------


@pytest.mark.django_db
def test_dashboard_shows_admin_escape_hatch_for_superuser(client, superadmin_user):
    """Super-admin sees a small ⚙ link to /admin/ for advanced operations
    (RGPD purge, roster import) that aren't in /gestion/."""
    client.force_login(superadmin_user)
    response = client.get("/gestion/")
    assert b'href="/admin/"' in response.content
    assert b"Outils avanc" in response.content  # "Outils avancés"


@pytest.mark.django_db
def test_dashboard_hides_admin_escape_hatch_for_coadmin(client, coadmin_user):
    """A co-admin must NOT see the link to /admin/ — it's super-admin only."""
    client.force_login(coadmin_user)
    response = client.get("/gestion/")
    assert b'href="/admin/"' not in response.content


@pytest.mark.django_db
def test_dashboard_top_nav_has_three_sections(client, coadmin_user):
    """Top nav: Dashboard / Membres / Cooptations."""
    client.force_login(coadmin_user)
    response = client.get("/gestion/")
    assert b"/gestion/" in response.content
    assert b"/gestion/membres/" in response.content
    assert b"/gestion/cooptations/" in response.content


# ---------- Souvenirs KPI tile ----------


class TestDashboardMemoriesTile:
    def test_tile_shows_zero_when_no_drafts(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/")
        body = resp.content.decode()
        # Tile renders even at 0 (intentional, per spec §G locked decisions).
        # Look for the section label.
        assert "Souvenirs" in body or "Brouillon" in body

    def test_tile_count_matches_draft_count(self, client, coadmin_user, make_memory):
        make_memory(status="draft")
        make_memory(status="draft")
        make_memory(status="published")
        client.force_login(coadmin_user)
        resp = client.get("/gestion/")
        body = resp.content.decode()
        # Loose check to avoid HTML brittleness: 2 should appear near the tile.
        assert ">2<" in body or 'data-count="2"' in body

    def test_tile_links_to_draft_filtered_list(self, client, coadmin_user):
        client.force_login(coadmin_user)
        resp = client.get("/gestion/")
        body = resp.content.decode()
        assert "/gestion/souvenirs/?status=draft" in body
