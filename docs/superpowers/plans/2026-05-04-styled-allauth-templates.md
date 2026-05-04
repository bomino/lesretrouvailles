# Styled Allauth Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Override 14 allauth account templates with project chrome so the entire `/accounts/*` flow matches the rest of the site visually. Closes the unstyled-form-on-cooptation-password-set complaint.

**Architecture:** Two shared partials provide the chrome — `_form_card.html` (multi-level extends pattern: itself extends `base.html`, leaf templates extend `_form_card.html` and override blocks for headline/subtitle/action_url/fields/submit_label) and `_input.html` (`{% include %}` partial for one form field with label + input + help text + errors). Form-style templates extend `_form_card.html`. Info-only templates (`*_done.html`, `verification_sent`, `account_inactive`, `verified_email_required`) extend `base.html` directly with their own info-card markup. Special case: `email.html` has two forms + a list of email addresses; extends `base.html` directly.

**Tech Stack:** Django 5.0 templates, allauth 65.x, Tailwind 3 + DaisyUI v4, pytest-django.

**Spec:** `docs/superpowers/specs/2026-05-04-styled-allauth-templates-design.md`

---

## File Structure

**Create (16 new templates + 1 test file):**
- `templates/account/_input.html` — single form field render: label + input + help_text + errors
- `templates/account/_form_card.html` — extends `base.html`, defines blocks `pill` (default "Espace membre"), `headline`, `subtitle`, `action_url`, `fields`, `submit_label`, `extra_actions`, `below_card`. Provides the rounded card + `<form>` scaffold + non_field_errors block + submit button.
- `templates/account/password_reset.html` — extends `_form_card.html`. 1 field (email).
- `templates/account/password_reset_done.html` — extends `base.html`. Info-only confirmation page.
- `templates/account/password_reset_from_key.html` — extends `base.html` directly (has a `token_fail` conditional branch with different layout). 2 fields (password1, password2) or error block.
- `templates/account/password_reset_from_key_done.html` — extends `base.html`. Info-only confirmation + login link.
- `templates/account/password_change.html` — extends `_form_card.html`. 3 fields (oldpassword, password1, password2).
- `templates/account/password_set.html` — extends `_form_card.html`. 2 fields (password1, password2).
- `templates/account/email.html` — extends `base.html` directly. Custom layout: list of emails + add-email form.
- `templates/account/email_change.html` — extends `_form_card.html`. 1 field (email).
- `templates/account/email_confirm.html` — extends `_form_card.html`. No fields (just a confirm button).
- `templates/account/verification_sent.html` — extends `base.html`. Info-only.
- `templates/account/account_inactive.html` — extends `base.html`. Info-only.
- `templates/account/verified_email_required.html` — extends `base.html`. Info-only with a resend CTA.
- `templates/account/reauthenticate.html` — extends `_form_card.html`. 1 field (password).
- `templates/account/signup.html` — extends `_form_card.html`. 3 fields. Resilience override (current adapter blocks signup; if ever opened, page is on-brand).
- `core/tests/test_allauth_templates.py` — single parametrized test for the GET-200 flows + targeted tests for special branches (token_fail) + a negative test for failing-form-POST renders styled errors.

**Modify:**
- `docs/superpowers/STATUS.md` — add row + section for this phase.

**Touched but unchanged:** the 3 existing styled templates (`login.html`, `logout.html`, `signup_closed.html`) stay as-is.

---

## Task Order Rationale

1. **Task 1 (partials)** — foundational. All form-style leaves depend on `_form_card.html` and use `_input.html`. Ship + smoke-test before any leaf templates.
2. **Task 2 (password-reset request)** — anonymous flow, simplest forms.
3. **Task 3 (password-reset from key)** — the critical one (cooptation flow). Has the `token_fail` branch.
4. **Task 4 (logged-in password mgmt)** — `password_change` and `password_set` are siblings.
5. **Task 5 (email mgmt)** — 4 templates around email addresses. The `email.html` is the most complex.
6. **Task 6 (edge cases)** — `account_inactive`, `verified_email_required`, `reauthenticate`. All info-only or rare-state.
7. **Task 7 (signup resilience + negative test)** — `signup.html` + the test asserting failing-POST renders styled error markup.
8. **Task 8 (STATUS update)** — housekeeping.

---

## Task 1: Shared partials (`_input.html` + `_form_card.html`)

**Files:**
- Create: `templates/account/_input.html`
- Create: `templates/account/_form_card.html`
- Create: `core/tests/test_allauth_templates.py`

- [ ] **Step 1: Write the failing test for partial smoke-rendering**

Create `core/tests/test_allauth_templates.py`:

