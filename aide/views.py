"""Public FAQ page at /aide/.

Single view, single template. Renders FAQ_ENTRIES grouped by category with
an optional ?q= server-side substring filter. When ?q= returns no matches,
writes an `aide.query.no_results` AuditLog row to seed a future bot-decision
dataset (anonymous actor allowed; mirrors the public-removal-request pattern).
"""

from __future__ import annotations

from collections import OrderedDict

import bleach
import markdown as _markdown
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from members.models import AuditLog

from .faq import CATEGORIES, CATEGORY_META, FAQ_ENTRIES, FAQEntry

Q_TRUNCATE_CHARS = 80

# Allowed tags/attrs for FAQ answer markdown — same posture as memoriam
# tributes (memoriam/views.py:18-35) but no h2/h3 since the question itself
# is the heading.
_ALLOWED_TAGS = ["p", "br", "strong", "em", "a", "ul", "ol", "li", "code", "blockquote"]
_ALLOWED_ATTRS = {"a": ["href", "title", "target", "rel"]}


def _render_answer(answer_md: str) -> str:
    raw_html = _markdown.markdown(answer_md, extensions=["extra"])
    return bleach.clean(raw_html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


# Pre-render once at import time — FAQ_ENTRIES is static.
_ANSWER_HTML: dict[str, str] = {e.slug: _render_answer(e.answer_md) for e in FAQ_ENTRIES}


def _filter_entries(q: str) -> list[FAQEntry]:
    """Case-insensitive substring filter across question + answer."""
    if not q:
        return list(FAQ_ENTRIES)
    needle = q.casefold()
    return [
        e
        for e in FAQ_ENTRIES
        if needle in e.question.casefold() or needle in e.answer_md.casefold()
    ]


def _group_by_category(entries: list[FAQEntry]) -> list[dict]:
    """Preserve CATEGORIES order; pair each entry with its rendered HTML; drop empty categories.

    Returns a list shaped for template rendering, one dict per non-empty category:
    ``{"name": str, "icon": str, "slug": str, "items": [(FAQEntry, html), ...]}``.
    """
    buckets: OrderedDict[str, list[tuple[FAQEntry, str]]] = OrderedDict((c, []) for c in CATEGORIES)
    for e in entries:
        buckets[e.category].append((e, _ANSWER_HTML[e.slug]))
    return [
        {
            "name": name,
            "icon": CATEGORY_META[name]["icon"],
            "slug": CATEGORY_META[name]["slug"],
            "items": items,
        }
        for name, items in buckets.items()
        if items
    ]


def _log_no_results(request: HttpRequest, q: str) -> None:
    actor = request.user if request.user.is_authenticated else None
    AuditLog.objects.create(
        actor=actor,
        action="aide.query.no_results",
        target_type="aide.FAQ",
        target_id="-",
        metadata={
            "q": q[:Q_TRUNCATE_CHARS],
            "actor_username": (
                request.user.username if request.user.is_authenticated else "anonymous"
            ),
        },
    )


def aide_view(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    entries = _filter_entries(q)
    if q and not entries:
        _log_no_results(request, q)
    sections = _group_by_category(entries)
    return render(
        request,
        "aide/index.html",
        {
            "q": q,
            "sections": sections,
            "total_count": len(entries),
            "all_count": len(FAQ_ENTRIES),
        },
    )
