"""Core views — health check, public landing, robots.txt."""

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings as django_settings
from django.db import connection
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


def health(_request):
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False
    payload = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "fail"}
    status_code = 200 if db_ok else 503
    return JsonResponse(payload, status=status_code)


# Kept temporarily so older imports/redirects don't 500 during the migration.
def landing_placeholder(request):
    return render(request, "core/landing_placeholder.html")


@require_http_methods(["GET"])
def landing_view(request):
    """The public landing page. Anonymous visitors get the recruitment-shaped
    CTAs and the ghost list (if the feature flag is on); authenticated members
    get the member-style CTAs from the prior placeholder template."""
    from members.models import PublicSearchEntry

    # Ghost section is a public-discovery surface — only fetch (and therefore
    # only render) for anonymous visitors when the operator-controlled flag
    # is on. Authenticated members already have the full directory; the
    # template just renders whatever queryset we hand it.
    ghosts = []
    if not request.user.is_authenticated and django_settings.PUBLIC_GHOST_LIST_ENABLED:
        ghosts = list(
            PublicSearchEntry.objects.filter(removed_at__isnull=True)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=1)
        )

    share_url = request.build_absolute_uri("/?utm_source=whatsapp&utm_campaign=invitation")
    share_message = "Les Retrouvailles — promotion 1980-1985 du CEG 1 Birni à Zinder"
    whatsapp_text = f"{share_message} {share_url}"

    return render(
        request,
        "core/landing.html",
        {
            "ghosts": ghosts,
            "share_url": share_url,
            "whatsapp_share_url": f"https://wa.me/?text={quote(whatsapp_text)}",
            "site_url": django_settings.SITE_URL,
        },
    )


def robots_txt(request):
    return render(
        request,
        "robots.txt",
        {"site_url": django_settings.SITE_URL},
        content_type="text/plain",
    )