```python
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

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import Client


TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "account"


def test_form_card_partial_renders_with_brand_chrome():
    """The shared form-card extends base.html and emits brand markers."""
    rendered = render_to_string(
        "account/_form_card.html",
        {"form": None},  # parent has no form context for this smoke test
    )
    assert "Les Retrouvailles" in rendered
    assert 'rounded-2xl bg-surface' in rendered  # the card chrome


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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest core/tests/test_allauth_templates.py -v`

Expected: 2 FAIL — `account/_form_card.html` and `account/_input.html` don't exist yet.

- [ ] **Step 3: Create `_input.html`**

Create `templates/account/_input.html`:

```html
{# Single form field render. #}
{# Args: #}
{#   field — bound form field (required) #}
{#   type — input type (default "text"; pass "email", "password", "url", etc.) #}
{#   label — visible label text (default field.label) #}
{#   autocomplete — HTML autocomplete attribute (optional) #}
{#   help_text — override for field.help_text (optional) #}
{#   required — pass `False` to drop the required attribute (default True) #}
<div class="space-y-1.5">
    <label for="{{ field.id_for_label }}" class="block text-sm font-medium">
        {{ label|default:field.label }}
    </label>
    <input type="{{ type|default:'text' }}"
           name="{{ field.html_name }}"
           id="{{ field.id_for_label }}"
           value="{{ field.value|default:'' }}"
           {% if autocomplete %}autocomplete="{{ autocomplete }}"{% endif %}
           {% if required|default:True %}required{% endif %}
           class="block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2.5 text-base shadow-sm focus:border-tertiary focus:outline-none focus:ring-2 focus:ring-tertiary/30">
    {% with help=help_text|default:field.help_text %}
        {% if help %}<p class="text-xs text-secondary">{{ help|safe }}</p>{% endif %}
    {% endwith %}
    {% if field.errors %}<p class="text-sm text-red-700">{{ field.errors|join:" " }}</p>{% endif %}
</div>
```

- [ ] **Step 4: Create `_form_card.html`**

Create `templates/account/_form_card.html`:

```html
{# Multi-level extends base for form-style allauth pages. #}
{# Leaf templates extend this and override blocks: pill, title, #}
{# headline, subtitle, action_url, fields, submit_label, extra_actions, #}
{# below_card. Note: leaves should override BOTH `title` and `headline` #}
{# (we don't try to share them via nested blocks — Django block lookup #}
{# doesn't support sibling-block inheritance cleanly). #}
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% endblock %}
{% block content %}
    <div class="mx-auto max-w-md">
        <div class="text-center mb-6">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">
                {% block pill %}{% trans "Espace membre" %}{% endblock %}
            </p>
            <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% block headline %}{% endblock %}
            </h1>
            <p class="mt-3 text-sm text-secondary">
                {% block subtitle %}{% endblock %}
            </p>
        </div>
        <div class="rounded-2xl bg-surface p-8 shadow-sm border border-secondary/15">
            <form method="post" action="{% block action_url %}{% endblock %}" class="space-y-5">
                {% csrf_token %}
                {% if form.non_field_errors %}
                    <div role="alert"
                         class="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
                        {{ form.non_field_errors }}
                    </div>
                {% endif %}
                {% block fields %}{% endblock %}
                <button type="submit"
                        class="w-full rounded-lg bg-tertiary px-4 py-2.5 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 focus:outline-none focus:ring-2 focus:ring-tertiary/40 min-h-tap">
                    {% block submit_label %}{% trans "Envoyer" %}{% endblock %}
                </button>
                {% block extra_actions %}{% endblock %}
            </form>
        </div>
        {% block below_card %}{% endblock %}
    </div>
{% endblock %}
```

