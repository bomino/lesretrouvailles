"""Sitemap for the public surface. Only landing + inscription are exposed —
member URLs (annuaire, profil, cooptation token URLs) must never appear."""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PublicSurfaceSitemap(Sitemap):
    """Two static URLs: the landing and the cooptation signup form."""

    changefreq = "weekly"
    priority = 0.8
    # Force https in <loc> entries even when Django receives the request
    # over plain HTTP (Railway terminates TLS at the proxy). The class
    # attribute takes precedence over the request-inferred protocol.
    protocol = "https"

    def items(self):
        return ["landing", "signup"]

    def location(self, item):
        if item == "landing":
            return "/"
        if item == "signup":
            return reverse("cooptation:signup")
        raise ValueError(f"Unknown sitemap item: {item}")
