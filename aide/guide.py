"""Render the canonical member guide for the public `/guide/` page.

Reads ``docs/guides/guide_membre.md`` once at module load time, runs it
through markdown + bleach, and exposes:

- ``GUIDE_HTML``: the cleaned, anchor-id-bearing body HTML.
- ``GUIDE_TOC``: a list of ``{"id", "text", "level"}`` filtered to ``level == 2``,
  i.e. the top-level numbered sections shown in the sidebar.

The ``toc`` markdown extension still emits anchor IDs for every heading, so
direct URLs like ``/guide/#2a-si-vous-avez-recu-un-email-dactivation`` work
even though the subsection isn't in the sidebar.

Failure mode is loud, not silent. If the file is missing at import time we
log a WARNING and serve a placeholder page (200, not 500). A unit test
asserts ``_GUIDE_PATH.exists()`` so a future rename or Dockerfile drift
fails CI before reaching prod.
"""

from __future__ import annotations

import logging
from pathlib import Path

import bleach
import markdown as _markdown
from django.conf import settings

logger = logging.getLogger(__name__)

_GUIDE_PATH: Path = settings.BASE_DIR / "docs" / "guides" / "guide_membre.md"

# Tags allowed through bleach. Mirrors memoriam tribute and aide answer
# pipelines, plus h1-h4 + hr + table tags for richer long-form content.
_ALLOWED_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "a",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
]

# Wildcard ``*`` lets every allowed tag carry an ``id`` attribute, so the
# anchor IDs the markdown ``toc`` extension generates survive bleach.
# Verified to work on bleach 6.3.0 (the installed version per pyproject.toml).
_ALLOWED_ATTRS = {
    "*": ["id"],
    "a": ["href", "title"],
}

_PLACEHOLDER_HTML = "<p>Le guide est temporairement indisponible.</p>"


def _load_and_render() -> tuple[str, list[dict]]:
    """Read the canonical guide, render to bleach-clean HTML, build TOC.

    Returns ``(html, toc)`` where ``toc`` is a list of dicts shaped for
    template rendering: ``{"id": str, "text": str, "level": int}``.

    On missing file: logs a warning and returns the placeholder + empty TOC.
    The view still 200s; operators see the warning in logs.
    """
    if not _GUIDE_PATH.exists():
        logger.warning(
            "Member guide markdown file not found at %s — serving placeholder. "
            "Check that the Dockerfile copies docs/guides/ into the runtime stage.",
            _GUIDE_PATH,
        )
        return (_PLACEHOLDER_HTML, [])

    raw = _GUIDE_PATH.read_text(encoding="utf-8")
    md = _markdown.Markdown(extensions=["extra", "toc"])
    html = md.convert(raw)
    cleaned = bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        strip=True,
    )

    # md.toc_tokens is a recursive structure mirroring the heading hierarchy:
    # the shallowest heading (h1, the page title) sits at the top level with
    # h2 sections nested as ``children``. Walk the tree and pick out level==2
    # entries for the sidebar; subsections (h3) still get anchor IDs in the
    # body and remain reachable via direct URL.
    def _walk(tokens, out):
        for token in tokens:
            if token.get("level") == 2:
                out.append(
                    {
                        "id": token["id"],
                        "text": token["name"],
                        "level": token["level"],
                    }
                )
            if token.get("children"):
                _walk(token["children"], out)

    toc: list[dict] = []
    _walk(md.toc_tokens, toc)

    return cleaned, toc


GUIDE_HTML, GUIDE_TOC = _load_and_render()