(Each leaf template overrides both `title` and `headline` independently — slightly redundant typing but reliable. Django doesn't support sibling-block inheritance, so trying to share `<title>` and `<h1>` content through nested blocks runs into "block defined more than once" errors.)

- [ ] **Step 5: Run tests — expect PASS**

Run: `pytest core/tests/test_allauth_templates.py -v`

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/account/_input.html templates/account/_form_card.html core/tests/test_allauth_templates.py
git commit -m "feat(allauth): shared _input + _form_card partials"
```

---

## Task 2: Password-reset request flow

**Files:**
- Create: `templates/account/password_reset.html`
- Create: `templates/account/password_reset_done.html`
- Modify: `core/tests/test_allauth_templates.py`

- [ ] **Step 1: Write failing tests**

Append to `core/tests/test_allauth_templates.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest core/tests/test_allauth_templates.py -v -k password_reset_pages`

Expected: 2 FAIL — templates render via allauth's bundled versions which may have `errorlist` markup or differ from our brand markers.

- [ ] **Step 3: Create `password_reset.html`**

Create `templates/account/password_reset.html`:

```html
{% extends "account/_form_card.html" %}
{% load i18n %}
{% block title %}{% trans "Mot de passe oublié" %}{% endblock %}
{% block headline %}{% trans "Mot de passe oublié ?" %}{% endblock %}
{% block subtitle %}
    {% trans "Entrez votre email — nous vous enverrons un lien pour réinitialiser votre mot de passe." %}
{% endblock %}
{% block action_url %}{% url 'account_reset_password' %}{% endblock %}
{% block submit_label %}{% trans "Envoyer le lien" %}{% endblock %}
{% block fields %}
    {% include "account/_input.html" with field=form.email type="email" label=_("Email") autocomplete="email" %}
{% endblock %}
```

- [ ] **Step 4: Create `password_reset_done.html`**

Create `templates/account/password_reset_done.html`:

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Email envoyé" %}{% endblock %}
{% block content %}
    <div class="mx-auto max-w-md">
        <div class="text-center mb-6">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">
                {% trans "Espace membre" %}
            </p>
            <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% trans "Email envoyé" %}
            </h1>
            <p class="mt-3 text-sm text-secondary">
                {% trans "Si l'adresse correspond à un compte, vous recevrez un lien sous quelques minutes. Vérifiez aussi vos spams." %}
            </p>
        </div>
        <div class="rounded-2xl bg-surface p-8 shadow-sm border border-secondary/15 text-center">
            <p class="text-sm">
                <a href="{% url 'account_login' %}"
                   class="text-tertiary hover:underline">{% trans "Retour à la connexion" %}</a>
            </p>
        </div>
    </div>
{% endblock %}
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `pytest core/tests/test_allauth_templates.py -v -k password_reset_pages`

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/account/password_reset.html templates/account/password_reset_done.html core/tests/test_allauth_templates.py
git commit -m "feat(allauth): style password_reset request flow"
```

---

## Task 3: Password-reset-from-key flow (the critical one)

**Files:**
- Create: `templates/account/password_reset_from_key.html`
- Create: `templates/account/password_reset_from_key_done.html`
- Modify: `core/tests/test_allauth_templates.py`

This is the page cooptation candidates land on after clicking the email link. Has a `token_fail` conditional branch (when the token is expired/already-used).

- [ ] **Step 1: Write failing test for the success branch**

Append to `core/tests/test_allauth_templates.py`:

```python
@pytest.mark.django_db
def test_password_reset_from_key_done_page(client):
    """The 'password set' confirmation page renders with brand chrome."""
    response = client.get("/accounts/password/reset/key/done/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Les Retrouvailles" in body
    assert 'class="errorlist"' not in body


def test_password_reset_from_key_template_extends_base(rf):
    """The set-password page exists at the right path and extends base.html.
    Reaching it via test client is awkward (needs a real key generation +
    an interim GET-then-redirect dance allauth uses). Source-level check
    is sufficient for chrome assertions."""
    src = (TEMPLATES_DIR / "password_reset_from_key.html").read_text(encoding="utf-8")
    assert '{% extends "base.html" %}' in src
    assert "Les Retrouvailles" not in src  # base.html provides this; not duplicated
    assert "_input.html" in src or "form" in src  # uses our partial or hand-rolls form


def test_password_reset_from_key_token_fail_branch(rf):
    """Source contains the token_fail branch with a CTA back to /accounts/password/reset/."""
    src = (TEMPLATES_DIR / "password_reset_from_key.html").read_text(encoding="utf-8")
    assert "token_fail" in src
    assert "account_reset_password" in src  # the CTA URL name
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest core/tests/test_allauth_templates.py -v -k password_reset_from_key`

Expected: 3 FAIL — file doesn't exist yet.

- [ ] **Step 3: Create `password_reset_from_key.html`**

Create `templates/account/password_reset_from_key.html`. This template extends `base.html` directly (NOT `_form_card.html`) because the `token_fail` branch needs a different layout (no form):

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Choisissez votre mot de passe" %}{% endblock %}
{% block content %}
    <div class="mx-auto max-w-md">
        {% if token_fail %}
            <div class="text-center mb-6">
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-secondary">
                    {% trans "Lien expiré" %}
                </p>
                <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                    {% trans "Lien invalide ou déjà utilisé" %}
                </h1>
                <p class="mt-3 text-sm text-secondary">
                    {% trans "Ce lien de réinitialisation n'est plus valide. Demandez un nouveau lien ci-dessous." %}
                </p>
            </div>
            <div class="rounded-2xl bg-surface p-8 shadow-sm border border-secondary/15 text-center">
                <a href="{% url 'account_reset_password' %}"
                   class="inline-block rounded-lg bg-tertiary px-6 py-2.5 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 transition min-h-tap">
                    {% trans "Demander un nouveau lien" %}
                </a>
            </div>
        {% else %}
            <div class="text-center mb-6">
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">
                    {% trans "Bienvenue" %}
                </p>
                <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                    {% trans "Choisissez votre mot de passe" %}
                </h1>
                <p class="mt-3 text-sm text-secondary">
                    {% trans "Une dernière étape avant de rejoindre les retrouvailles." %}
                </p>
            </div>
            <div class="rounded-2xl bg-surface p-8 shadow-sm border border-secondary/15">
                <form method="post" action="{{ action_url }}" class="space-y-5">
                    {% csrf_token %}
                    {% if form.non_field_errors %}
                        <div role="alert"
                             class="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
                            {{ form.non_field_errors }}
                        </div>
                    {% endif %}
                    {% include "account/_input.html" with field=form.password1 type="password" label=_("Nouveau mot de passe") autocomplete="new-password" %}
                    {% include "account/_input.html" with field=form.password2 type="password" label=_("Confirmer le mot de passe") autocomplete="new-password" %}
                    <button type="submit"
                            class="w-full rounded-lg bg-tertiary px-4 py-2.5 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 focus:outline-none focus:ring-2 focus:ring-tertiary/40 min-h-tap">
                        {% trans "Enregistrer" %}
                    </button>
                </form>
            </div>
        {% endif %}
    </div>
{% endblock %}
```

- [ ] **Step 4: Create `password_reset_from_key_done.html`**

Create `templates/account/password_reset_from_key_done.html`:

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Mot de passe enregistré" %}{% endblock %}
{% block content %}
    <div class="mx-auto max-w-md">
        <div class="text-center mb-6">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">
                {% trans "Espace membre" %}
            </p>
            <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% trans "Mot de passe enregistré" %}
            </h1>
            <p class="mt-3 text-sm text-secondary">
                {% trans "Vous pouvez maintenant vous connecter avec votre nouveau mot de passe." %}
            </p>
        </div>
        <div class="rounded-2xl bg-surface p-8 shadow-sm border border-secondary/15 text-center">
            <a href="{% url 'account_login' %}"
               class="inline-block rounded-lg bg-tertiary px-6 py-2.5 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 transition min-h-tap">
                {% trans "Se connecter" %}
            </a>
        </div>
    </div>
{% endblock %}
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `pytest core/tests/test_allauth_templates.py -v -k password_reset_from_key`

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/account/password_reset_from_key.html templates/account/password_reset_from_key_done.html core/tests/test_allauth_templates.py
git commit -m "feat(allauth): style password_reset_from_key (incl token_fail branch)"
```

---

## Task 4: Logged-in password management

**Files:**
- Create: `templates/account/password_change.html`
- Create: `templates/account/password_set.html`
- Modify: `core/tests/test_allauth_templates.py`

- [ ] **Step 1: Write failing tests**

Append to `core/tests/test_allauth_templates.py` (top of the file, ensure these fixtures are available — add a `member_client` fixture if not already present):

```python
@pytest.fixture
def member_client(db):
    """Logged-in member with charter consent (passes ConsentRequiredMiddleware)."""
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
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `pytest core/tests/test_allauth_templates.py::test_password_change_renders_with_brand_chrome -v`

Expected: FAIL.

- [ ] **Step 3: Create `password_change.html`**

Create `templates/account/password_change.html`:

```html
{% extends "account/_form_card.html" %}
{% load i18n %}
{% block title %}{% trans "Changer mon mot de passe" %}{% endblock %}
{% block headline %}{% trans "Changer mon mot de passe" %}{% endblock %}
{% block subtitle %}{% trans "Pour la sécurité de votre compte." %}{% endblock %}
{% block action_url %}{% url 'account_change_password' %}{% endblock %}
{% block submit_label %}{% trans "Enregistrer" %}{% endblock %}
{% block fields %}
    {% include "account/_input.html" with field=form.oldpassword type="password" label=_("Mot de passe actuel") autocomplete="current-password" %}
    {% include "account/_input.html" with field=form.password1 type="password" label=_("Nouveau mot de passe") autocomplete="new-password" %}
    {% include "account/_input.html" with field=form.password2 type="password" label=_("Confirmer le nouveau mot de passe") autocomplete="new-password" %}
{% endblock %}
{% block extra_actions %}
    <p class="mt-3 text-center text-sm">
        <a href="{% url 'account_reset_password' %}"
           class="text-tertiary hover:underline">{% trans "Mot de passe oublié ?" %}</a>
    </p>
{% endblock %}
```

- [ ] **Step 4: Create `password_set.html`**

Create `templates/account/password_set.html`:

```html
{% extends "account/_form_card.html" %}
{% load i18n %}
{% block title %}{% trans "Définir un mot de passe" %}{% endblock %}
{% block headline %}{% trans "Définir un mot de passe" %}{% endblock %}
{% block subtitle %}{% trans "Choisissez un mot de passe pour votre compte." %}{% endblock %}
{% block action_url %}{% url 'account_set_password' %}{% endblock %}
{% block submit_label %}{% trans "Enregistrer" %}{% endblock %}
{% block fields %}
    {% include "account/_input.html" with field=form.password1 type="password" label=_("Mot de passe") autocomplete="new-password" %}
    {% include "account/_input.html" with field=form.password2 type="password" label=_("Confirmer le mot de passe") autocomplete="new-password" %}
{% endblock %}
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `pytest core/tests/test_allauth_templates.py -v`

Expected: ALL PASS so far (~7 tests).

- [ ] **Step 6: Commit**

```bash
git add templates/account/password_change.html templates/account/password_set.html core/tests/test_allauth_templates.py
git commit -m "feat(allauth): style logged-in password management pages"
```

---

## Task 5: Email management (`email`, `email_change`, `email_confirm`, `verification_sent`)

**Files:**
- Create: `templates/account/email.html`
- Create: `templates/account/email_change.html`
- Create: `templates/account/email_confirm.html`
- Create: `templates/account/verification_sent.html`
- Modify: `core/tests/test_allauth_templates.py`

- [ ] **Step 1: Write failing tests**

Append to `core/tests/test_allauth_templates.py`:

```python
@pytest.mark.django_db
def test_email_management_page_renders_with_brand_chrome(member_client):
    response = member_client.get("/accounts/email/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Les Retrouvailles" in body
    assert 'class="errorlist"' not in body


@pytest.mark.django_db
def test_verification_sent_page_template_extends_base():
    """verification_sent.html is rare to GET (depends on email-verification flow);
    source-level check is enough."""
    src = (TEMPLATES_DIR / "verification_sent.html").read_text(encoding="utf-8")
    assert '{% extends "base.html" %}' in src
    assert "verification" in src.lower()


@pytest.mark.django_db
def test_email_change_template_extends_form_card():
    src = (TEMPLATES_DIR / "email_change.html").read_text(encoding="utf-8")
    assert '{% extends "account/_form_card.html" %}' in src


@pytest.mark.django_db
def test_email_confirm_template_extends_form_card():
    src = (TEMPLATES_DIR / "email_confirm.html").read_text(encoding="utf-8")
    assert '{% extends "account/_form_card.html" %}' in src
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest core/tests/test_allauth_templates.py -v -k email`

Expected: 4 FAIL.

- [ ] **Step 3: Create `email.html`**

Create `templates/account/email.html` (extends `base.html` directly because the layout is a list + an add-form, not a single form):

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Mes adresses email" %}{% endblock %}
{% block content %}
    <div class="mx-auto max-w-2xl">
        <div class="text-center mb-6">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">
                {% trans "Espace membre" %}
            </p>
            <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% trans "Mes adresses email" %}
            </h1>
            <p class="mt-3 text-sm text-secondary">
                {% trans "Gérez l'adresse principale et les adresses associées à votre compte." %}
            </p>
        </div>
        {% if emailaddresses %}
            <form method="post" action="{% url 'account_email' %}"
                  class="rounded-2xl bg-surface p-6 shadow-sm border border-secondary/15 space-y-4">
                {% csrf_token %}
                <p class="text-sm text-secondary">
                    {% trans "Adresses associées à ce compte :" %}
                </p>
                <ul class="space-y-2">
                    {% for radio in emailaddress_radios %}
                        {% with emailaddress=radio.emailaddress %}
                            <li class="flex items-center gap-3 p-2 rounded-lg hover:bg-base-200">
                                <input type="radio"
                                       name="email"
                                       value="{{ emailaddress.email }}"
                                       id="{{ radio.id }}"
                                       {% if radio.checked %}checked{% endif %}
                                       class="h-4 w-4 text-tertiary focus:ring-tertiary">
                                <label for="{{ radio.id }}" class="flex-1 text-sm">
                                    {{ emailaddress.email }}
                                    {% if emailaddress.verified %}
                                        <span class="ml-2 inline-block rounded-full bg-tertiary/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-tertiary">{% trans "Vérifiée" %}</span>
                                    {% else %}
                                        <span class="ml-2 inline-block rounded-full bg-yellow-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-yellow-800">{% trans "Non vérifiée" %}</span>
                                    {% endif %}
                                    {% if emailaddress.primary %}
                                        <span class="ml-2 inline-block rounded-full bg-ceremonial-gold/20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-ceremonial-gold">{% trans "Principale" %}</span>
                                    {% endif %}
                                </label>
                            </li>
                        {% endwith %}
                    {% endfor %}
                </ul>
                <div class="flex flex-wrap gap-2 pt-2">
                    <button type="submit" name="action_primary"
                            class="rounded-lg bg-tertiary px-4 py-2 text-sm font-medium text-on-tertiary shadow-sm hover:opacity-95 min-h-tap">
                        {% trans "Définir comme principale" %}
                    </button>
                    <button type="submit" name="action_send"
                            class="rounded-lg border border-secondary/25 bg-white px-4 py-2 text-sm font-medium hover:border-tertiary/40 hover:text-tertiary min-h-tap">
                        {% trans "Renvoyer la vérification" %}
                    </button>
                    <button type="submit" name="action_remove"
                            class="rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-100 min-h-tap"
                            onclick="return confirm('{% trans "Confirmer la suppression de cette adresse ?" %}');">
                        {% trans "Supprimer" %}
                    </button>
                </div>
            </form>
        {% endif %}
        {% if can_add_email %}
            <div class="mt-8 rounded-2xl bg-surface p-6 shadow-sm border border-secondary/15">
                <h2 class="font-display text-xl font-semibold tracking-tight mb-4">
                    {% trans "Ajouter une adresse" %}
                </h2>
                <form method="post" action="{% url 'account_email' %}" class="space-y-4">
                    {% csrf_token %}
                    {% if form.non_field_errors %}
                        <div role="alert"
                             class="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
                            {{ form.non_field_errors }}
                        </div>
                    {% endif %}
                    {% include "account/_input.html" with field=form.email type="email" label=_("Nouvelle adresse") autocomplete="email" %}
                    <button type="submit" name="action_add"
                            class="rounded-lg bg-tertiary px-4 py-2.5 text-sm font-medium text-on-tertiary shadow-sm hover:opacity-95 min-h-tap">
                        {% trans "Ajouter" %}
                    </button>
                </form>
            </div>
        {% endif %}
    </div>
{% endblock %}
```

- [ ] **Step 4: Create `email_change.html`**

Create `templates/account/email_change.html`:

```html
{% extends "account/_form_card.html" %}
{% load i18n %}
{% block title %}{% trans "Changer mon adresse email" %}{% endblock %}
{% block headline %}{% trans "Changer mon adresse email" %}{% endblock %}
{% block subtitle %}{% trans "Vous recevrez un lien de confirmation à la nouvelle adresse." %}{% endblock %}
{% block action_url %}{% url 'account_change_email' %}{% endblock %}
{% block submit_label %}{% trans "Enregistrer" %}{% endblock %}
{% block fields %}
    {% include "account/_input.html" with field=form.email type="email" label=_("Nouvelle adresse email") autocomplete="email" %}
{% endblock %}
```

- [ ] **Step 5: Create `email_confirm.html`**

Create `templates/account/email_confirm.html`:

```html
{% extends "account/_form_card.html" %}
{% load i18n %}
{% block title %}{% trans "Confirmer cette adresse email" %}{% endblock %}
{% block headline %}{% trans "Confirmer cette adresse email" %}{% endblock %}
{% block subtitle %}
    {% if confirmation %}
        {% blocktrans with email=confirmation.email_address.email %}Cliquez sur Confirmer pour valider l'adresse {{ email }}.{% endblocktrans %}
    {% else %}
        {% trans "Lien de confirmation invalide ou expiré." %}
    {% endif %}
{% endblock %}
{% block action_url %}{% url 'account_confirm_email' confirmation.key %}{% endblock %}
{% block submit_label %}{% trans "Confirmer" %}{% endblock %}
{% block fields %}{# no input fields — just the confirm button #}{% endblock %}
```

- [ ] **Step 6: Create `verification_sent.html`**

Create `templates/account/verification_sent.html`:

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Email de vérification envoyé" %}{% endblock %}
{% block content %}
    <div class="mx-auto max-w-md">
        <div class="text-center mb-6">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">
                {% trans "Espace membre" %}
            </p>
            <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% trans "Email de vérification envoyé" %}
            </h1>
            <p class="mt-3 text-sm text-secondary">
                {% trans "Vérifiez votre boîte de réception et cliquez sur le lien pour activer votre compte." %}
            </p>
        </div>
    </div>
{% endblock %}
```

- [ ] **Step 7: Run tests — expect PASS**

Run: `pytest core/tests/test_allauth_templates.py -v -k email`

Expected: 4 PASS.

- [ ] **Step 8: Commit**

```bash
git add templates/account/email.html templates/account/email_change.html templates/account/email_confirm.html templates/account/verification_sent.html core/tests/test_allauth_templates.py
git commit -m "feat(allauth): style email management + verification pages"
```

---

## Task 6: Edge-case templates (`account_inactive`, `verified_email_required`, `reauthenticate`)

**Files:**
- Create: `templates/account/account_inactive.html`
- Create: `templates/account/verified_email_required.html`
- Create: `templates/account/reauthenticate.html`
- Modify: `core/tests/test_allauth_templates.py`

- [ ] **Step 1: Write failing tests (file-level checks since runtime GET is awkward)**

Append to `core/tests/test_allauth_templates.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest core/tests/test_allauth_templates.py -v -k edge_case`

Expected: 3 FAIL — files don't exist.

- [ ] **Step 3: Create `account_inactive.html`**

Create `templates/account/account_inactive.html`:

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Compte inactif" %}{% endblock %}
{% block content %}
    <div class="mx-auto max-w-md">
        <div class="text-center mb-6">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-secondary">
                {% trans "Espace membre" %}
            </p>
            <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% trans "Compte inactif" %}
            </h1>
            <p class="mt-3 text-sm text-secondary">
                {% trans "Votre compte n'est plus actif. Contactez l'équipe si vous pensez qu'il s'agit d'une erreur." %}
            </p>
        </div>
    </div>
{% endblock %}
```

- [ ] **Step 4: Create `verified_email_required.html`**

Create `templates/account/verified_email_required.html`:

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Vérification requise" %}{% endblock %}
{% block content %}
    <div class="mx-auto max-w-md">
        <div class="text-center mb-6">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">
                {% trans "Espace membre" %}
            </p>
            <h1 class="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% trans "Vérification requise" %}
            </h1>
            <p class="mt-3 text-sm text-secondary">
                {% trans "Veuillez confirmer votre adresse email avant de continuer. Un email de vérification vous a été envoyé." %}
            </p>
        </div>
        <div class="rounded-2xl bg-surface p-8 shadow-sm border border-secondary/15 text-center">
            <a href="{% url 'account_email' %}"
               class="text-sm text-tertiary hover:underline">
                {% trans "Gérer mes adresses email" %}
            </a>
        </div>
    </div>
{% endblock %}
```

