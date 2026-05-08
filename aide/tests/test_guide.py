"""Tests for aide.guide and the /guide/ view.

Test design favors structural assertions (heading count, length) plus a small
set of stable sentinel substrings ("1980-1985", "WhatsApp", "RGPD") rather
than full heading texts that may be polished later. Catches regressions
without coupling to copy.
"""

from __future__ import annotations

import re

import pytest
from django.test import Client
from django.urls import reverse

from aide import guide as guide_module
from aide.guide import _GUIDE_PATH, GUIDE_HTML, GUIDE_TOC

# --------------------------------------------------------------------------
# Module-level: file path, render output, safety
# --------------------------------------------------------------------------


def test_guide_path_resolves():
    """If this fails, the canonical markdown file moved/renamed and the live
    page would silently degrade to the placeholder. CI catches it loudly."""
    assert _GUIDE_PATH.exists(), (
        f"Canonical member guide not found at {_GUIDE_PATH}. "
        "Did the file move? Update aide/guide.py::_GUIDE_PATH and the "
        "Dockerfile COPY line."
    )


def test_guide_html_is_non_trivial():
    """Structural sanity — the rendered guide should be long-form, not the
    placeholder. Threshold is loose enough to absorb future content edits."""
    assert len(GUIDE_HTML) > 5000, f"GUIDE_HTML suspiciously short: {len(GUIDE_HTML)} chars"


def test_guide_html_is_not_placeholder():
    assert "temporairement indisponible" not in GUIDE_HTML


def test_guide_html_has_section_headings():
    """At least 8 top-level h2 sections expected (the guide currently has 11)."""
    h2_count = len(re.findall(r"<h2[^>]*>", GUIDE_HTML))
    assert h2_count >= 8, f"Expected at least 8 h2 sections, found {h2_count}"


def test_guide_html_has_sentinel_substrings():
    """Anchor terms unlikely to be edited away — they're part of the
    platform's intrinsic identity, not stylistic copy."""
    for sentinel in ("1980", "1985", "WhatsApp", "RGPD"):
        assert sentinel in GUIDE_HTML, f"Sentinel {sentinel!r} missing from rendered guide"


def test_guide_html_strips_script_tags():
    """Bleach must strip any <script>; defense-in-depth even though the
    canonical file is curated."""
    assert "<script" not in GUIDE_HTML.lower()


def test_guide_html_strips_inline_event_handlers():
    """No onclick=, onerror= etc. should survive bleach."""
    assert not re.search(r"\son\w+\s*=", GUIDE_HTML), "Inline event handler leaked through bleach"


# --------------------------------------------------------------------------
# Table of contents
# --------------------------------------------------------------------------


def test_guide_toc_has_sections():
    """At least 8 top-level entries (matches the h2-count assertion)."""
    assert len(GUIDE_TOC) >= 8, f"GUIDE_TOC has only {len(GUIDE_TOC)} entries"


def test_guide_toc_entries_are_well_shaped():
    for entry in GUIDE_TOC:
        assert entry.get("id"), f"TOC entry missing id: {entry}"
        assert entry.get("text"), f"TOC entry missing text: {entry}"
        assert entry.get("level") == 2, f"TOC entry has wrong level (sidebar = h2 only): {entry}"


def test_every_toc_id_appears_as_anchor_in_html():
    """The TOC sidebar links jump to anchor IDs in the body. If the IDs
    don't match, the links are dead. Catches markdown-toc-extension drift."""
    body_ids = set(re.findall(r'id="([^"]+)"', GUIDE_HTML))
    missing = [entry["id"] for entry in GUIDE_TOC if entry["id"] not in body_ids]
    assert not missing, f"TOC IDs not present as anchor IDs in body: {missing}"


# --------------------------------------------------------------------------
# Missing-file fallback (covers the loud-failure-mode contract)
# --------------------------------------------------------------------------


def test_load_returns_placeholder_when_file_missing(monkeypatch, tmp_path, caplog):
    """If the file disappears, _load_and_render serves the placeholder
    (page still 200s) AND logs a WARNING (operator gets a signal)."""
    fake_path = tmp_path / "absent_guide.md"
    monkeypatch.setattr(guide_module, "_GUIDE_PATH", fake_path)

    with caplog.at_level("WARNING", logger="aide.guide"):
        html, toc = guide_module._load_and_render()

    assert "temporairement indisponible" in html
    assert toc == []
    assert any("not found" in record.message.lower() for record in caplog.records), (
        "Expected a WARNING log when the guide file is missing"
    )


# --------------------------------------------------------------------------
# View end-to-end
# --------------------------------------------------------------------------


@pytest.fixture
def client_anon():
    return Client()


@pytest.fixture
def client_auth(make_user):
    user = make_user(password="testpass123")
    c = Client()
    c.login(username=user.username, password="testpass123")
    return c


@pytest.mark.django_db
def test_guide_view_is_public_for_anonymous(client_anon):
    response = client_anon.get(reverse("member_guide"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_guide_view_is_accessible_for_authenticated(client_auth):
    response = client_auth.get(reverse("member_guide"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_guide_view_renders_real_content(client_anon):
    """Smoke check: the rendered page contains a sentinel substring and at
    least one h2 heading, so we know the view actually serves the guide and
    not an empty template."""
    response = client_anon.get(reverse("member_guide"))
    body = response.content.decode("utf-8")
    assert "1980" in body
    assert "<h2" in body
