"""Member-only views for the In Memoriam surface."""

from __future__ import annotations

import markdown as _markdown
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import InMemoriamEntry


@login_required
@require_http_methods(["GET"])
def list_view(request):
    entries = InMemoriamEntry.objects.published().order_by("full_name")
    return render(request, "memoriam/list.html", {"entries": entries})


@login_required
@require_http_methods(["GET"])
def detail_view(request, pk: int):
    entry = get_object_or_404(InMemoriamEntry.objects.published(), pk=pk)
    tribute_html = _markdown.markdown(entry.tribute, extensions=["extra"])
    return render(
        request,
        "memoriam/detail.html",
        {"entry": entry, "tribute_html": tribute_html},
    )
