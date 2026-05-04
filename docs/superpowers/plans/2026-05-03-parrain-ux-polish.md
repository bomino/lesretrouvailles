# P3.1 — Parrain UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a member-only pending-vouches dashboard at `/cooptations-a-valider/` with a nav badge, and bump session lifetime to 90 days with sliding expiry — so parrains can find pending requests easily and stay logged in across email clicks.

**Architecture:** Three independent additions. (A) New `parrain_dashboard_view` lists `CooptationRequest` rows where the current user is the named parrain and the request is still actionable. (B) New `pending_vouches_count` context processor exposes a count for a small numeric badge in the auth nav. (C) Settings change to `SESSION_COOKIE_AGE` (90 days) plus `SESSION_SAVE_EVERY_REQUEST` (slides expiry forward on every request). No DB migrations, no new emails, no new dependencies.

**Tech Stack:** Django 5.0, PostgreSQL, pytest-django, Tailwind/DaisyUI utility classes (existing design tokens only).

**Spec:** `docs/superpowers/specs/2026-05-03-parrain-ux-polish-design.md`

---

## File Structure

**Create:**
- `cooptation/context_processors.py` — single `pending_vouches_count` function returning `{"pending_vouches_count": int}`.
- `cooptation/templates/cooptation/parrain_dashboard.html` — extends `base.html`, renders pending list or empty state.
- `cooptation/tests/test_parrain_dashboard.py` — view tests (auth, empty state, listing, identity isolation, filtering, link correctness).
- `cooptation/tests/test_pending_vouches_count.py` — context processor + nav badge integration tests.
- `alumni/tests/__init__.py` — package marker (may already exist; idempotent).
- `alumni/tests/test_session_settings.py` — single assertion test for session config.

**Modify:**
- `cooptation/urls.py` — add the `parrain_dashboard` route.
- `cooptation/views.py` — add `parrain_dashboard_view`.
- `templates/base.html` — add nav link + conditional badge in both desktop and mobile nav.
- `alumni/settings/base.py` — add `SESSION_COOKIE_AGE`, `SESSION_SAVE_EVERY_REQUEST`, register the new context processor.

---

## Task Order Rationale

1. **Task 1 (Session settings):** Smallest, fully isolated, gives an immediate green test.
2. **Task 2 (Dashboard view):** Foundational; the page must exist before the nav can link to it.
3. **Task 3 (Context processor):** Independent of the view but the badge in Task 4 needs it.
4. **Task 4 (Nav integration):** Wires Tasks 2 + 3 into `base.html`.
5. **Task 5 (STATUS.md update):** Housekeeping commit.

---

## Task 1: Session lifetime configuration

**Files:**
- Create: `alumni/tests/test_session_settings.py`
- Modify: `alumni/settings/base.py`

- [ ] **Step 1: Verify alumni/tests/ exists as a package**

Run:
```bash
ls alumni/tests/__init__.py 2>&1 || mkdir -p alumni/tests && touch alumni/tests/__init__.py
```

Expected: either the file exists (no-op output) or it's created. If created, also create the file:

```python
# alumni/tests/__init__.py
```

(Empty file — package marker only.)

- [ ] **Step 2: Write the failing test**

Create `alumni/tests/test_session_settings.py`:

```python
"""Session cookie config: 90-day sliding expiry so parrains stay logged in
between cooptation email clicks (P3.1 spec)."""

from django.conf import settings


def test_session_cookie_age_is_90_days():
    assert settings.SESSION_COOKIE_AGE == 60 * 60 * 24 * 90


def test_session_saves_every_request_for_sliding_expiry():
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest alumni/tests/test_session_settings.py -v`

Expected: 2 FAIL — Django defaults are `SESSION_COOKIE_AGE = 1209600` (2 weeks) and `SESSION_SAVE_EVERY_REQUEST = False`.

- [ ] **Step 4: Add settings**

Edit `alumni/settings/base.py`. Insert these lines after the `LOGIN_REDIRECT_URL = "/"` / `LOGOUT_REDIRECT_URL = "/"` block (around line 118):

