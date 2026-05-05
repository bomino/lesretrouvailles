"""Tests for audit_launch_readiness command (P7)."""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

User = get_user_model()


@pytest.mark.django_db
def test_audit_prints_all_sections_on_empty_db():
    out = StringIO()
    call_command("audit_launch_readiness", stdout=out)

    output = out.getvalue()
    # Every checked dimension must appear, even on an empty DB
    assert "Active members" in output
    assert "Memory rows" in output
    assert "InMemoriamEntry" in output
    assert "PublicSearchEntry" in output


@pytest.mark.django_db
def test_audit_flags_below_threshold_items():
    """On an empty DB, all content checks should show below-threshold warnings."""
    out = StringIO()
    call_command("audit_launch_readiness", stdout=out)

    output = out.getvalue()
    # Memory minimum is 10; we have 0 → should be flagged
    assert "⚠" in output or "WARN" in output or "below" in output.lower()
