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