```python
# P3.1: 90-day sliding session lifetime so parrains stay logged in across
# cooptation email clicks (~2 weeks per request × multiple requests in flight).
# SAVE_EVERY_REQUEST trades one session-row write per request for sliding
# expiry — negligible cost at our scale, big UX win.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90 days
SESSION_SAVE_EVERY_REQUEST = True
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest alumni/tests/test_session_settings.py -v`

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add alumni/tests/__init__.py alumni/tests/test_session_settings.py alumni/settings/base.py
git commit -m "feat(p3.1): 90-day sliding session for parrain UX"
```

---

## Task 2: Pending-vouches dashboard

**Files:**
- Create: `cooptation/templates/cooptation/parrain_dashboard.html`
- Create: `cooptation/tests/test_parrain_dashboard.py`
- Modify: `cooptation/urls.py`
- Modify: `cooptation/views.py`

### 2a — URL + view + template scaffold (just enough to render)

- [ ] **Step 1: Write the first failing test (anonymous redirect)**

Create `cooptation/tests/test_parrain_dashboard.py`:

```python
"""Pending-vouches dashboard at /cooptations-a-valider/ — member-only listing
of CooptationRequests still awaiting a response from the current user."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


URL = "/cooptations-a-valider/"


@pytest.mark.django_db
def test_anonymous_user_redirects_to_login():
    response = Client().get(URL)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest cooptation/tests/test_parrain_dashboard.py -v`

Expected: FAIL with 404 (URL not registered).

- [ ] **Step 3: Add the URL route**

Edit `cooptation/urls.py`. Add the new path between `signup_success` and `parrain_vouch`:

```python
from django.urls import path

from . import views

app_name = "cooptation"

urlpatterns = [
    path("inscription/", views.signup_view, name="signup"),
    path("inscription/merci/", views.signup_success_view, name="signup_success"),
    path("cooptations-a-valider/", views.parrain_dashboard_view, name="parrain_dashboard"),
    path("cooptation/<str:token>/", views.parrain_vouch_view, name="parrain_vouch"),
    path("questionnaire/<str:token>/", views.questionnaire_view, name="questionnaire"),
]
```

- [ ] **Step 4: Add the view function**

Edit `cooptation/views.py`. Add this function immediately after the existing `signup_success_view` (around line 113):

```python
@login_required
@require_http_methods(["GET"])
def parrain_dashboard_view(request):
    """Member-only listing of CooptationRequests awaiting the current user's
    response. Mirrors the per-token /cooptation/<token>/ page but as an index
    so parrains don't have to dig through email to find pending requests.

    Filters: response='pending' AND expires_at > now AND parrain == me.
    Already-answered or expired requests are hidden — clicking them would
    just hit the 410 page on parrain_vouch_view.
    """
    member = getattr(request.user, "member", None)
    pending = []
    if member is not None:
        pending = list(
            CooptationRequest.objects.filter(
                parrain=member,
                response="pending",
                expires_at__gt=timezone.now(),
            )
            .select_related("application")
            .order_by("expires_at")
        )
    return render(request, "cooptation/parrain_dashboard.html", {"pending": pending})
```

- [ ] **Step 5: Create minimal template**

Create `cooptation/templates/cooptation/parrain_dashboard.html`:

```html
{% extends "base.html" %}
{% load i18n %}
{% block title %}
    {% trans "Cooptations à valider" %}
{% endblock %}
{% block content %}
    <div class="mx-auto max-w-3xl">
        <header class="mb-8">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-tertiary">
                {% trans "Espace parrain" %}
            </p>
            <h1 class="mt-2 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                {% trans "Cooptations en attente de votre validation" %}
            </h1>
            <p class="mt-3 text-sm text-secondary">
                {% trans "Voici les candidatures qui attendent votre accord. Cliquez pour répondre." %}
            </p>
        </header>
        {% if pending %}
            <ul class="space-y-4">
                {% for request_obj in pending %}
                    <li class="rounded-2xl border border-secondary/15 bg-surface/70 p-5 shadow-sm">
                        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                            <div>
                                <p class="font-display text-lg font-semibold">{{ request_obj.application.full_name }}</p>
                                <p class="mt-1 text-sm text-secondary">
                                    {{ request_obj.application.years_attended|join:", " }}
                                    {% if request_obj.application.city %}
                                        · {{ request_obj.application.city }}
                                        {% if request_obj.application.country %}, {{ request_obj.application.country }}{% endif %}
                                    {% endif %}
                                </p>
                                <p class="mt-1 text-xs text-secondary">
                                    {% blocktrans with delta=request_obj.expires_at|timeuntil %}Expire dans {{ delta }}{% endblocktrans %}
                                </p>
                            </div>
                            <a href="{% url 'cooptation:parrain_vouch' request_obj.token %}"
                               class="inline-flex items-center gap-2 rounded-lg bg-tertiary px-5 py-2.5 text-sm font-medium text-on-tertiary shadow-sm hover:opacity-95 transition min-h-tap">
                                {% trans "Répondre" %}
                                <span aria-hidden="true">→</span>
                            </a>
                        </div>
                    </li>
                {% endfor %}
            </ul>
        {% else %}
            <div class="rounded-2xl border border-secondary/15 bg-surface/70 p-8 text-center shadow-sm">
                <p class="text-base text-secondary">
                    {% trans "Vous n'avez aucune cooptation en attente. Merci de votre vigilance." %}
                </p>
            </div>
        {% endif %}
    </div>
{% endblock %}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest cooptation/tests/test_parrain_dashboard.py -v`

Expected: 1 PASS.

- [ ] **Step 7: Commit**

```bash
git add cooptation/urls.py cooptation/views.py cooptation/templates/cooptation/parrain_dashboard.html cooptation/tests/test_parrain_dashboard.py
git commit -m "feat(p3.1): scaffold parrain dashboard view + URL + template"
```

### 2b — Empty state for authenticated user without Member

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_parrain_dashboard.py`:

```python
@pytest.mark.django_db
def test_authenticated_user_without_member_sees_empty_state(make_user):
    """Admin or any auth'd user with no Member profile gets an empty list,
    not a 500 — the view defends with getattr(..., 'member', None)."""
    user = make_user(password="x")
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get(URL)
    assert response.status_code == 200
    assert b"aucune cooptation en attente" in response.content
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest cooptation/tests/test_parrain_dashboard.py::test_authenticated_user_without_member_sees_empty_state -v`

Expected: PASS — view already handles this branch.

- [ ] **Step 3: Commit**

```bash
git add cooptation/tests/test_parrain_dashboard.py
git commit -m "test(p3.1): empty state for auth user without Member"
```

### 2c — Empty state for member with zero pending

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_parrain_dashboard.py`:

```python
@pytest.mark.django_db
def test_member_with_zero_pending_sees_empty_state(make_member, make_user):
    user = make_user(password="x")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get(URL)
    assert response.status_code == 200
    assert b"aucune cooptation en attente" in response.content
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest cooptation/tests/test_parrain_dashboard.py::test_member_with_zero_pending_sees_empty_state -v`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add cooptation/tests/test_parrain_dashboard.py
git commit -m "test(p3.1): empty state for member with no pending vouches"
```

### 2d — Member with pending requests sees them

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_parrain_dashboard.py`:

```python
@pytest.mark.django_db
def test_member_with_pending_sees_candidates_ordered_by_urgency(
    make_cooptation_request, make_application
):
    """Two pending requests for the same parrain — both candidates render,
    soonest-to-expire first."""
    req1 = make_cooptation_request(
        application=make_application(full_name="Aïssa Soumana"),
    )
    parrain = req1.parrain
    # Second request for the SAME parrain, expiring sooner
    req2 = make_cooptation_request(
        application=make_application(full_name="Boubacar Issoufou"),
        parrain=parrain,
        expires_at=timezone.now() + timedelta(days=2),
    )
    # Push req1 expiry further out so req2 should sort first
    req1.expires_at = timezone.now() + timedelta(days=10)
    req1.save()

    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=parrain.user.username, password="x")

    response = c.get(URL)
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "Aïssa Soumana" in body
    assert "Boubacar Issoufou" in body
    # Order: Boubacar (expires in 2 days) appears before Aïssa (10 days)
    assert body.index("Boubacar Issoufou") < body.index("Aïssa Soumana")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest cooptation/tests/test_parrain_dashboard.py::test_member_with_pending_sees_candidates_ordered_by_urgency -v`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add cooptation/tests/test_parrain_dashboard.py
git commit -m "test(p3.1): pending list renders ordered by expires_at"
```

### 2e — Identity isolation

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_parrain_dashboard.py`:

```python
@pytest.mark.django_db
def test_member_does_not_see_another_members_pending(
    make_cooptation_request, make_member, make_user
):
    """Member B is logged in. The pending request belongs to Member A.
    Dashboard for B must not list A's request — full identity isolation."""
    req_for_a = make_cooptation_request()
    candidate_name = req_for_a.application.full_name

    user_b = make_user(password="x")
    member_b = make_member(user=user_b)
    ConsentRecord.objects.create(
        member=member_b, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )

    c = Client()
    c.login(username=user_b.username, password="x")
    response = c.get(URL)
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert candidate_name not in body
    assert "aucune cooptation en attente" in body
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest cooptation/tests/test_parrain_dashboard.py::test_member_does_not_see_another_members_pending -v`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add cooptation/tests/test_parrain_dashboard.py
git commit -m "test(p3.1): identity isolation between parrains"
```

