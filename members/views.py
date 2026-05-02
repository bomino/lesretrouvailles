"""Views for the membership app."""

from __future__ import annotations

import markdown as _markdown
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .charters import CHARTER_CURRENT_VERSION, get_charter_text
from .models import ConsentRecord


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


@require_http_methods(["GET", "POST"])
def charter_view(request):
    if request.method == "POST":
        member = getattr(request.user, "member", None)
        if member is not None:
            ConsentRecord.objects.create(
                member=member,
                charter_version=CHARTER_CURRENT_VERSION,
                ip_address=_client_ip(request),
            )
            request.session["consent_ok_for"] = CHARTER_CURRENT_VERSION
        next_url = request.GET.get("next") or request.POST.get("next") or "/"
        return HttpResponseRedirect(next_url)

    body_html = _markdown.markdown(
        get_charter_text(CHARTER_CURRENT_VERSION),
        extensions=["extra"],
    )
    return render(
        request,
        "members/charter.html",
        {
            "charter_html": body_html,
            "charter_version": CHARTER_CURRENT_VERSION,
            "next": request.GET.get("next", "/"),
        },
    )
