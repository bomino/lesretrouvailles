"""Verify MEMORIAM_CONTACT_EMAIL is a clean email (no display name) so
that mailto: links work in the detail-page footer."""

from __future__ import annotations

from django.conf import settings


def test_memoriam_contact_email_is_clean():
    """Must not contain '<' or '>' (display-name framing)."""
    val = settings.MEMORIAM_CONTACT_EMAIL
    assert "<" not in val
    assert ">" not in val
    assert "@" in val