### 2f — Already-answered requests hidden

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_parrain_dashboard.py`:

```python
@pytest.mark.django_db
@pytest.mark.parametrize("response_value", ["accepted", "refused"])
def test_already_answered_requests_are_hidden(make_cooptation_request, response_value):
    req = make_cooptation_request()
    req.response = response_value
    req.responded_at = timezone.now()
    req.save()
    candidate_name = req.application.full_name

    parrain = req.parrain
    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )

    c = Client()
    c.login(username=parrain.user.username, password="x")
    response = c.get(URL)
    assert candidate_name not in response.content.decode("utf-8")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest "cooptation/tests/test_parrain_dashboard.py::test_already_answered_requests_are_hidden" -v`

Expected: 2 PASS (parametrized).

- [ ] **Step 3: Commit**

```bash
git add cooptation/tests/test_parrain_dashboard.py
git commit -m "test(p3.1): hide already-answered requests"
```

### 2g — Expired requests hidden

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_parrain_dashboard.py`:

```python
@pytest.mark.django_db
def test_expired_requests_are_hidden(make_cooptation_request):
    req = make_cooptation_request()
    req.expires_at = timezone.now() - timedelta(hours=1)
    req.save()
    candidate_name = req.application.full_name

    parrain = req.parrain
    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )

    c = Client()
    c.login(username=parrain.user.username, password="x")
    response = c.get(URL)
    assert candidate_name not in response.content.decode("utf-8")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest cooptation/tests/test_parrain_dashboard.py::test_expired_requests_are_hidden -v`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add cooptation/tests/test_parrain_dashboard.py
