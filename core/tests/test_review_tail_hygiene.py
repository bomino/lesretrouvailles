"""T7 (2026-08-01 review tail): core hygiene items."""

from __future__ import annotations

from pathlib import Path


def test_basic_auth_compares_credentials_in_constant_time():
    """`==` on credentials leaks timing; compare_digest is the standard fix.
    Staging-only gate, so this is defense-in-depth, not a live hole."""
    src = (Path(__file__).resolve().parents[2] / "core" / "middleware.py").read_text(
        encoding="utf-8"
    )
    assert "compare_digest" in src


def test_landing_placeholder_view_is_gone():
    """Kept 'temporarily' for the P4 migration (2026-05-03); unrouted since.
    Flagged by the review as dead code — now removed."""
    import core.views

    assert not hasattr(core.views, "landing_placeholder")
