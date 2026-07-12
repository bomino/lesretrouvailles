"""Sitemap for the public surface. Only landing + inscription are exposed —
member URLs (annuaire, profil, cooptation token URLs) must never appear."""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PublicSurfaceSitemap(Sitemap):
    """The four public URLs: landing, cooptation signup, FAQ, member guide.

    /aide/ and /guide/ are login-exempt (LOGIN_REQUIRED_WHITELIST) precisely
    so members without a session can reach them; leaving them out of the
    sitemap meant a member searching for help found nothing.
    """

    changefreq = "weekly"
    priority = 0.8
    # Force https in <loc> entries even when Django receives the request
    # over plain HTTP (Railway terminates TLS at the proxy). The class
    # attribute takes precedence over the request-inferred protocol.
    protocol = "https"

    def items(self):
        return ["landing", "signup", "aide", "guide"]

    def location(self, item):
        if item == "landing":
            return "/"
        if item == "signup":
            return reverse("cooptation:signup")
        if item == "aide":
            return reverse("aide:index")
        if item == "guide":
            return reverse("member_guide")
        raise ValueError(f"Unknown sitemap item: {item}")