git commit -m "test(p3.1): hide expired requests"
```

### 2h — Each row links to the correct token URL

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_parrain_dashboard.py`:

```python
@pytest.mark.django_db
def test_pending_row_links_to_per_token_vouch_page(make_cooptation_request):
    req = make_cooptation_request()
    parrain = req.parrain
    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )

    c = Client()
    c.login(username=parrain.user.username, password="x")
    response = c.get(URL)
    body = response.content.decode("utf-8")
    assert f'href="/cooptation/{req.token}/"' in body
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest cooptation/tests/test_parrain_dashboard.py::test_pending_row_links_to_per_token_vouch_page -v`

Expected: PASS.

- [ ] **Step 3: Run the full test file to confirm nothing regressed**

Run: `pytest cooptation/tests/test_parrain_dashboard.py -v`

Expected: 9 PASS (including parametrized variants).

- [ ] **Step 4: Commit**

```bash
git add cooptation/tests/test_parrain_dashboard.py
git commit -m "test(p3.1): each row links to per-token vouch page"
```

---

## Task 3: Context processor for nav badge count

**Files:**
- Create: `cooptation/context_processors.py`
- Create: `cooptation/tests/test_pending_vouches_count.py`
- Modify: `alumni/settings/base.py`

- [ ] **Step 1: Write the first failing test**

