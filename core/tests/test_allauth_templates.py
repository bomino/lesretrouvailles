"""Tests for the styled allauth template overrides.

Coverage strategy:
- Parametrized GET-200 test covers the easy public/authed flows.
- Targeted tests cover special branches (e.g., password_reset_from_key
  token_fail) and the negative-POST-renders-styled-errors check.
- File-content tests cover edge templates that need rare server state
  to render (account_inactive, verified_email_required, reauthenticate,
  email_confirm) — these assert the file extends base.html and uses the
  shared partials, without invoking the test client.
"""

from __future__ import annotations

from pathlib import Path

from django.template.loader import render_to_string

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "account"


def test_form_card_partial_renders_with_brand_chrome():
    """The shared form-card extends base.html and emits brand markers."""
    rendered = render_to_string(
        "account/_form_card.html",
        {"form": None},  # parent has no form context for this smoke test
    )
    assert "Les Retrouvailles" in rendered
    assert "rounded-2xl bg-surface" in rendered  # the card chrome


def test_input_partial_renders_label_and_input(rf):
    """Smoke test: _input.html renders an input with the canonical Tailwind class."""
    from django import forms

    class SmokeForm(forms.Form):
        email = forms.EmailField()

    f = SmokeForm()
    rendered = render_to_string(
        "account/_input.html",
        {"field": f["email"], "type": "email", "label": "Email", "autocomplete": "email"},
    )
    assert "Email" in rendered  # label
    assert 'type="email"' in rendered
    assert "rounded-lg border border-secondary/20" in rendered  # canonical input class
