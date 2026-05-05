"""Member-only views for the In Memoriam surface."""

from __future__ import annotations

import bleach
import markdown as _markdown
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from members.models import Member

from .emails import send_nomination_received_to_admins
from .forms import NominationForm
from .models import InMemoriamEntry

_ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "a",
    "ul",
    "ol",
    "li",
    "blockquote",
    "h2",
    "h3",
    "h4",
    "code",
    "pre",
    "hr",
]
_ALLOWED_ATTRS = {"a": ["href", "title"]}


@login_required
@require_http_methods(["GET"])
def list_view(request):
    entries = InMemoriamEntry.objects.published().order_by("full_name")
    return render(request, "memoriam/list.html", {"entries": entries})


@login_required
@require_http_methods(["GET"])
def detail_view(request, pk: int):
    entry = get_object_or_404(InMemoriamEntry.objects.published(), pk=pk)
    raw_html = _markdown.markdown(entry.tribute, extensions=["extra"])
    tribute_html = bleach.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        strip=True,
    )
    return render(
        request,
        "memoriam/detail.html",
        {"entry": entry, "tribute_html": tribute_html},
    )


@login_required
@require_http_methods(["GET", "POST"])
@ratelimit(key="user", rate="1/d", method="POST", block=True)
def nominate_view(request):
    if request.method == "POST":
        form = NominationForm(request.POST)
        if form.is_valid():
            nom = form.save(commit=False)
            nom.nominator = get_object_or_404(Member, user=request.user)
            nom.save()
            send_nomination_received_to_admins(nom)
            return redirect("memoriam:nominate_thanks")
    else:
        form = NominationForm()
    return render(request, "memoriam/nominate.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def nominate_thanks_view(request):
    return render(request, "memoriam/nominate_thanks.html")