Create `cooptation/tests/test_pending_vouches_count.py`:

```python
"""Context processor `pending_vouches_count` exposes the number of pending
cooptation requests for the current user, used by the nav badge."""

from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.utils import timezone

from cooptation.context_processors import pending_vouches_count


@pytest.mark.django_db
def test_returns_zero_for_anonymous_user():
    from django.contrib.auth.models import AnonymousUser

    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    assert pending_vouches_count(request) == {"pending_vouches_count": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest cooptation/tests/test_pending_vouches_count.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'cooptation.context_processors'`.

- [ ] **Step 3: Create the context processor**

Create `cooptation/context_processors.py`:

```python
"""Template context processors for the cooptation app."""

from __future__ import annotations

from django.utils import timezone

from .models import CooptationRequest


def pending_vouches_count(request) -> dict[str, int]:
    """Number of CooptationRequests awaiting the current user's response.

    Returns 0 for anonymous users and for authenticated users without a
    Member profile (e.g., admins). Used by the nav badge in base.html.

    Cost: one indexed query per authenticated request (parrain_id is the
    auto-indexed FK column). At our scale (low hundreds of members, low
    daily request volume) this is negligible. If profiling later flags
    this as a hot spot, memoize on the request object.
    """
    if not request.user.is_authenticated:
        return {"pending_vouches_count": 0}
    member = getattr(request.user, "member", None)
    if member is None:
        return {"pending_vouches_count": 0}
    count = CooptationRequest.objects.filter(
        parrain=member,
        response="pending",
        expires_at__gt=timezone.now(),
    ).count()
    return {"pending_vouches_count": count}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_returns_zero_for_anonymous_user -v`

Expected: PASS.

- [ ] **Step 5: Add the auth-user-without-member test**

Append to `cooptation/tests/test_pending_vouches_count.py`:

```python
@pytest.mark.django_db
def test_returns_zero_for_authenticated_user_without_member(make_user):
    user = make_user()
    request = RequestFactory().get("/")
    request.user = user
    assert pending_vouches_count(request) == {"pending_vouches_count": 0}
```

- [ ] **Step 6: Run test**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_returns_zero_for_authenticated_user_without_member -v`

Expected: PASS.

- [ ] **Step 7: Add the member-with-pending test**

Append to `cooptation/tests/test_pending_vouches_count.py`:

```python
@pytest.mark.django_db
def test_returns_correct_count_for_member_with_pending(make_cooptation_request):
    req1 = make_cooptation_request()
    parrain = req1.parrain
    # Second pending request for same parrain
    make_cooptation_request(parrain=parrain)
    # Already-answered: should NOT count
    answered = make_cooptation_request(parrain=parrain)
    answered.response = "accepted"
    answered.save()
    # Expired: should NOT count
    expired = make_cooptation_request(parrain=parrain)
    expired.expires_at = timezone.now() - timedelta(days=1)
    expired.save()

    request = RequestFactory().get("/")
    request.user = parrain.user
    assert pending_vouches_count(request) == {"pending_vouches_count": 2}
```

- [ ] **Step 8: Run test**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_returns_correct_count_for_member_with_pending -v`

Expected: PASS.

- [ ] **Step 9: Register the context processor in settings**

