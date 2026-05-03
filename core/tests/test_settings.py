"""Regression tests for settings normalization quirks."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://example.com", "https://example.com"),
        ("https://example.com/", "https://example.com"),
        ("https://example.com  ", "https://example.com"),
        ("  https://example.com", "https://example.com"),
        ("https://example.com/ ", "https://example.com"),
    ],
)
def test_site_url_strips_whitespace_and_trailing_slash(monkeypatch, raw, expected):
    """SITE_URL is concatenated with paths to build absolute links in
    cooptation emails. A trailing space turns the URL into
    `https://host%20/path` (browser-rendered Redirect Notice in production);
    a trailing slash gives `https://host//path`. Both have happened — strip
    on read so an env-var typo can't silently break the link.
    """
    monkeypatch.setenv("SITE_URL", raw)
    import alumni.settings.base as base

    importlib.reload(base)
    assert base.SITE_URL == expected
