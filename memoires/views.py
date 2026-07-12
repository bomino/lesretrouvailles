"""Member-only views for the Mur des souvenirs."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import Memory

PAGE_SIZE = 24


@login_required
@require_http_methods(["GET"])
def gallery_view(request):
    """Grid of published memories, newest era first.

    Drafts are excluded — they are admin-curation territory only.

    Paginated like every other list surface (directory 20/page, gestion
    memories 12/page): every card carries a Cloudinary <img>, so an
    unbounded grid grows DOM size and data cost linearly with curation on
    the low-end Android devices this audience uses.
    """
    qs = Memory.objects.filter(status="published")
    paginator = Paginator(qs, PAGE_SIZE)
    try:
        page_number = max(1, int(request.GET.get("page", "1")))
    except (TypeError, ValueError):
        page_number = 1
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(paginator.num_pages or 1)

    return render(
        request,
        "memoires/gallery.html",
        {"memories": page.object_list, "page": page},
    )


@login_required
@require_http_methods(["GET"])
def detail_view(request, pk: int):
    memory = get_object_or_404(Memory, pk=pk, status="published")
    return render(request, "memoires/detail.html", {"memory": memory})