Edit `alumni/settings/base.py`. In the `TEMPLATES` config, add the new processor at the end of the `context_processors` list (around line 63):

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "members.context.member_preferences",
                "core.context_processors.site",
                "cooptation.context_processors.pending_vouches_count",
            ],
        },
    },
]
```

- [ ] **Step 10: Run the full file to confirm nothing regressed**

Run: `pytest cooptation/tests/test_pending_vouches_count.py -v`

Expected: 3 PASS.

- [ ] **Step 11: Commit**

```bash
git add cooptation/context_processors.py cooptation/tests/test_pending_vouches_count.py alumni/settings/base.py
git commit -m "feat(p3.1): pending_vouches_count context processor + register"
```

---

## Task 4: Nav link + badge in base.html

**Files:**
- Modify: `templates/base.html`
- Modify: `cooptation/tests/test_pending_vouches_count.py` (add nav badge integration tests)

### 4a — Add the desktop nav link (no badge yet)

- [ ] **Step 1: Add the failing integration test**

Append to `cooptation/tests/test_pending_vouches_count.py`:

```python
from django.contrib.auth import get_user_model
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.mark.django_db
def test_nav_includes_dashboard_link_for_authenticated_member(make_member, make_user):
    user = make_user(password="x")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get("/")
    body = response.content.decode("utf-8")
    assert "/cooptations-a-valider/" in body
    assert "Cooptations" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_nav_includes_dashboard_link_for_authenticated_member -v`

Expected: FAIL — `/cooptations-a-valider/` is in URL conf but not in any nav.

- [ ] **Step 3: Add the desktop nav link in templates/base.html**

Edit `templates/base.html`. Locate the desktop auth nav block (around lines 49-55):

```html
{% if request.user.is_authenticated %}
    <nav class="hidden md:flex items-center gap-1 text-sm"
         aria-label="{% trans 'Navigation principale' %}">
        <a href="/annuaire/"
           class="rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">{% trans "Annuaire" %}</a>
        <a href="/profil/"
           class="rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">{% trans "Mon profil" %}</a>
    </nav>
{% endif %}
```

Replace with:

```html
{% if request.user.is_authenticated %}
    <nav class="hidden md:flex items-center gap-1 text-sm"
         aria-label="{% trans 'Navigation principale' %}">
        <a href="/annuaire/"
           class="rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">{% trans "Annuaire" %}</a>
        <a href="/cooptations-a-valider/"
           class="inline-flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">
            {% trans "Cooptations à valider" %}
            {% if pending_vouches_count %}
                <span class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-tertiary px-1.5 text-xs font-semibold text-on-tertiary"
                      aria-label="{% blocktrans count counter=pending_vouches_count %}{{ counter }} en attente{% plural %}{{ counter }} en attente{% endblocktrans %}">
                    {{ pending_vouches_count }}
                </span>
            {% endif %}
        </a>
        <a href="/profil/"
           class="rounded-lg px-3 py-2 hover:bg-base-200 hover:text-tertiary transition">{% trans "Mon profil" %}</a>
    </nav>
{% endif %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_nav_includes_dashboard_link_for_authenticated_member -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/base.html cooptation/tests/test_pending_vouches_count.py
git commit -m "feat(p3.1): add desktop nav link to parrain dashboard"
```

### 4b — Badge appears when count > 0

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_pending_vouches_count.py`:

```python
@pytest.mark.django_db
def test_nav_badge_renders_when_pending_count_positive(make_cooptation_request):
    req = make_cooptation_request()
    parrain = req.parrain
    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=parrain.user.username, password="x")
    response = c.get("/")
    body = response.content.decode("utf-8")
    # The numeric badge bubble — search for the count followed by closing </span>
    # right after the bg-tertiary rounded-full pill class.
    assert "rounded-full bg-tertiary" in body
    # The aria-label tells screen readers what the badge means.
    assert "1 en attente" in body
```

- [ ] **Step 2: Run test**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_nav_badge_renders_when_pending_count_positive -v`

Expected: PASS — badge HTML was added in step 4a/3, this test just confirms it.

- [ ] **Step 3: Add the negative test (badge absent when count == 0)**

Append to `cooptation/tests/test_pending_vouches_count.py`:

```python
@pytest.mark.django_db
def test_nav_badge_absent_when_pending_count_zero(make_member, make_user):
    user = make_user(password="x")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get("/")
    body = response.content.decode("utf-8")
    # Link is present but the count badge bubble is not.
    assert "/cooptations-a-valider/" in body
    assert "rounded-full bg-tertiary" not in body or "en attente" not in body
```

- [ ] **Step 4: Run test**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_nav_badge_absent_when_pending_count_zero -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cooptation/tests/test_pending_vouches_count.py
git commit -m "test(p3.1): badge appears on positive count, absent on zero"
```

### 4c — Add link to mobile nav

- [ ] **Step 1: Add the failing test**

Append to `cooptation/tests/test_pending_vouches_count.py`:

```python
@pytest.mark.django_db
def test_mobile_nav_includes_dashboard_link(make_member, make_user):
    """The mobile nav (md:hidden block) should also include the dashboard
    link so phone users have parity with desktop."""
    user = make_user(password="x")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get("/")
    body = response.content.decode("utf-8")
    # The mobile nav block has the md:hidden class and contains its own links.
    # Count "/cooptations-a-valider/" — must appear at least twice (desktop + mobile).
    assert body.count("/cooptations-a-valider/") >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_mobile_nav_includes_dashboard_link -v`

Expected: FAIL — currently only desktop nav has the link.

- [ ] **Step 3: Add the link to the mobile nav in templates/base.html**

Edit `templates/base.html`. Locate the mobile auth nav block (around lines 86-97):

```html
{% if request.user.is_authenticated %}
    <nav class="md:hidden border-t border-secondary/10 bg-surface/95"
         aria-label="{% trans 'Navigation mobile' %}">
        <div class="container mx-auto flex justify-around px-2 py-1.5 text-sm">
            <a href="/annuaire/" class="rounded-lg px-3 py-2 hover:text-tertiary">{% trans "Annuaire" %}</a>
            <a href="/profil/" class="rounded-lg px-3 py-2 hover:text-tertiary">{% trans "Mon profil" %}</a>
            <form method="post" action="{% url 'account_logout' %}" class="inline">
                {% csrf_token %}
                <button type="submit" class="rounded-lg px-3 py-2 hover:text-tertiary">{% trans "Quitter" %}</button>
            </form>
        </div>
    </nav>
{% endif %}
```

Replace with:

```html
{% if request.user.is_authenticated %}
    <nav class="md:hidden border-t border-secondary/10 bg-surface/95"
         aria-label="{% trans 'Navigation mobile' %}">
        <div class="container mx-auto flex justify-around px-2 py-1.5 text-sm">
            <a href="/annuaire/" class="rounded-lg px-3 py-2 hover:text-tertiary">{% trans "Annuaire" %}</a>
            <a href="/cooptations-a-valider/" class="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 hover:text-tertiary">
                {% trans "À valider" %}
                {% if pending_vouches_count %}
                    <span class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-tertiary px-1.5 text-xs font-semibold text-on-tertiary">
                        {{ pending_vouches_count }}
                    </span>
                {% endif %}
            </a>
            <a href="/profil/" class="rounded-lg px-3 py-2 hover:text-tertiary">{% trans "Mon profil" %}</a>
            <form method="post" action="{% url 'account_logout' %}" class="inline">
                {% csrf_token %}
                <button type="submit" class="rounded-lg px-3 py-2 hover:text-tertiary">{% trans "Quitter" %}</button>
            </form>
        </div>
    </nav>
{% endif %}
```

(Mobile uses the shorter label **"À valider"** to fit the constrained width; desktop keeps the full **"Cooptations à valider"**.)

- [ ] **Step 4: Run test**

Run: `pytest cooptation/tests/test_pending_vouches_count.py::test_mobile_nav_includes_dashboard_link -v`

Expected: PASS.

- [ ] **Step 5: Run the full test file to confirm nothing regressed**

Run: `pytest cooptation/tests/test_pending_vouches_count.py -v`

Expected: 7 PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/base.html cooptation/tests/test_pending_vouches_count.py
git commit -m "feat(p3.1): add mobile nav link to parrain dashboard"
```

---

## Task 5: STATUS update

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Add P3.1 row to the Phase Index table**

Edit `docs/superpowers/STATUS.md`. Locate the Phase Index table row for P4c (around line 17). Insert a new P3.1 row immediately after the P4c row and before the P5 row:

```markdown
| P3.1 | Parrain UX Polish (pending-vouches dashboard + 90-day session) | Complete (2026-05-03) | [plan](plans/2026-05-03-parrain-ux-polish.md) |
```

The Phase Index table should now read:

```markdown
| P4c | Public surface — quarterly review automation + admin status filter | Complete (tag `v0.4.0c-public-surface-admin`, 2026-05-03) | [plan](plans/2026-05-03-public-surface-admin.md) |
| P3.1 | Parrain UX Polish (pending-vouches dashboard + 90-day session) | Complete (2026-05-03) | [plan](plans/2026-05-03-parrain-ux-polish.md) |
| P5 | Mémoire seed | Not started | — |
```

- [ ] **Step 2: Add the P3.1 phase section**

Append the following section to `docs/superpowers/STATUS.md`. Place it after the existing P4c section and before any other content (or at end of file if P4c is the last phase section):

```markdown
## P3.1 — Parrain UX Polish

**Shipped:** 2026-05-03
**Plan:** [plans/2026-05-03-parrain-ux-polish.md](plans/2026-05-03-parrain-ux-polish.md)
**Spec:** [specs/2026-05-03-parrain-ux-polish-design.md](specs/2026-05-03-parrain-ux-polish-design.md)
**Test suite:** all passing (337 prior + ~18 new in `cooptation/tests/test_parrain_dashboard.py`, `cooptation/tests/test_pending_vouches_count.py`, `alumni/tests/test_session_settings.py`)

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | 90-day sliding session lifetime | [x] | _filled by implementer_ |
| 2 | Pending-vouches dashboard view + URL + template | [x] | _filled by implementer_ |
| 3 | `pending_vouches_count` context processor | [x] | _filled by implementer_ |
| 4 | Nav link + badge in `base.html` (desktop + mobile) | [x] | _filled by implementer_ |
| 5 | STATUS.md update | [x] | _filled by implementer_ |

---
```

The implementer should fill the commit SHAs from `git log --oneline | head -10` after the prior commits land.

- [ ] **Step 3: Fill in the commit SHAs**

Run: `git log --oneline | head -15`

Expected output: a list of P3.1-related commits in reverse chronological order. Map each Task # to its terminal commit SHA (the one whose message starts with `feat(p3.1):` or `test(p3.1):` and matches the task's outcome). Replace each `_filled by implementer_` placeholder with the appropriate short SHA.

- [ ] **Step 4: Run the full test suite to confirm green**

Run: `pytest --tb=short`

Expected: ALL PASS. Test count should land near 355 (337 prior + ~18 new from P3.1).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(p3.1): mark Parrain UX Polish complete in STATUS"
```

---

## Final verification checklist

After Task 5 commits:

- [ ] `pytest` exits clean.
- [ ] `git log --oneline | head -20` shows all P3.1 commits in order.
- [ ] Manual smoke (optional, against local runserver):
  1. Log in as a member who has at least one pending CooptationRequest.
  2. Confirm the "Cooptations à valider" link appears in the desktop nav with a count badge.
  3. Click → land on `/cooptations-a-valider/` showing the pending list.
  4. Click "Répondre" → land on the existing per-token vouch page.
  5. Submit a vouch → confirm the dashboard now shows one fewer entry (or the empty state if it was the only one).
  6. In a mobile viewport, confirm "À valider" appears in the bottom nav with the same badge behavior.

---

## What this plan does NOT do (per spec §Non-goals)

- No new email about the dashboard. The existing `parrain_invitation` email keeps its per-token CTA unchanged.
- No "recently answered" history section.
- No notification preferences for the dashboard.
- No pagination.
- No analogous admin-side helper for ghost-list signoffs.

If any of those become desired later, they're separate phases.
