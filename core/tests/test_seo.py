"""Tests for SEO infrastructure: sitemap, robots.txt, OG tags, JSON-LD."""

from __future__ import annotations

import re

import pytest


@pytest.mark.django_db
def test_sitemap_returns_200_xml(client):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")


@pytest.mark.django_db
def test_sitemap_includes_landing_and_inscription(client):
    response = client.get("/sitemap.xml")
    body = response.content.decode("utf-8")
    locs = re.findall(r"<loc>([^<]+)</loc>", body)
    assert any(loc.endswith("/inscription/") for loc in locs), (
        f"Inscription not in sitemap; locs: {locs}"
    )
    assert any(loc.endswith("/") and not loc.endswith("/inscription/") for loc in locs), (
        f"Root landing not in sitemap; locs: {locs}"
    )


@pytest.mark.django_db
def test_sitemap_excludes_member_urls(client):
    response = client.get("/sitemap.xml")
    body = response.content.decode("utf-8")
    for forbidden in ("/profil/", "/annuaire/", "/admin/", "/cooptation/"):
        assert forbidden not in body, (
            f"Sitemap leaks member URL {forbidden}; only public surfaces should appear there"
        )


@pytest.mark.django_db
def test_sitemap_no_percent_20_in_output(client, settings):
    """Sanity check: the rendered sitemap must not contain `%20`.

    Note: Django's sitemap framework builds <loc> URLs from the
    `sites.Site` model's `domain` field — NOT from settings.SITE_URL.
    SITE_URL drives email templates and robots.txt, not this view.
    The sites.Site domain default is `example.com` in tests; whatever
    it is in production must also be free of trailing whitespace,
    which is operator concern, not code concern. This test guards
    against any rendering pipeline accidentally emitting URL-encoded
    spaces (which would be a clear sign of upstream data corruption).
    """
    settings.SITE_URL = "https://prod.example.test"  # not consulted by sitemap framework
    response = client.get("/sitemap.xml")
    body = response.content.decode("utf-8")
    assert "%20" not in body


@pytest.mark.django_db
def test_robots_txt_returns_200_text_plain(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")


@pytest.mark.django_db
def test_robots_allows_public_paths(client):
    body = client.get("/robots.txt").content.decode("utf-8")
    assert "Allow: /\n" in body or body.strip().split("\n")[1].startswith("Allow: /")
    assert "Allow: /inscription/" in body
    assert "Allow: /sitemap.xml" in body


@pytest.mark.django_db
def test_robots_disallows_member_and_admin_paths(client):
    body = client.get("/robots.txt").content.decode("utf-8")
    for path in (
        "/admin/",
        "/accounts/",
        "/profil/",
        "/annuaire/",
        "/cooptation/",
        "/questionnaire/",
        "/charte/",
    ):
        assert f"Disallow: {path}" in body, f"robots.txt missing Disallow for {path}"


@pytest.mark.django_db
def test_robots_references_sitemap_url_from_settings(client, settings):
    settings.SITE_URL = "https://prod.example.test"
    body = client.get("/robots.txt").content.decode("utf-8")
    assert "Sitemap: https://prod.example.test/sitemap.xml" in body


@pytest.mark.django_db
def test_cloudflare_beacon_present_when_token_set_and_anonymous(client, settings):
    settings.CLOUDFLARE_ANALYTICS_TOKEN = "test-cf-token-abc"
    body = client.get("/").content.decode("utf-8")
    assert "static.cloudflareinsights.com/beacon.min.js" in body
    assert "test-cf-token-abc" in body


@pytest.mark.django_db
def test_cloudflare_beacon_absent_when_token_blank(client, settings):
    settings.CLOUDFLARE_ANALYTICS_TOKEN = ""
    body = client.get("/").content.decode("utf-8")
    assert "static.cloudflareinsights.com" not in body


@pytest.mark.django_db
def test_cloudflare_beacon_absent_for_authenticated_users(client, settings):
    """Members visiting member pages must not pollute the public-surface metric."""
    from django.contrib.auth import get_user_model

    from members.models import Member

    settings.CLOUDFLARE_ANALYTICS_TOKEN = "test-cf-token-abc"
    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="bob@example.test", email="bob@example.test", password="x"
    )
    Member.objects.create(
        user=user,
        first_name="Bob",
        last_name="X",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    # ConsentRequiredMiddleware gates auth users until they accept the charter
    from members.charters import CHARTER_CURRENT_VERSION

    session = client.session
    session["consent_ok_for"] = CHARTER_CURRENT_VERSION
    session.save()
    client.force_login(user)
    body = client.get("/profil/").content.decode("utf-8")
    assert "static.cloudflareinsights.com" not in body
