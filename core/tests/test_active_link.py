"""Tests for the `active_link` template tag library.

The library exposes two simple_tags used across the desktop navbar,
mobile dropdown, and gestion subnav to mark the current page:
- `{% active_class prefix %}` returns a CSS class string when
  request.path matches the prefix (prefix-match by default, exact
  match when called with `exact=True`).
- `{% active_aria prefix %}` returns ` aria-current="page"` as a
  SafeString when active, else empty.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import RequestFactory


def _render(tag_args: str, *, path: str) -> str:
    template = Template("{% load active_link %}" + tag_args)
    rf = RequestFactory()
    return template.render(Context({"request": rf.get(path)}))


class TestActiveClass:
    def test_prefix_match_returns_active_class(self):
        out = _render("{% active_class '/annuaire/' %}", path="/annuaire/")
        assert "bg-base-200" in out
        assert "text-tertiary" in out
        assert "font-medium" in out

    def test_prefix_match_includes_subpaths(self):
        # /annuaire/<id>/ should mark Annuaire as active.
        out = _render("{% active_class '/annuaire/' %}", path="/annuaire/123/")
        assert "bg-base-200" in out

    def test_no_match_returns_empty(self):
        out = _render("{% active_class '/annuaire/' %}", path="/souvenirs/")
        assert out.strip() == ""

    def test_exact_match_requires_equal_path(self):
        out_root = _render("{% active_class '/gestion/' exact=True %}", path="/gestion/")
        assert "bg-base-200" in out_root
        out_subpath = _render("{% active_class '/gestion/' exact=True %}", path="/gestion/membres/")
        assert out_subpath.strip() == ""

    def test_custom_active_class_overrides_default(self):
        out = _render(
            "{% active_class '/annuaire/' active='custom-active' %}",
            path="/annuaire/",
        )
        assert out.strip() == "custom-active"

    def test_no_request_in_context_returns_empty(self):
        template = Template("{% load active_link %}{% active_class '/annuaire/' %}")
        rendered = template.render(Context({}))
        assert rendered.strip() == ""

    def test_anonymous_path_no_match(self):
        # Path that doesn't match any prefix → empty.
        out = _render("{% active_class '/gestion/' %}", path="/")
        assert out.strip() == ""


class TestActiveAria:
    def test_active_returns_aria_current_page(self):
        out = _render("{% active_aria '/annuaire/' %}", path="/annuaire/")
        assert 'aria-current="page"' in out

    def test_inactive_returns_empty(self):
        out = _render("{% active_aria '/annuaire/' %}", path="/souvenirs/")
        assert out.strip() == ""

    def test_exact_match_supported(self):
        out_root = _render("{% active_aria '/gestion/' exact=True %}", path="/gestion/")
        assert 'aria-current="page"' in out_root
        out_subpath = _render("{% active_aria '/gestion/' exact=True %}", path="/gestion/membres/")
        assert out_subpath.strip() == ""

    def test_no_request_returns_empty(self):
        template = Template("{% load active_link %}{% active_aria '/annuaire/' %}")
        rendered = template.render(Context({}))
        assert rendered.strip() == ""

    def test_safe_string_so_attribute_renders_unescaped(self):
        # When active, the returned string must be marked safe so the
        # quotes around "page" aren't HTML-escaped into &quot;.
        out = _render("{% active_aria '/annuaire/' %}", path="/annuaire/")
        assert "&quot;" not in out
        assert 'aria-current="page"' in out


# --------- Integration: templates wire the tags correctly ---------


def _login_as_member(client):
    """Helper: create an authenticated member with charter consent + log in."""
    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="navactive@example.test",
        email="navactive@example.test",
        password="x",
    )
    member = Member.objects.create(
        user=user,
        first_name="Nav",
        last_name="Active",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    ConsentRecord.objects.create(
        member=member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    client.force_login(user)
    return user, member


def _login_as_coadmin(client):
    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="22790000801",
        email="coadmin_navactive@example.test",
        password="x",
        is_staff=True,
        is_superuser=False,
    )
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_annuaire_nav_link_is_active_on_annuaire_page(client):
    _login_as_member(client)
    response = client.get("/annuaire/")
    body = response.content.decode("utf-8")
    # The Annuaire link should carry aria-current="page". Desktop +
    # mobile each render their own copy, so expect ≥ 2 occurrences.
    assert body.count('aria-current="page"') >= 2
    # Active CSS class should be present.
    assert "bg-base-200" in body


@pytest.mark.django_db
def test_souvenirs_does_not_mark_annuaire_active(client):
    _login_as_member(client)
    response = client.get("/souvenirs/")
    body = response.content.decode("utf-8")
    # Find positions: aria-current must appear, but ONLY on /souvenirs/ links.
    assert 'aria-current="page"' in body
    # The Annuaire <a> should NOT have aria-current on its href.
    # Crude check: split on /annuaire/" and verify no aria-current in
    # the following whitespace-only run before the closing >.
    parts = body.split('href="/annuaire/"')
    for piece in parts[1:]:
        head = piece.split(">", 1)[0]
        assert "aria-current" not in head, "Annuaire link wrongly marked active on /souvenirs/"


@pytest.mark.django_db
def test_gestion_dashboard_link_active_only_on_dashboard(client):
    """Tableau de bord uses exact-match — it should NOT stay active when
    the user is on /gestion/membres/ or other gestion subpages."""
    _login_as_coadmin(client)

    # On /gestion/ — Tableau de bord IS active.
    resp_dashboard = client.get("/gestion/")
    body = resp_dashboard.content.decode("utf-8")
    # "Tableau de bord" appears in both the page <h1> AND the subnav link.
    # rfind locates the subnav link (later in source order).
    tableau_idx = body.rfind("Tableau de bord")
    assert tableau_idx != -1
    a_open_idx = body.rfind("<a ", 0, tableau_idx)
    a_close_idx = body.find(">", a_open_idx)
    tableau_a_tag = body[a_open_idx:a_close_idx]
    assert 'aria-current="page"' in tableau_a_tag

    # On /gestion/membres/ — Tableau de bord is NOT active.
    resp_membres = client.get("/gestion/membres/")
    body = resp_membres.content.decode("utf-8")
    tableau_idx = body.rfind("Tableau de bord")
    a_open_idx = body.rfind("<a ", 0, tableau_idx)
    a_close_idx = body.find(">", a_open_idx)
    tableau_a_tag = body[a_open_idx:a_close_idx]
    assert "aria-current" not in tableau_a_tag


@pytest.mark.django_db
def test_gestion_membres_link_active_on_membres_page(client):
    _login_as_coadmin(client)
    response = client.get("/gestion/membres/")
    body = response.content.decode("utf-8")
    # The Membres link in the gestion subnav must be active.
    a_idx = body.find('href="/gestion/membres/"')
    assert a_idx != -1
    a_close_idx = body.find(">", a_idx)
    membres_a_tag = body[a_idx:a_close_idx]
    assert 'aria-current="page"' in membres_a_tag