- [ ] **Step 5: Create `reauthenticate.html`**

Create `templates/account/reauthenticate.html`:

```html
{% extends "account/_form_card.html" %}
{% load i18n %}
{% block title %}{% trans "Confirmation de sécurité" %}{% endblock %}
{% block headline %}{% trans "Confirmation de sécurité" %}{% endblock %}
{% block subtitle %}{% trans "Veuillez saisir votre mot de passe pour confirmer cette opération." %}{% endblock %}
{% block action_url %}{% url 'account_reauthenticate' %}{% endblock %}
{% block submit_label %}{% trans "Confirmer" %}{% endblock %}
{% block fields %}
    {% include "account/_input.html" with field=form.password type="password" label=_("Mot de passe") autocomplete="current-password" %}
{% endblock %}
```

- [ ] **Step 6: Run tests — expect PASS**

Run: `pytest core/tests/test_allauth_templates.py -v -k edge_case`

Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add templates/account/account_inactive.html templates/account/verified_email_required.html templates/account/reauthenticate.html core/tests/test_allauth_templates.py
git commit -m "feat(allauth): style edge-case account pages"
```

---

## Task 7: Resilience signup override + negative test

**Files:**
- Create: `templates/account/signup.html`
- Modify: `core/tests/test_allauth_templates.py`

The current `NoSignupAdapter` blocks signup and the user lands on `signup_closed.html` instead. But if the policy is ever flipped (`is_open_for_signup = True`), the page should already be on-brand. This task is pure resilience.

- [ ] **Step 1: Write failing tests**

Append to `core/tests/test_allauth_templates.py`:

```python
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
    # Error message is rendered (specific French copy depends on allauth's
    # localization, but at minimum some "non valide" or "valid" word appears).
    assert "valid" in body.lower()  # English fallback covers if i18n is off
