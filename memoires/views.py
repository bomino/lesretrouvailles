"""Member-only views for the Mur des souvenirs."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import Memory


@login_required
@require_http_methods(["GET"])
def gallery_view(request):
    """Grid of published memories, newest era first.

    Drafts are excluded — they are admin-curation territory only.
    """
    memories = Memory.objects.filter(status="published")
    return render(request, "memoires/gallery.html", {"memories": memories})


@login_required
@require_http_methods(["GET"])
def detail_view(request, pk: int):
    memory = get_object_or_404(Memory, pk=pk, status="published")
    return render(request, "memoires/detail.html", {"memory": memory})
