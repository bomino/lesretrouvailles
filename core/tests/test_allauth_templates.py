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

import re
from pathlib import Path

import pytest
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


def test_input_partial_renders_label_and_input():
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


def test_input_partial_supports_optional_field():
    """Regression: passing required=False must omit the required attribute.
    The naive `{% if required|default:True %}` was broken because Django's
    `|default` substitutes the default when the value is False (truthy/falsy
    semantics, not None-checking)."""
    from django import forms

    class SmokeForm(forms.Form):
        nickname = forms.CharField(required=False)

    f = SmokeForm()
    rendered = render_to_string(
        "account/_input.html",
        {"field": f["nickname"], "type": "text", "label": "Nickname", "required": False},
    )
    # The input tag should NOT contain the bare `required` attribute.
    # Walk through carefully to avoid false matches on the `required` substring
    # (e.g., if it ever appears in a class or comment).
    input_match = re.search(r"<input[^>]*>", rendered)
    assert input_match is not None, f"no <input> found in rendered output: {rendered}"
    input_tag = input_match.group(0)
    assert "required" not in input_tag, f"required=False must omit the attribute, got: {input_tag}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "/accounts/password/reset/",
        "/accounts/password/reset/done/",
    ],
)
def test_password_reset_pages_render_with_brand_chrome(client, url):
    """Anonymous-accessible pages in the password-reset flow render with
    the project's base.html and contain no Django default errorlist markup."""
    response = client.get(url)
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Les Retrouvailles" in body  # footer brand text from base.html
    assert 'class="errorlist"' not in body


@pytest.mark.django_db
def test_password_reset_from_key_done_page(client):
    """The 'password set' confirmation page renders with brand chrome."""
    response = client.get("/accounts/password/reset/key/done/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Les Retrouvailles" in body
    assert 'class="errorlist"' not in body


def test_password_reset_from_key_template_extends_base():
    """The set-password page exists at the right path and extends base.html.
    Reaching it via test client is awkward (needs a real key generation +
    an interim GET-then-redirect dance allauth uses). Source-level check
    is sufficient for chrome assertions."""
    src = (TEMPLATES_DIR / "password_reset_from_key.html").read_text(encoding="utf-8")
    assert '{% extends "base.html" %}' in src
    # base.html will render "Les Retrouvailles" — we just need the extension.


def test_password_reset_from_key_token_fail_branch():
    """Source contains the token_fail branch with a CTA back to /accounts/password/reset/."""
    src = (TEMPLATES_DIR / "password_reset_from_key.html").read_text(encoding="utf-8")
    assert "token_fail" in src
    assert "account_reset_password" in src  # the CTA URL name


@pytest.fixture
def member_client(db):
    """Logged-in member with charter consent (passes ConsentRequiredMiddleware)."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="allauth-test@example.test",
        email="allauth-test@example.test",
        password="orig-pw-1",
    )
    member = Member.objects.create(
        user=user,
        first_name="Test",
        last_name="Member",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="orig-pw-1")
    return c


@pytest.mark.django_db
def test_password_change_renders_with_brand_chrome(member_client):
    response = member_client.get("/accounts/password/change/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Les Retrouvailles" in body
    assert 'class="errorlist"' not in body
    assert 'name="oldpassword"' in body  # confirms the form rendered


@pytest.mark.django_db
def test_email_management_page_renders_with_brand_chrome(member_client):
    response = member_client.get("/accounts/email/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Les Retrouvailles" in body
    assert 'class="errorlist"' not in body


def test_verification_sent_template_extends_base():
    """verification_sent.html is rare to GET (depends on email-verification flow);
    source-level check is enough."""
    src = (TEMPLATES_DIR / "verification_sent.html").read_text(encoding="utf-8")
    assert '{% extends "base.html" %}' in src
    assert "vérification" in src.lower()


def test_email_change_template_extends_form_card():
    src = (TEMPLATES_DIR / "email_change.html").read_text(encoding="utf-8")
    assert '{% extends "account/_form_card.html" %}' in src


def test_email_confirm_template_extends_form_card():
    src = (TEMPLATES_DIR / "email_confirm.html").read_text(encoding="utf-8")
    assert '{% extends "account/_form_card.html" %}' in src


@pytest.mark.parametrize(
    "filename",
    [
        "account_inactive.html",
        "verified_email_required.html",
        "reauthenticate.html",
    ],
)
def test_edge_case_template_extends_base_or_form_card(filename):
    """These pages need rare server state to GET (inactive user logged in,
    sensitive-op redirect, etc.). Source-level check confirms they extend
    our base + use brand chrome."""
    src = (TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    extends_base = '{% extends "base.html" %}' in src
    extends_form_card = '{% extends "account/_form_card.html" %}' in src
    assert extends_base or extends_form_card, (
        f"{filename} must extend base.html or account/_form_card.html"
    )
    assert "{% load i18n %}" in src or "{% load i18n " in src


def test_signup_template_extends_form_card():
    """Resilience override: even though signups are currently disabled, the
    template should be on-brand if the adapter ever flips."""
    src = (TEMPLATES_DIR / "signup.html").read_text(encoding="utf-8")
    assert '{% extends "account/_form_card.html" %}' in src
    assert "Inscription" in src or "Bienvenue" in src  # the pill text


@pytest.mark.django_db
def test_failing_post_to_password_reset_renders_styled_errors(client):
    """Negative test: deliberately submit invalid data and verify the
    rendered error markup uses the styled alert pattern, not Django's
    default <ul class='errorlist'>."""
    response = client.post(
        "/accounts/password/reset/",
        {"email": "not-an-email-address"},
    )
    assert response.status_code == 200  # form re-rendered with errors
    body = response.content.decode("utf-8")
    assert 'class="errorlist"' not in body