```

- [ ] **Step 2: Run tests — expect FAIL on first; PASS on second already (existing _form_card-extending templates already pass through the negative test path because the pattern produces no `errorlist`)**

Run: `pytest core/tests/test_allauth_templates.py -v -k "signup_template or failing_post"`

Expected: 1 FAIL (signup template), 1 may PASS (negative test — depends on allauth's bundled `password_reset.html` being already overridden by Task 2).

- [ ] **Step 3: Create `signup.html`**

Create `templates/account/signup.html`:

```html
{% extends "account/_form_card.html" %}
{% load i18n %}
{% block title %}{% trans "Inscription" %}{% endblock %}
{% block pill %}{% trans "Inscription" %}{% endblock %}
{% block headline %}{% trans "Bienvenue parmi les anciens" %}{% endblock %}
{% block subtitle %}
    {% trans "Cette plateforme est privée. Pour vous inscrire, demandez à deux camarades de vous coopter." %}
{% endblock %}
{% block action_url %}{% url 'account_signup' %}{% endblock %}
{% block submit_label %}{% trans "S'inscrire" %}{% endblock %}
{% block fields %}
    {% include "account/_input.html" with field=form.email type="email" label=_("Email") autocomplete="email" %}
    {% include "account/_input.html" with field=form.password1 type="password" label=_("Mot de passe") autocomplete="new-password" %}
    {% include "account/_input.html" with field=form.password2 type="password" label=_("Confirmer le mot de passe") autocomplete="new-password" %}
{% endblock %}
{% block below_card %}
    <p class="mt-6 text-center text-sm text-secondary">
        <a href="{% url 'cooptation:signup' %}" class="text-tertiary hover:underline">
            {% trans "← Demander une cooptation à la place" %}
        </a>
    </p>
{% endblock %}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest core/tests/test_allauth_templates.py -v`

Expected: ALL allauth-template tests pass.

- [ ] **Step 5: Run full test suite to confirm no regressions**

Run: `pytest --ignore=members/tests/test_cloudinary_sign.py --tb=short`

Expected: ALL PASS. Test count should be ~387 (post-P5a) + ~14 new = ~401.

- [ ] **Step 6: Commit**

```bash
git add templates/account/signup.html core/tests/test_allauth_templates.py
git commit -m "feat(allauth): style signup (resilience override) + negative POST test"
```

---

## Task 8: STATUS update + final verification

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Add row to Phase Index**

Open `docs/superpowers/STATUS.md`. The Phase Index table is near the top. Insert a new row AFTER the existing P5a row. Format mirrors other phases:

```markdown
| Allauth styling | Allauth template overrides (full /accounts/* visual coverage) | Complete (2026-05-04) | [plan](plans/2026-05-04-styled-allauth-templates.md) |
```

(This phase doesn't fit the P-numbered roadmap because it's a polish phase, not a master-spec phase. Use the descriptive label.)

- [ ] **Step 2: Add a phase section**

Append a new section to `docs/superpowers/STATUS.md`. Place it after the existing P5a section.

```markdown
## Allauth template styling

**Shipped:** 2026-05-04
**Plan:** [plans/2026-05-04-styled-allauth-templates.md](plans/2026-05-04-styled-allauth-templates.md)
**Spec:** [specs/2026-05-04-styled-allauth-templates-design.md](specs/2026-05-04-styled-allauth-templates-design.md)
**Test suite:** all passing (~14 new tests)

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Shared partials (_input + _form_card) + smoke tests | [x] | _filled by implementer_ |
| 2 | Password-reset request flow (2 templates) | [x] | _filled by implementer_ |
| 3 | Password-reset-from-key flow (2 templates incl. token_fail) | [x] | _filled by implementer_ |
| 4 | Logged-in password mgmt (2 templates) | [x] | _filled by implementer_ |
| 5 | Email management (4 templates) | [x] | _filled by implementer_ |
| 6 | Edge-case templates (3 templates) | [x] | _filled by implementer_ |
| 7 | Signup resilience override + negative POST test | [x] | _filled by implementer_ |
| 8 | STATUS.md update | [x] | (this commit) |

---
```

- [ ] **Step 3: Fill in commit SHAs**

Run: `git log --oneline | head -10`

Map each task to its terminal SHA. Replace each `_filled by implementer_` placeholder with the actual short SHA.

- [ ] **Step 4: Run full test suite**

Run: `pytest --ignore=members/tests/test_cloudinary_sign.py --tb=short`

Expected: ALL PASS (~401 tests).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(allauth): mark Allauth template styling complete in STATUS"
```

---

## Final verification checklist

After Task 8 commits:

- [ ] `pytest --ignore=members/tests/test_cloudinary_sign.py` exits clean.
- [ ] `git log --oneline | head -15` shows all phase commits in order.
- [ ] **Manual smoke** (against local runserver, since this phase is purely visual):
  1. Visit `/accounts/login/` — already styled, sanity check.
  2. Visit `/accounts/password/reset/` — should show new pill + "Mot de passe oublié ?" headline + email input.
  3. POST a junk email — should show styled red alert, NOT `errorlist`.
  4. Visit `/accounts/password/reset/done/` — should show "Email envoyé" info card.
  5. Generate a real password reset email (or use shell to build a key) and visit `/accounts/password/reset/key/<key>-set-password/` — should show "Bienvenue" + "Choisissez votre mot de passe" + 2 password fields.
  6. Visit `/accounts/password/reset/key/invalid-token-set-password/` — should show "Lien expiré" branch + CTA back to /accounts/password/reset/.
  7. Log in. Visit `/accounts/password/change/` — styled form.
  8. Visit `/accounts/email/` — styled list of email addresses + add-email form.

---

## What this plan does NOT do (per spec §Non-goals)

- No phone-based / passkey / code-login templates.
- No abstract `base_*.html` overrides.
- No allauth `snippets/` overrides.
- No retrofit of the existing 3 styled templates into the new partial pattern.
- No branded email-template (TXT) overrides — separate phase.
