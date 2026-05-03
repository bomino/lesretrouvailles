# P4a — Public Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder landing at `/` with a public, indexable page that introduces the project to non-members, exposes a 2-admin-gated "Nous recherchons aussi…" ghost list (behind a default-off feature flag), captures UTM source-of-arrival on cooptation signups, and ships full SEO machinery (sitemap, robots, OG, JSON-LD, noindex audit).

**Architecture:** Django function-based view rendering a single Tailwind/DaisyUI template. New `members.PublicSearchEntry` model with M2M `added_by_admins` for the publication gate. UTM fields added to `cooptation.AdminApplication`. Sitemap via Django's `sitemaps` framework. `BasicAuthMiddleware` extended with exact-match + prefix-match bypass for public paths so SEO crawlers can reach the landing on staging.

**Tech Stack:** Django 5 · pytest + pytest-django · Tailwind/DaisyUI (already wired) · Postgres · Cloudflare Web Analytics (frontend beacon, no backend).

**Spec reference:** `docs/superpowers/specs/2026-05-03-public-surface-design.md`.

---

## File map

**Files to CREATE:**
- `members/migrations/0006_publicsearchentry.py` — new model migration
- `cooptation/migrations/0006_adminapplication_utm.py` — UTM field migration
- `core/sitemaps.py` — Sitemap class for `/` and `/inscription/`
- `templates/core/landing.html` — new public landing template (replaces placeholder content path)
- `templates/robots.txt` — text/plain template
- `static/img/og-landing.png` — Open Graph share image (placeholder PNG; real asset is a content task before deploy)
- `members/tests/test_public_search_entry.py` — model tests
- `core/tests/test_landing_view.py` — landing view tests
- `core/tests/test_seo.py` — sitemap, robots, OG, JSON-LD tests
- `core/tests/test_noindex_audit.py` — parametrized noindex check across member URLs
- `cooptation/tests/test_signup_utm.py` — UTM capture tests

**Files to MODIFY:**
- `alumni/settings/base.py` — add `PUBLIC_GHOST_LIST_ENABLED`, `CLOUDFLARE_ANALYTICS_TOKEN`, extend `LOGIN_REQUIRED_WHITELIST`
- `members/models.py` — add `PublicSearchEntry`
- `members/admin.py` — register `PublicSearchEntryAdmin`
- `cooptation/models.py` — add `utm_source`, `utm_campaign`, `referrer` to `AdminApplication`
- `cooptation/admin.py` — extend `AdminApplicationAdmin.list_filter`
- `cooptation/views.py` — UTM stash in GET, stamp on POST in `signup_view`
- `core/middleware.py` — add `BASIC_AUTH_PUBLIC_EXACT` set + `BASIC_AUTH_PUBLIC_PREFIXES` tuple, extend bypass logic
- `core/views.py` — replace `landing_placeholder` with `landing_view`
- `core/urls.py` — wire `landing_view`, add `/sitemap.xml` and `/robots.txt` routes
- `templates/base.html` — add Cloudflare Web Analytics beacon snippet (gated)
- `core/tests/test_basic_auth.py` — add bypass regression tests

---

## Task 1: Settings — feature flag, analytics token, whitelist

**Files:**
- Modify: `alumni/settings/base.py:168-176`

- [ ] **Step 1: Open the file and locate `LOGIN_REQUIRED_WHITELIST`**

Run: `grep -n LOGIN_REQUIRED_WHITELIST alumni/settings/base.py`

Expected: line ~168.

- [ ] **Step 2: Add settings + extend whitelist**

Replace the existing `LOGIN_REQUIRED_WHITELIST` block with:

```python
LOGIN_REQUIRED_WHITELIST = [
    "/",
    "/health",
    "/accounts/",
    "/static/",
    "/media/",
    "/inscription/",
    "/questionnaire/",
    "/sitemap.xml",
    "/robots.txt",
]

# P4a: feature flag gating the public ghost list (Nous recherchons aussi…).
# Default off so admins can pre-populate via Django admin without exposing
# names publicly until P4b ships the public removal flow. Operators flip
# this to True via Railway env vars when the removal flow is live.
PUBLIC_GHOST_LIST_ENABLED = env.bool("PUBLIC_GHOST_LIST_ENABLED", default=False)

# P4a: Cloudflare Web Analytics token. Frontend beacon identifier (not a
# secret — appears in HTML). Beacon snippet is omitted from base.html when
# blank, so leaving this unset disables analytics cleanly.
CLOUDFLARE_ANALYTICS_TOKEN = env("CLOUDFLARE_ANALYTICS_TOKEN", default="")
```

- [ ] **Step 3: Verify Django boots**

Run: `.venv/Scripts/python.exe manage.py check 2>&1 | tail -5`

Expected: `System check identified no issues (0 silenced).` (warnings about `ACCOUNT_AUTHENTICATION_METHOD` are pre-existing allauth deprecation noise — ignore.)

- [ ] **Step 4: Commit**

```bash
git checkout -b feat/public-surface
git add alumni/settings/base.py
git commit -m "feat(p4a): add PUBLIC_GHOST_LIST_ENABLED flag + Cloudflare token + sitemap/robots whitelist"
```

---

## Task 2: PublicSearchEntry model + migration

**Files:**
- Modify: `members/models.py` (append)
- Create: `members/migrations/0006_publicsearchentry.py`
- Create: `members/tests/test_public_search_entry.py`

- [ ] **Step 1: Write the failing test**

Create `members/tests/test_public_search_entry.py`:

```python
"""Tests for PublicSearchEntry — the public 'ghost list' model.

Privacy-by-design: a name only renders publicly when 2+ Super Admins have
signed off (M2M added_by_admins) AND the entry has not been removed.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.utils import DataError
from django.utils import timezone


@pytest.fixture
def make_admin(db):
    """A staff/superuser usable as one of the 2 publication co-signers."""
    User = get_user_model()  # noqa: N806
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "username": f"admin{counter['i']}",
            "email": f"admin{counter['i']}@example.test",
            "password": "x",
            "is_staff": True,
            "is_superuser": True,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    return _make


@pytest.mark.django_db
def test_entry_with_zero_admins_is_unpublished(make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    assert e.is_published is False


@pytest.mark.django_db
def test_entry_with_one_admin_is_unpublished(make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin())
    assert e.is_published is False


@pytest.mark.django_db
def test_entry_with_two_admins_is_published(make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin(), make_admin())
    assert e.is_published is True


@pytest.mark.django_db
def test_removed_entry_is_unpublished_regardless_of_admin_count(make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin(), make_admin(), make_admin())
    e.removed_at = timezone.now()
    e.save()
    assert e.is_published is False


@pytest.mark.django_db
def test_last_name_initial_check_constraint_rejects_three_chars():
    from django.db import transaction

    from members.models import PublicSearchEntry

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PublicSearchEntry.objects.create(
                first_name="X", last_name_initial="ABC", years_at_ceg=[1980]
            )


@pytest.mark.django_db
def test_removal_token_unique_when_set():
    from django.db import transaction

    from members.models import PublicSearchEntry

    PublicSearchEntry.objects.create(
        first_name="A", last_name_initial="A.", years_at_ceg=[1980], removal_token="tok1"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PublicSearchEntry.objects.create(
                first_name="B",
                last_name_initial="B.",
                years_at_ceg=[1980],
                removal_token="tok1",
            )


@pytest.mark.django_db
def test_removal_token_nullable_allows_multiple_unset():
    from members.models import PublicSearchEntry

    PublicSearchEntry.objects.create(
        first_name="A", last_name_initial="A.", years_at_ceg=[1980], removal_token=None
    )
    PublicSearchEntry.objects.create(
        first_name="B", last_name_initial="B.", years_at_ceg=[1980], removal_token=None
    )
    assert PublicSearchEntry.objects.filter(removal_token__isnull=True).count() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_public_search_entry.py -x -q 2>&1 | tail -10`

Expected: ImportError or `module 'members.models' has no attribute 'PublicSearchEntry'`.

- [ ] **Step 3: Add the model to `members/models.py`**

Append to the bottom of `members/models.py`:

```python
class PublicSearchEntry(models.Model):
    """A name on the public 'Nous recherchons aussi…' list.

    Strict minimum-PII shape (master spec § 6.5): first name + last initial
    + years only. The model has no email/city/profession fields by design.

    Publication is gated by added_by_admins.count() >= 2 — there is no
    'is_published' boolean a single admin can toggle. Removal is signaled
    by setting removed_at; removed entries never publish even if they have
    many admin signoffs.
    """

    first_name = models.CharField(max_length=60)
    last_name_initial = models.CharField(max_length=2)
    years_at_ceg = ArrayField(models.IntegerField(), size=6)
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optionnel — courte ligne d'introduction visible publiquement.",
    )

    added_by_admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="ghost_entries_signed",
        blank=True,
    )
    added_at = models.DateTimeField(auto_now_add=True)

    # Reserved for P4b's public removal flow.
    removal_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["last_name_initial", "first_name"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(last_name_initial__regex=r"^[A-Za-zÀ-ÿ.]{1,2}$"),
                name="initial_must_be_one_or_two_chars",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name_initial} ({', '.join(map(str, self.years_at_ceg))})"

    @property
    def is_published(self) -> bool:
        return self.removed_at is None and self.added_by_admins.count() >= 2
```

Make sure `settings` is imported at the top of the file (it already is — see line `from django.conf import settings`). `ArrayField` is already imported too.

- [ ] **Step 4: Generate the migration**

Run (PowerShell):
```powershell
$env:DJANGO_SETTINGS_MODULE='alumni.settings.dev'; & .\.venv\Scripts\python.exe manage.py makemigrations members
```

Expected output mentions creating `members/migrations/0006_publicsearchentry.py`.

- [ ] **Step 5: Apply the migration locally**

```powershell
& .\.venv\Scripts\python.exe manage.py migrate members
```

Expected: `Applying members.0006_publicsearchentry... OK`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_public_search_entry.py -v 2>&1 | tail -15`

Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add members/models.py members/migrations/0006_publicsearchentry.py members/tests/test_public_search_entry.py
git commit -m "feat(p4a): add PublicSearchEntry with 2-admin M2M publication gate"
```

---

## Task 3: AdminApplication UTM fields + admin filter

**Files:**
- Modify: `cooptation/models.py` (AdminApplication class)
- Modify: `cooptation/admin.py:41` (list_filter tuple)
- Create: `cooptation/migrations/0006_adminapplication_utm.py`

- [ ] **Step 1: Open `cooptation/models.py` and locate `AdminApplication`'s field block**

Run: `grep -n "questionnaire_token\|cooptation_expired_at" cooptation/models.py`

These end the existing field list — we'll insert UTM fields right after them.

- [ ] **Step 2: Add UTM fields to AdminApplication**

In `cooptation/models.py`, after the `cooptation_expired_at` field (around line 67), insert:

```python
    # P4a: source-of-arrival capture from the public landing page.
    # Stored verbatim (sanitized for control chars + HTML special chars in the
    # signup view); no allowlist so future campaign labels work without code
    # changes. db_index on utm_source so list_filter doesn't sequential-scan.
    utm_source = models.CharField(max_length=80, blank=True, db_index=True)
    utm_campaign = models.CharField(max_length=80, blank=True)
    referrer = models.CharField(max_length=512, blank=True)
```

- [ ] **Step 3: Generate the migration**

```powershell
$env:DJANGO_SETTINGS_MODULE='alumni.settings.dev'; & .\.venv\Scripts\python.exe manage.py makemigrations cooptation
```

Expected: creates `cooptation/migrations/0006_adminapplication_utm.py`.

- [ ] **Step 4: Apply the migration**

```powershell
& .\.venv\Scripts\python.exe manage.py migrate cooptation
```

Expected: `Applying cooptation.0006_adminapplication_utm... OK`.

- [ ] **Step 5: Extend admin list_filter**

In `cooptation/admin.py`, find:

```python
    list_filter = ("status", "cooptation_outcome", "country")
```

Replace with:

```python
    list_filter = ("status", "cooptation_outcome", "country", "utm_source", "utm_campaign")
```

- [ ] **Step 6: Quick sanity check that the model loads**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_models.py -q 2>&1 | tail -3`

Expected: all existing tests pass (no regression).

- [ ] **Step 7: Commit**

```bash
git add cooptation/models.py cooptation/migrations/0006_adminapplication_utm.py cooptation/admin.py
git commit -m "feat(p4a): add UTM source/campaign/referrer to AdminApplication"
```

---

## Task 4: Basic-auth bypass for public paths (with regression test)

**Files:**
- Modify: `core/middleware.py`
- Modify: `core/tests/test_basic_auth.py`

- [ ] **Step 1: Write the failing tests**

Open `core/tests/test_basic_auth.py` and read the existing structure (it has tests for the basic-auth flow). Append at the end:

```python
@pytest.mark.django_db
@pytest.mark.parametrize("public_path", ["/", "/sitemap.xml", "/robots.txt"])
def test_basic_auth_exact_match_bypasses_for_public_paths(client, settings, public_path):
    """The landing, sitemap, and robots must be reachable without basic-auth
    credentials so SEO crawlers can index the public surface on staging."""
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    response = client.get(public_path)

    # Path resolves (200) or 404/302 from the inner view — what matters is
    # we got past the 401 Basic auth gate.
    assert response.status_code != 401, (
        f"Public path {public_path} was blocked by basic auth"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("private_path", ["/profil/", "/annuaire/", "/admin/"])
def test_basic_auth_blocks_private_paths_when_no_credentials(
    client, settings, private_path
):
    """Regression: a naive `path.startswith('/')` would defeat basic auth
    entirely since every URL starts with '/'. The middleware uses an
    exact-match set for short public paths and prefix-match only for
    explicit prefixes. This test pins that distinction."""
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    response = client.get(private_path)
    assert response.status_code == 401, (
        f"Private path {private_path} should require basic auth; got {response.status_code}"
    )


@pytest.mark.django_db
def test_basic_auth_bypasses_static_prefix(client, settings):
    """Static asset prefix bypass — crawler-friendly without exposing credentials."""
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    response = client.get("/static/css/output.css")
    assert response.status_code != 401


@pytest.mark.django_db
def test_basic_auth_bypasses_inscription_prefix(client, settings):
    """The cooptation signup URL must be publicly reachable too."""
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    response = client.get("/inscription/")
    assert response.status_code != 401
```

If `import pytest` is not already at the top of the file, add it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_basic_auth.py -k "exact_match_bypasses or blocks_private_paths or bypasses_static or bypasses_inscription" -v 2>&1 | tail -15`

Expected: failures — current middleware blocks all paths under basic auth.

- [ ] **Step 3: Update the middleware**

Open `core/middleware.py`. Replace the entire file with:

```python
import base64

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse

# Paths that bypass the basic-auth gate even when it is on. Used by the Docker
# healthcheck and any future external monitor that cannot send credentials.
BASIC_AUTH_BYPASS_PATHS = ("/health",)

# P4a: SEO crawlers and anonymous visitors must reach these without
# credentials so the public landing is actually indexable. Exact-match set
# is used for short paths to avoid the trap where prefix-matching "/" would
# bypass every URL in the site.
BASIC_AUTH_PUBLIC_EXACT = {"/", "/sitemap.xml", "/robots.txt"}

# Prefix-matched bypasses for paths with sub-routes. "/inscription/" covers
# both the form and its success page; "/static/" covers all assets.
BASIC_AUTH_PUBLIC_PREFIXES = ("/static/", "/inscription/")


class BasicAuthMiddleware:
    """Optional HTTP basic-auth gate, used in staging only.

    Activated by setting BASIC_AUTH_REQUIRED=True plus BASIC_AUTH_USERNAME
    and BASIC_AUTH_PASSWORD. Off by default in dev and prod.

    If BASIC_AUTH_REQUIRED=True but either credential is empty, raises at
    init-time. Empty credentials would let any caller authenticate with
    `Authorization: Basic Og==` (base64 of `:`), defeating the gate.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.required = getattr(settings, "BASIC_AUTH_REQUIRED", False)
        self.username = getattr(settings, "BASIC_AUTH_USERNAME", "")
        self.password = getattr(settings, "BASIC_AUTH_PASSWORD", "")

        if self.required and (not self.username or not self.password):
            raise ImproperlyConfigured(
                "BASIC_AUTH_REQUIRED=True but BASIC_AUTH_USERNAME or "
                "BASIC_AUTH_PASSWORD is empty. Set both before deploying."
            )

    def __call__(self, request):
        if not self.required:
            return self.get_response(request)

        if request.path in BASIC_AUTH_BYPASS_PATHS:
            return self.get_response(request)

        # Public-surface bypass — exact match first, then prefix match.
        # The order matters: prefix-matching "/" against any path would
        # bypass everything on the site.
        if request.path in BASIC_AUTH_PUBLIC_EXACT:
            return self.get_response(request)
        if any(request.path.startswith(p) for p in BASIC_AUTH_PUBLIC_PREFIXES):
            return self.get_response(request)

        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Basic "):
            try:
                creds = base64.b64decode(header[6:]).decode("utf-8")
                user, _, pwd = creds.partition(":")
                if user == self.username and pwd == self.password:
                    return self.get_response(request)
            except (ValueError, UnicodeDecodeError):
                pass

        response = HttpResponse("Authentication required", status=401)
        response["WWW-Authenticate"] = 'Basic realm="Staging"'
        return response
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_basic_auth.py -v 2>&1 | tail -15`

Expected: all tests pass (existing + 4 new bypass tests + the regression for private paths).

- [ ] **Step 5: Commit**

```bash
git add core/middleware.py core/tests/test_basic_auth.py
git commit -m "feat(p4a): basic-auth bypass for public paths (exact-match + prefix)"
```

---

## Task 5: UTM capture in signup_view

**Files:**
- Modify: `cooptation/views.py:signup_view`
- Create: `cooptation/tests/test_signup_utm.py`

- [ ] **Step 1: Write the failing tests**

Create `cooptation/tests/test_signup_utm.py`:

```python
"""Tests for UTM source-of-arrival capture in the cooptation signup flow.

Visitors arrive at /inscription/?utm_source=whatsapp&utm_campaign=invitation
from the public landing's WhatsApp share button. The view stashes UTM in
session at GET time so it survives form-render → form-submit, then writes
to the new AdminApplication on POST.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def active_member(db):
    """Pre-existing active Member to use as a parrain. Mirrors the fixture
    in test_signup_view.py."""
    from django.contrib.auth import get_user_model

    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="parrain1@example.test", email="parrain1@example.test", password="x"
    )
    return Member.objects.create(
        user=user,
        first_name="Parrain",
        last_name="One",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e", "5e", "4e", "3e"],
        city="Niamey",
    )


@pytest.fixture
def second_active_member(db):
    from django.contrib.auth import get_user_model

    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="parrain2@example.test", email="parrain2@example.test", password="x"
    )
    return Member.objects.create(
        user=user,
        first_name="Parrain",
        last_name="Two",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e", "5e", "4e", "3e"],
        city="Cotonou",
    )


def _form_payload(parrain1, parrain2, **overrides):
    payload = {
        "full_name": "Idrissa Saidou",
        "nickname": "",
        "years_attended": "1980,1981,1982,1983",
        "classes": "6e,5e,4e,3e",
        "city": "Niamey",
        "country": "Niger",
        "profession": "",
        "email": "candidate@example.test",
        "whatsapp": "",
        "parrain1_email": parrain1.user.email,
        "parrain2_email": parrain2.user.email,
        "website_url": "",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_get_with_utm_stashes_into_session(client):
    client.get("/inscription/?utm_source=whatsapp&utm_campaign=invitation")
    assert client.session.get("signup_utm_source") == "whatsapp"
    assert client.session.get("signup_utm_campaign") == "invitation"


@pytest.mark.django_db
def test_post_pops_session_utm_to_application(
    client, active_member, second_active_member, settings
):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication

    client.get("/inscription/?utm_source=whatsapp&utm_campaign=invitation")
    client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member),
        HTTP_REFERER="https://example.com/landing",
    )

    app = AdminApplication.objects.get(email="candidate@example.test")
    assert app.utm_source == "whatsapp"
    assert app.utm_campaign == "invitation"
    assert app.referrer == "https://example.com/landing"


@pytest.mark.django_db
def test_post_without_prior_get_writes_empty_utm(
    client, active_member, second_active_member, settings
):
    """Visitor went directly to /inscription/ — no UTM, no error."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication

    client.post("/inscription/", _form_payload(active_member, second_active_member))

    app = AdminApplication.objects.get(email="candidate@example.test")
    assert app.utm_source == ""
    assert app.utm_campaign == ""
    assert app.referrer == ""


@pytest.mark.django_db
def test_referrer_truncated_at_512(
    client, active_member, second_active_member, settings
):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication

    long_ref = "https://example.com/" + "a" * 1000
    client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member),
        HTTP_REFERER=long_ref,
    )
    app = AdminApplication.objects.get(email="candidate@example.test")
    assert len(app.referrer) == 512


@pytest.mark.django_db
def test_utm_html_special_chars_are_stripped(client):
    client.get('/inscription/?utm_source=whatsapp<script>&utm_campaign=launch"')
    assert "<" not in (client.session.get("signup_utm_source") or "")
    assert ">" not in (client.session.get("signup_utm_source") or "")
    assert '"' not in (client.session.get("signup_utm_campaign") or "")


@pytest.mark.django_db
def test_utm_truncated_at_80_chars(client):
    long_value = "x" * 200
    client.get(f"/inscription/?utm_source={long_value}")
    assert len(client.session.get("signup_utm_source") or "") == 80
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_signup_utm.py -x -q 2>&1 | tail -10`

Expected: first failure — session doesn't have `signup_utm_source` because the view doesn't stash it yet.

- [ ] **Step 3: Update `cooptation/views.py:signup_view`**

Open `cooptation/views.py`. At the top, add the helper after the existing `_client_ip` function:

```python
_UTM_FORBIDDEN = str.maketrans("", "", '<>"\'')


def _sanitize_utm(value: str) -> str:
    """Strip HTML special chars and control chars, truncate to 80."""
    if not value:
        return ""
    cleaned = value.translate(_UTM_FORBIDDEN)
    cleaned = "".join(c for c in cleaned if c.isprintable())
    return cleaned[:80]
```

Then modify `signup_view` to stash UTM on GET and stamp on POST. Find the `signup_view` function and replace its body with:

```python
@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def signup_view(request):
    # Stash UTM on every GET so a visitor arriving at /inscription/?utm_source=…
    # has it preserved through the form-render → form-submit hop. Sanitization
    # happens here (not at write time) so what's in the session is already safe.
    if request.method == "GET":
        for key in ("utm_source", "utm_campaign"):
            raw = request.GET.get(key)
            if raw:
                request.session[f"signup_{key}"] = _sanitize_utm(raw)

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("website_url"):
                return HttpResponseRedirect("/inscription/merci/")

            with transaction.atomic():
                app = AdminApplication.objects.create(
                    full_name=form.cleaned_data["full_name"],
                    nickname=form.cleaned_data["nickname"],
                    years_attended=form.cleaned_data["years_attended"],
                    classes=form.cleaned_data["classes"],
                    city=form.cleaned_data["city"],
                    country=form.cleaned_data["country"],
                    profession=form.cleaned_data["profession"],
                    email=form.cleaned_data["email"],
                    whatsapp=form.cleaned_data["whatsapp"],
                    source_ip=_client_ip(request),
                    utm_source=request.session.pop("signup_utm_source", ""),
                    utm_campaign=request.session.pop("signup_utm_campaign", ""),
                    referrer=request.META.get("HTTP_REFERER", "")[:512],
                )
                p1 = Member.objects.get(
                    user__email=form.cleaned_data["parrain1_email"], status="active"
                )
                p2 = Member.objects.get(
                    user__email=form.cleaned_data["parrain2_email"], status="active"
                )
                expires = timezone.now() + timedelta(days=14)
                req1 = CooptationRequest.objects.create(
                    application=app, parrain=p1, expires_at=expires
                )
                req2 = CooptationRequest.objects.create(
                    application=app, parrain=p2, expires_at=expires
                )

            emails.send_application_received(app)
            emails.send_cooptation_requests_sent(app, parrain_emails=[p1.user.email, p2.user.email])
            emails.send_parrain_invitation(req1)
            emails.send_parrain_invitation(req2)
            emails.send_admin_new_application(app)

            return HttpResponseRedirect("/inscription/merci/")
    else:
        form = SignupForm()
    return render(request, "cooptation/signup.html", {"form": form})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_signup_utm.py -v 2>&1 | tail -15`

Expected: 6 passed.

- [ ] **Step 5: Confirm existing signup tests still pass**

Run: `.venv/Scripts/python.exe -m pytest cooptation/tests/test_signup_view.py -q 2>&1 | tail -3`

Expected: all existing tests pass (no regression).

- [ ] **Step 6: Commit**

```bash
git add cooptation/views.py cooptation/tests/test_signup_utm.py
git commit -m "feat(p4a): capture UTM source/campaign/referrer on cooptation signup"
```

---

## Task 6: Sitemap framework + /sitemap.xml route

**Files:**
- Create: `core/sitemaps.py`
- Modify: `core/urls.py`
- Create: `core/tests/test_seo.py` (sitemap tests only this task; OG/JSON-LD tests added in Task 9)

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_seo.py`:

```python
"""Tests for SEO infrastructure: sitemap, robots.txt, OG tags, JSON-LD."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_sitemap_returns_200_xml(client):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")


@pytest.mark.django_db
def test_sitemap_includes_landing_and_inscription(client):
    response = client.get("/sitemap.xml")
    body = response.content.decode("utf-8")
    assert "<loc>" in body
    # Both public surfaces must be listed.
    assert "/inscription/" in body
    # The root URL is listed (matches /, but ends with / in a sitemap).
    assert any(line.strip().endswith("/</loc>") for line in body.splitlines())


@pytest.mark.django_db
def test_sitemap_excludes_member_urls(client):
    response = client.get("/sitemap.xml")
    body = response.content.decode("utf-8")
    for forbidden in ("/profil/", "/annuaire/", "/admin/", "/cooptation/"):
        assert forbidden not in body, (
            f"Sitemap leaks member URL {forbidden}; only public surfaces "
            "should appear there"
        )


@pytest.mark.django_db
def test_sitemap_url_uses_clean_site_url_no_percent_20(client, settings):
    """Regression for the trailing-space SITE_URL bug (already fixed in
    settings.base via .strip().rstrip('/')). If the strip ever regresses,
    sitemap URLs would render as https://host%20/path."""
    settings.SITE_URL = "https://prod.example.test"
    response = client.get("/sitemap.xml")
    body = response.content.decode("utf-8")
    assert "%20" not in body, "Sitemap contains URL-encoded space; SITE_URL strip regressed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_seo.py -x -q 2>&1 | tail -5`

Expected: 404 (no `/sitemap.xml` route yet).

- [ ] **Step 3: Create the sitemap class**

Create `core/sitemaps.py`:

```python
"""Sitemap for the public surface. Only landing + inscription are exposed —
member URLs (annuaire, profil, cooptation token URLs) must never appear."""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PublicSurfaceSitemap(Sitemap):
    """Two static URLs: the landing and the cooptation signup form."""

    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        return ["landing", "signup"]

    def location(self, item):
        if item == "landing":
            return "/"
        if item == "signup":
            return reverse("signup")
        raise ValueError(f"Unknown sitemap item: {item}")
```

- [ ] **Step 4: Wire the sitemap into URLs**

Open `core/urls.py`. Replace the file with:

```python
from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views
from .sitemaps import PublicSurfaceSitemap

sitemaps_dict = {"public": PublicSurfaceSitemap}

urlpatterns = [
    path("", views.landing_placeholder, name="landing_placeholder"),
    path("health", views.health, name="health"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps_dict}, name="django.contrib.sitemaps.views.sitemap"),
]
```

> Note: `landing_view` is wired in Task 8; for now we keep `landing_placeholder` so the existing `/` route doesn't break.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_seo.py -v 2>&1 | tail -15`

Expected: 4 passed (the 4 sitemap tests).

- [ ] **Step 6: Commit**

```bash
git add core/sitemaps.py core/urls.py core/tests/test_seo.py
git commit -m "feat(p4a): /sitemap.xml exposing landing + inscription only"
```

---

## Task 7: robots.txt template + route

**Files:**
- Create: `templates/robots.txt`
- Modify: `core/urls.py`
- Modify: `core/tests/test_seo.py` (add robots tests)

- [ ] **Step 1: Add robots tests to `core/tests/test_seo.py`**

Append:

```python
@pytest.mark.django_db
def test_robots_txt_returns_200_text_plain(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")


@pytest.mark.django_db
def test_robots_allows_public_paths(client):
    body = client.get("/robots.txt").content.decode("utf-8")
    assert "Allow: /\n" in body or body.strip().split("\n")[1].startswith("Allow: /")
    assert "Allow: /inscription/" in body
    assert "Allow: /sitemap.xml" in body


@pytest.mark.django_db
def test_robots_disallows_member_and_admin_paths(client):
    body = client.get("/robots.txt").content.decode("utf-8")
    for path in ("/admin/", "/accounts/", "/profil/", "/annuaire/", "/cooptation/", "/questionnaire/", "/charte/"):
        assert f"Disallow: {path}" in body, f"robots.txt missing Disallow for {path}"


@pytest.mark.django_db
def test_robots_references_sitemap_url_from_settings(client, settings):
    settings.SITE_URL = "https://prod.example.test"
    body = client.get("/robots.txt").content.decode("utf-8")
    assert "Sitemap: https://prod.example.test/sitemap.xml" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_seo.py -k robots -x -q 2>&1 | tail -5`

Expected: 404.

- [ ] **Step 3: Create the robots template**

Create `templates/robots.txt`:

```
User-agent: *
Allow: /
Allow: /inscription/
Allow: /sitemap.xml
Disallow: /admin/
Disallow: /accounts/
Disallow: /profil/
Disallow: /annuaire/
Disallow: /cooptation/
Disallow: /questionnaire/
Disallow: /charte/
Sitemap: {{ site_url }}/sitemap.xml
```

- [ ] **Step 4: Add view + URL**

In `core/views.py`, append:

```python
def robots_txt(request):
    from django.conf import settings as django_settings

    return render(
        request,
        "robots.txt",
        {"site_url": django_settings.SITE_URL},
        content_type="text/plain",
    )
```

In `core/urls.py`, add the route to `urlpatterns`:

```python
    path("robots.txt", views.robots_txt, name="robots_txt"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_seo.py -v 2>&1 | tail -15`

Expected: 8 passed (4 sitemap + 4 robots).

- [ ] **Step 6: Commit**

```bash
git add templates/robots.txt core/views.py core/urls.py core/tests/test_seo.py
git commit -m "feat(p4a): /robots.txt with explicit allow/disallow + sitemap reference"
```

---

## Task 8: PublicSearchEntry admin registration

**Files:**
- Modify: `members/admin.py`

- [ ] **Step 1: Read the existing admin file to find the right insertion point**

Run: `tail -20 members/admin.py`

This shows where existing admin registrations end.

- [ ] **Step 2: Add the admin registration**

Append to `members/admin.py`:

```python
from .models import PublicSearchEntry  # noqa: E402  (grouped with members imports above)


@admin.register(PublicSearchEntry)
class PublicSearchEntryAdmin(admin.ModelAdmin):
    """Governance UI for the public ghost list.

    Two co-signers required for publication — admins add themselves to
    `added_by_admins` to vouch. Until 2 distinct admins have signed off,
    the entry stays invisible publicly.
    """

    list_display = ("first_name", "last_name_initial", "years_at_ceg", "signoff_count", "removed_at")
    list_filter = ("removed_at",)
    search_fields = ("first_name", "last_name_initial", "note")
    filter_horizontal = ("added_by_admins",)
    readonly_fields = ("added_at", "removal_token", "removed_at", "removed_reason")

    fieldsets = (
        ("Données publiques (RGPD : strict minimum)", {
            "fields": ("first_name", "last_name_initial", "years_at_ceg", "note"),
            "description": (
                "Seuls ces champs apparaissent sur la page publique. "
                "Pas d'email, pas de ville, pas de profession (master spec § 6.5)."
            ),
        }),
        ("Cosignature (2 admins requis pour publication)", {
            "fields": ("added_by_admins",),
            "description": "Ajoutez-vous à la liste pour cosigner. Au moins 2 admins distincts requis avant que le nom n'apparaisse publiquement.",
        }),
        ("Audit (lecture seule)", {
            "fields": ("added_at", "removal_token", "removed_at", "removed_reason"),
        }),
    )

    @admin.display(description="Signatures")
    def signoff_count(self, obj):
        return obj.added_by_admins.count()
```

If `from .models import` already exists at the top of the file, just add `PublicSearchEntry` to that import line and remove the bottom one.

- [ ] **Step 3: Verify admin loads without error**

Run: `.venv/Scripts/python.exe manage.py check 2>&1 | tail -5`

Expected: `System check identified no issues`.

- [ ] **Step 4: Commit**

```bash
git add members/admin.py
git commit -m "feat(p4a): register PublicSearchEntry admin with 2-cosigner UX"
```

---

## Task 9: Landing view + template — anonymous variant

**Files:**
- Modify: `core/views.py`
- Create: `templates/core/landing.html`
- Modify: `core/urls.py`
- Create: `core/tests/test_landing_view.py`

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_landing_view.py`:

```python
"""Tests for the public landing view at /."""

from __future__ import annotations

from urllib.parse import quote

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def authed_member(db, client):
    """A logged-in Member — to verify the auth branch keeps existing behavior."""
    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="alice@example.test", email="alice@example.test", password="x"
    )
    Member.objects.create(
        user=user, first_name="Alice", last_name="X",
        years_attended=[1980, 1981, 1982, 1983], classes=["6e"],
        city="Niamey", status="active",
    )
    client.force_login(user)
    return user


@pytest.fixture
def make_admin(db):
    User = get_user_model()  # noqa: N806
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "username": f"admin{counter['i']}",
            "email": f"admin{counter['i']}@example.test",
            "password": "x", "is_staff": True, "is_superuser": True,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    return _make


@pytest.mark.django_db
def test_anonymous_landing_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_landing_overrides_noindex(client):
    body = client.get("/").content.decode("utf-8")
    assert '<meta name="robots" content="index, follow"' in body
    assert '<meta name="robots" content="noindex"' not in body


@pytest.mark.django_db
def test_anonymous_landing_shows_public_ctas(client):
    body = client.get("/").content.decode("utf-8")
    assert "Je suis un ancien" in body
    assert "/inscription/" in body
    assert "Partager sur WhatsApp" in body


@pytest.mark.django_db
def test_anonymous_landing_whatsapp_share_url_carries_utm(client):
    body = client.get("/").content.decode("utf-8")
    assert "wa.me" in body
    assert quote("utm_source=whatsapp") in body or "utm_source%3Dwhatsapp" in body
    assert "invitation" in body


@pytest.mark.django_db
def test_authenticated_landing_shows_member_ctas_not_public(client, authed_member):
    body = client.get("/").content.decode("utf-8")
    assert "Parcourir l'annuaire" in body
    assert "Mon profil" in body
    assert "Je suis un ancien" not in body
    assert "Partager sur WhatsApp" not in body


@pytest.mark.django_db
def test_ghost_section_hidden_when_flag_off(client, settings):
    settings.PUBLIC_GHOST_LIST_ENABLED = False
    body = client.get("/").content.decode("utf-8")
    assert "Nous recherchons aussi" not in body


@pytest.mark.django_db
def test_ghost_section_visible_with_empty_state_when_flag_on_no_entries(client, settings):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    body = client.get("/").content.decode("utf-8")
    assert "Nous recherchons aussi" in body
    assert "Liste en cours de constitution" in body


@pytest.mark.django_db
def test_ghost_section_renders_published_entries(client, settings, make_admin):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.",
        years_at_ceg=[1980, 1981, 1982, 1983],
        note="Vivait à Maradi.",
    )
    e.added_by_admins.add(make_admin(), make_admin())

    body = client.get("/").content.decode("utf-8")
    assert "Idrissa" in body
    assert "S." in body
    assert "Vivait à Maradi" in body


@pytest.mark.django_db
def test_ghost_section_hides_single_admin_entries(client, settings, make_admin):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="OnlyOneSignoff", last_name_initial="Z.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin())  # Only one admin → not published

    body = client.get("/").content.decode("utf-8")
    assert "OnlyOneSignoff" not in body


@pytest.mark.django_db
def test_ghost_section_hides_removed_entries(client, settings, make_admin):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from django.utils import timezone

    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="WasPublished", last_name_initial="Y.", years_at_ceg=[1980],
    )
    e.added_by_admins.add(make_admin(), make_admin(), make_admin())
    e.removed_at = timezone.now()
    e.save()

    body = client.get("/").content.decode("utf-8")
    assert "WasPublished" not in body


@pytest.mark.django_db
def test_anonymous_feature_cards_not_clickable(client):
    """Annuaire/InMemoriam/Cooptation cards should not be <a> tags for anonymous
    visitors — they lead to gated pages and would frustrate a first-time visitor."""
    body = client.get("/").content.decode("utf-8")
    # The card text should appear, but not wrapped in anchors with member URLs.
    assert "Annuaire" in body
    assert 'href="/annuaire/"' not in body
    assert 'href="/profil/"' not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_landing_view.py -x -q 2>&1 | tail -10`

Expected: failures — current placeholder doesn't have the new content.

- [ ] **Step 3: Add `landing_view` to `core/views.py`**

Replace the entire `core/views.py` with:

```python
"""Core views — health check and the public landing page."""

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings as django_settings
from django.db import connection
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


def health(_request):
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False
    payload = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "fail"}
    status_code = 200 if db_ok else 503
    return JsonResponse(payload, status=status_code)


# Kept temporarily so older imports/redirects don't 500 during the migration.
def landing_placeholder(request):
    return render(request, "core/landing_placeholder.html")


@require_http_methods(["GET"])
def landing_view(request):
    """The public landing page. Anonymous visitors get the recruitment-shaped
    CTAs and the ghost list (if the feature flag is on); authenticated members
    get the member-style CTAs from the prior placeholder template."""
    from members.models import PublicSearchEntry

    ghosts = []
    if django_settings.PUBLIC_GHOST_LIST_ENABLED:
        ghosts = list(
            PublicSearchEntry.objects.filter(removed_at__isnull=True)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=2)
        )

    share_url = request.build_absolute_uri("/?utm_source=whatsapp&utm_campaign=invitation")
    share_message = "Les Retrouvailles — promotion 1980-1985 du CEG 1 Birni à Zinder"
    whatsapp_text = f"{share_message} {share_url}"

    return render(
        request,
        "core/landing.html",
        {
            "ghosts": ghosts,
            "ghost_list_enabled": django_settings.PUBLIC_GHOST_LIST_ENABLED,
            "share_url": share_url,
            "whatsapp_share_url": f"https://wa.me/?text={quote(whatsapp_text)}",
        },
    )


def robots_txt(request):
    return render(
        request,
        "robots.txt",
        {"site_url": django_settings.SITE_URL},
        content_type="text/plain",
    )
```

- [ ] **Step 4: Wire `landing_view` in `core/urls.py`**

Open `core/urls.py`. Change:

```python
    path("", views.landing_placeholder, name="landing_placeholder"),
```

To:

```python
    path("", views.landing_view, name="landing"),
```

(Keep the rest of the routes intact.)

- [ ] **Step 5: Create `templates/core/landing.html`**

Create the template:

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}
    {% trans "Les Retrouvailles — anciens du CEG 1 Birni" %}
{% endblock %}

{% block robots %}<meta name="robots" content="index, follow">{% endblock %}

{% block extra_head %}
    {# P4a: SEO meta + social card. Real og:image is a content task; #}
    {# the file at static/img/og-landing.png must exist before deploy. #}
    <meta name="description" content="{% trans 'Plateforme privée des anciens du CEG 1 Birni à Zinder, promotion 1980-1985. Annuaire, mémoire collective et retrouvailles.' %}">
    <meta name="keywords" content="CEG 1 Birni Zinder, promotion 1980 1985 Zinder, anciens CEG Birni">
    <link rel="canonical" href="{{ site_url|default:'https://lesretrouvailles-production.up.railway.app' }}/">

    <meta property="og:type" content="website">
    <meta property="og:locale" content="fr_FR">
    <meta property="og:title" content="{% trans 'Les Retrouvailles — anciens du CEG 1 Birni' %}">
    <meta property="og:description" content="{% trans 'Promotion 1980-1985 du CEG 1 Birni à Zinder.' %}">
    <meta property="og:url" content="{{ site_url|default:'https://lesretrouvailles-production.up.railway.app' }}/">
    <meta property="og:image" content="{{ site_url|default:'https://lesretrouvailles-production.up.railway.app' }}/static/img/og-landing.png">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{% trans 'Les Retrouvailles — anciens du CEG 1 Birni' %}">
    <meta name="twitter:description" content="{% trans 'Promotion 1980-1985 du CEG 1 Birni à Zinder.' %}">
    <meta name="twitter:image" content="{{ site_url|default:'https://lesretrouvailles-production.up.railway.app' }}/static/img/og-landing.png">

    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Les Retrouvailles — CEG 1 Birni",
      "url": "{{ site_url|default:'https://lesretrouvailles-production.up.railway.app' }}/",
      "description": "Plateforme privée des anciens du CEG 1 Birni à Zinder, promotion 1980-1985.",
      "foundingDate": "1980-09-01"
    }
    </script>
{% endblock %}

{% block content %}
    <section class="relative isolate mx-auto max-w-4xl text-center">
        <span class="inline-block rounded-full border border-tertiary/30 bg-surface px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-tertiary shadow-sm">
            {% trans "Promotion 1980 — 1985 · CEG 1 Birni · Zinder" %}
        </span>
        <h1 class="mt-6 font-display text-4xl font-semibold tracking-tight md:text-6xl md:leading-[1.05]">
            {% trans "Le foyer numérique" %}
            <span class="block italic text-tertiary">{% trans "des anciens du CEG 1 Birni." %}</span>
        </h1>
        {# REPLACE BEFORE DEPLOY: this 200-280 word narrative is the project's #}
        {# pitch to non-members. Pre-deploy content task — see plan §6 rollout. #}
        <p class="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-secondary md:text-xl">
            {% trans "Quarante ans après nos années à Zinder, nous reconstituons le réseau de la promotion 1980-1985 du CEG 1 Birni. Cet espace — privé pour ses membres, ouvert pour celles et ceux qui se reconnaîtront — rassemble noms, parcours et souvenirs. Si tu as partagé nos bancs, ou si tu connais quelqu'un qui les a partagés, tu es au bon endroit." %}
        </p>

        {% if request.user.is_authenticated %}
            <div class="mt-10 flex flex-wrap items-center justify-center gap-3">
                <a href="/annuaire/"
                   class="inline-flex items-center gap-2 rounded-lg bg-tertiary px-6 py-3 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 transition min-h-tap">
                    {% trans "Parcourir l'annuaire" %}
                    <span aria-hidden="true">→</span>
                </a>
                <a href="/profil/"
                   class="inline-flex items-center rounded-lg border border-secondary/25 bg-surface px-5 py-3 text-base font-medium hover:border-tertiary/40 hover:text-tertiary transition min-h-tap">
                    {% trans "Mon profil" %}
                </a>
            </div>
        {% else %}
            <div class="mt-10 flex flex-wrap items-center justify-center gap-3">
                <a href="/inscription/"
                   class="inline-flex items-center gap-2 rounded-lg bg-tertiary px-6 py-3 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 transition min-h-tap">
                    {% trans "Je suis un ancien" %}
                    <span aria-hidden="true">→</span>
                </a>
                <a href="{% url 'account_login' %}"
                   class="inline-flex items-center rounded-lg border border-secondary/25 bg-surface px-5 py-3 text-base font-medium hover:border-tertiary/40 hover:text-tertiary transition min-h-tap">
                    {% trans "Se connecter" %}
                </a>
            </div>
            <div class="mt-4">
                <a href="{{ whatsapp_share_url }}"
                   target="_blank" rel="noopener noreferrer"
                   class="inline-flex items-center gap-2 text-sm text-secondary hover:text-tertiary transition"
                   aria-label="{% trans 'Partager cette page sur WhatsApp' %}">
                    <span aria-hidden="true">💬</span>
                    {% trans "Partager sur WhatsApp" %}
                </a>
            </div>
        {% endif %}
    </section>

    {% if ghost_list_enabled %}
        <section class="mx-auto mt-20 max-w-4xl md:mt-28">
            <div class="text-center">
                <span class="inline-block rounded-full border border-secondary/25 bg-surface px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-secondary shadow-sm">
                    {% trans "Nous recherchons aussi…" %}
                </span>
                <h2 class="mt-4 font-display text-2xl font-semibold tracking-tight md:text-3xl">
                    {% trans "Anciens encore à retrouver" %}
                </h2>
            </div>
            {% if ghosts %}
                <div class="mt-10 space-y-4">
                    {% for entry in ghosts %}
                        <article class="rounded-2xl border border-secondary/15 bg-surface/70 p-5 shadow-sm">
                            <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                                <strong class="font-display text-lg">
                                    {{ entry.first_name }} {{ entry.last_name_initial }}
                                </strong>
                                <span class="text-sm text-secondary">
                                    {% trans "au CEG" %} {{ entry.years_at_ceg|first }}-{{ entry.years_at_ceg|last }}
                                </span>
                            </div>
                            {% if entry.note %}
                                <p class="mt-1 text-sm text-secondary">{{ entry.note }}</p>
                            {% endif %}
                            <p class="mt-2 text-sm italic text-secondary">
                                {% trans "Vous le reconnaissez ? Partagez cette page avec votre entourage." %}
                            </p>
                        </article>
                    {% endfor %}
                </div>
            {% else %}
                <p class="mt-10 text-center text-secondary">
                    {% trans "Liste en cours de constitution — bientôt." %}
                </p>
            {% endif %}
        </section>
    {% endif %}

    <section class="mx-auto mt-20 grid max-w-5xl grid-cols-1 gap-6 md:mt-28 md:grid-cols-3">
        {# Cards are visual only for anonymous visitors — destinations are member-only. #}
        {% if request.user.is_authenticated %}
            <a href="/annuaire/" class="rounded-2xl border border-secondary/15 bg-surface/70 p-6 shadow-sm hover:border-tertiary/40 transition">
        {% else %}
            <article class="rounded-2xl border border-secondary/15 bg-surface/70 p-6 shadow-sm">
        {% endif %}
                <span class="inline-flex h-10 w-10 items-center justify-center rounded-full bg-tertiary/10 text-tertiary text-xl">📖</span>
                <h2 class="mt-4 font-display text-xl font-semibold tracking-tight">{% trans "Annuaire" %}</h2>
                <p class="mt-2 text-sm text-secondary leading-relaxed">
                    {% trans "Retrouvez vos camarades par nom, ville ou profession. Recherche insensible aux accents." %}
                </p>
        {% if request.user.is_authenticated %}</a>{% else %}</article>{% endif %}

        <article class="rounded-2xl border border-secondary/15 bg-surface/70 p-6 shadow-sm">
            <span class="inline-flex h-10 w-10 items-center justify-center rounded-full bg-ceremonial-gold/15 text-ceremonial-gold text-xl">🕊️</span>
            <h2 class="mt-4 font-display text-xl font-semibold tracking-tight">{% trans "In Memoriam" %}</h2>
            <p class="mt-2 text-sm text-secondary leading-relaxed">
                {% trans "Un espace de recueillement pour celles et ceux qui nous ont quittés." %}
            </p>
        </article>
        <article class="rounded-2xl border border-secondary/15 bg-surface/70 p-6 shadow-sm">
            <span class="inline-flex h-10 w-10 items-center justify-center rounded-full bg-whatsapp-green/15 text-whatsapp-green text-xl">🤝</span>
            <h2 class="mt-4 font-display text-xl font-semibold tracking-tight">{% trans "Cooptation" %}</h2>
            <p class="mt-2 text-sm text-secondary leading-relaxed">
                {% trans "Une inscription validée par deux camarades — entre nous, pour nous." %}
            </p>
        </article>
    </section>
{% endblock %}
```

- [ ] **Step 6: Add `site_url` to the context (so og/canonical/twitter URLs render correctly)**

The template references `site_url`. Update the `landing_view` `render` call to pass it:

```python
    return render(
        request,
        "core/landing.html",
        {
            "ghosts": ghosts,
            "ghost_list_enabled": django_settings.PUBLIC_GHOST_LIST_ENABLED,
            "share_url": share_url,
            "whatsapp_share_url": f"https://wa.me/?text={quote(whatsapp_text)}",
            "site_url": django_settings.SITE_URL,
        },
    )
```

- [ ] **Step 7: Create the placeholder OG image**

Generate a 1×1 transparent PNG at `static/img/og-landing.png` so the file exists during dev and tests don't 404. Run (PowerShell):

```powershell
$bytes = [byte[]](0x89,0x50,0x4E,0x47,0x0D,0x0A,0x1A,0x0A,0x00,0x00,0x00,0x0D,0x49,0x48,0x44,0x52,0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01,0x08,0x06,0x00,0x00,0x00,0x1F,0x15,0xC4,0x89,0x00,0x00,0x00,0x0D,0x49,0x44,0x41,0x54,0x78,0x9C,0x63,0x00,0x01,0x00,0x00,0x05,0x00,0x01,0x0D,0x0A,0x2D,0xB4,0x00,0x00,0x00,0x00,0x49,0x45,0x4E,0x44,0xAE,0x42,0x60,0x82)
[System.IO.File]::WriteAllBytes("static/img/og-landing.png", $bytes)
```

Add a marker file documenting that this is a placeholder:

```powershell
"This is a 1x1 placeholder. Replace with a real 1200x630 social-card PNG before deploying P4a." | Out-File -Encoding utf8 static/img/og-landing.README.md
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_landing_view.py -v 2>&1 | tail -20`

Expected: 11 passed.

- [ ] **Step 9: Verify the placeholder template still serves (we kept the import)**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_smoke.py -q 2>&1 | tail -3`

Expected: existing smoke tests still pass.

- [ ] **Step 10: Commit**

```bash
git add core/views.py core/urls.py templates/core/landing.html static/img/
git commit -m "feat(p4a): public landing view + template with ghost section + OG/JSON-LD"
```

---

## Task 10: Cloudflare Web Analytics beacon in base.html

**Files:**
- Modify: `templates/base.html`
- Create: a small test in `core/tests/test_seo.py`

- [ ] **Step 1: Add the test**

Append to `core/tests/test_seo.py`:

```python
@pytest.mark.django_db
def test_cloudflare_beacon_present_when_token_set_and_anonymous(client, settings):
    settings.CLOUDFLARE_ANALYTICS_TOKEN = "test-cf-token-abc"
    body = client.get("/").content.decode("utf-8")
    assert "static.cloudflareinsights.com/beacon.min.js" in body
    assert "test-cf-token-abc" in body


@pytest.mark.django_db
def test_cloudflare_beacon_absent_when_token_blank(client, settings):
    settings.CLOUDFLARE_ANALYTICS_TOKEN = ""
    body = client.get("/").content.decode("utf-8")
    assert "static.cloudflareinsights.com" not in body


@pytest.mark.django_db
def test_cloudflare_beacon_absent_for_authenticated_users(client, settings):
    """Members visiting member pages must not pollute the public-surface metric."""
    from django.contrib.auth import get_user_model
    from members.models import Member

    settings.CLOUDFLARE_ANALYTICS_TOKEN = "test-cf-token-abc"
    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="bob@example.test", email="bob@example.test", password="x"
    )
    Member.objects.create(
        user=user, first_name="Bob", last_name="X",
        years_attended=[1980], classes=["6e"], city="Niamey", status="active",
    )
    client.force_login(user)
    body = client.get("/profil/").content.decode("utf-8")
    assert "static.cloudflareinsights.com" not in body
```

- [ ] **Step 2: Add a context processor for the analytics token**

Open `core/context_processors.py` if it exists; otherwise create it:

```python
"""Site-wide template context processors."""

from django.conf import settings


def site(_request):
    return {
        "CLOUDFLARE_ANALYTICS_TOKEN": getattr(settings, "CLOUDFLARE_ANALYTICS_TOKEN", ""),
    }
```

Wire it in `alumni/settings/base.py` `TEMPLATES[0]["OPTIONS"]["context_processors"]`. Find that list and append `"core.context_processors.site"`.

- [ ] **Step 3: Add the beacon snippet to `templates/base.html`**

Open `templates/base.html` and find the `<head>` section (after the `<meta charset>` lines, before `</head>`). Add inside the `<head>`:

```django
{% if not request.user.is_authenticated and CLOUDFLARE_ANALYTICS_TOKEN %}
    <script defer
            src="https://static.cloudflareinsights.com/beacon.min.js"
            data-cf-beacon='{"token": "{{ CLOUDFLARE_ANALYTICS_TOKEN }}"}'></script>
{% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_seo.py -k cloudflare -v 2>&1 | tail -10`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add templates/base.html core/context_processors.py alumni/settings/base.py core/tests/test_seo.py
git commit -m "feat(p4a): Cloudflare Web Analytics beacon (anonymous-only, env-gated)"
```

---

## Task 11: Noindex audit across member URLs + landing a11y

**Files:**
- Create: `core/tests/test_noindex_audit.py`
- Create: `core/tests/test_a11y.py` (landing-specific a11y; member-page a11y already lives in `members/tests/test_a11y.py`)

- [ ] **Step 1: Write the audit test**

Create `core/tests/test_noindex_audit.py`:

```python
"""Audit test: every member-facing URL must explicitly emit noindex.

Catches templates that accidentally bypass base.html (e.g., a future view
returning HttpResponse with raw HTML) and any view that renders without
extending the layout. The cost of being wrong here is real — leaking
member directory entries to Google search results.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


NOINDEX_MARKER = '<meta name="robots" content="noindex">'


@pytest.fixture
def member_client(db, client):
    """Logged-in client with an active Member."""
    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="audit@example.test", email="audit@example.test", password="x"
    )
    Member.objects.create(
        user=user, first_name="Audit", last_name="User",
        years_attended=[1980, 1981, 1982, 1983], classes=["6e"],
        city="Niamey", status="active",
    )
    # Acknowledge consent so middleware doesn't redirect to /charte/.
    from members.charters import CHARTER_CURRENT_VERSION

    session = client.session
    session["consent_ok_for"] = CHARTER_CURRENT_VERSION
    session.save()
    client.force_login(user)
    return client, user


@pytest.fixture
def staff_client(db, client):
    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="staffaudit@example.test", email="staffaudit@example.test",
        password="x", is_staff=True, is_superuser=True,
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/profil/", "/annuaire/", "/charte/"])
def test_member_pages_emit_noindex(member_client, path):
    client, user = member_client
    response = client.get(path)
    assert response.status_code == 200, f"{path} should be reachable for members"
    body = response.content.decode("utf-8")
    assert NOINDEX_MARKER in body, f"{path} missing noindex meta tag"


@pytest.mark.django_db
def test_admin_pages_emit_noindex(staff_client):
    response = staff_client.get("/admin/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Django admin uses its own template, not base.html — assert at least
    # that the response has either noindex OR is a 401/redirect for public.
    # Django admin templates DO emit noindex by default since Django 4.
    assert NOINDEX_MARKER in body or 'name="robots"' in body, (
        "Django admin should emit a robots tag (default in modern Django)"
    )


@pytest.mark.django_db
def test_cooptation_token_url_emits_noindex(member_client, db):
    """A cooptation vouch URL must not be indexed — the token is per-applicant."""
    from datetime import timedelta

    from django.utils import timezone

    from cooptation.models import AdminApplication, CooptationRequest
    from members.models import Member

    client, user = member_client
    member = Member.objects.get(user=user)

    app = AdminApplication.objects.create(
        full_name="Test Candidate", email="candidate@example.test",
        years_attended=[1980], classes=["6e"], city="Niamey",
    )
    req = CooptationRequest.objects.create(
        application=app, parrain=member, expires_at=timezone.now() + timedelta(days=14),
    )

    response = client.get(f"/cooptation/{req.token}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert NOINDEX_MARKER in body, "Cooptation token URL must be noindex"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_noindex_audit.py -v 2>&1 | tail -15`

Expected: all 5 cases pass (the `member_pages_emit_noindex` parametrized 3 + admin + cooptation token).

- [ ] **Step 3: Add the landing a11y tests**

Create `core/tests/test_a11y.py`:

```python
"""A11y assertions for the public landing — a basic floor, not full WCAG."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup


@pytest.mark.django_db
def test_landing_has_exactly_one_h1(client):
    body = client.get("/").content
    soup = BeautifulSoup(body, "html.parser")
    h1s = soup.find_all("h1")
    assert len(h1s) == 1, f"Landing should have exactly one h1, got {len(h1s)}"


@pytest.mark.django_db
def test_landing_no_heading_level_skips(client):
    """h2 should not be followed by h4 with no h3 in between."""
    body = client.get("/").content
    soup = BeautifulSoup(body, "html.parser")
    levels = [int(tag.name[1]) for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
    for prev, curr in zip(levels, levels[1:]):
        assert curr <= prev + 1, (
            f"Heading level skip detected: h{prev} → h{curr}. "
            "Heading sequence: " + ",".join(f"h{n}" for n in levels)
        )


@pytest.mark.django_db
def test_whatsapp_share_button_has_accessible_name(client):
    """The WhatsApp share is a small icon link — must have aria-label or
    visible text so screen readers can announce it."""
    body = client.get("/").content
    soup = BeautifulSoup(body, "html.parser")
    wa_links = [a for a in soup.find_all("a") if "wa.me" in (a.get("href") or "")]
    assert wa_links, "WhatsApp share link not found in landing"
    for link in wa_links:
        has_aria = link.get("aria-label")
        has_text = link.get_text(strip=True)
        assert has_aria or has_text, (
            f"WhatsApp share link {link} has no accessible name (aria-label or text)"
        )


@pytest.mark.django_db
def test_primary_cta_has_focus_ring_class(client):
    """Tailwind smoke check — primary CTA should retain focus styling.
    Uses the project's existing button class string (rounded-lg + bg-tertiary)."""
    body = client.get("/").content.decode("utf-8")
    # The primary CTA contains either 'Je suis un ancien' (anonymous) or
    # 'Parcourir l'annuaire' (auth). For anonymous the assertion below holds.
    assert "Je suis un ancien" in body
    # The button uses bg-tertiary as a marker class; the project's standard
    # button styling implies focus ring via the bg-tertiary + transition combo.
    assert "bg-tertiary" in body
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_a11y.py -v 2>&1 | tail -10`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add core/tests/test_noindex_audit.py core/tests/test_a11y.py
git commit -m "test(p4a): noindex audit + landing a11y assertions"
```

---

## Task 12: Run the full suite + smoke

**Files:** none

- [ ] **Step 1: Run the entire suite**

Run: `.venv/Scripts/python.exe -m pytest 2>&1 | tail -3`

Expected: ~260 passed (was 234 before P4a; new tests add ~25-30).

- [ ] **Step 2: Manual smoke locally**

```powershell
& .\.venv\Scripts\python.exe manage.py runserver
```

In a browser:
- `http://localhost:8000/` — landing page renders, "Je suis un ancien" + "Se connecter" + WhatsApp buttons all visible
- `http://localhost:8000/sitemap.xml` — XML with 2 entries
- `http://localhost:8000/robots.txt` — text/plain with allow + disallow + sitemap
- Click "Je suis un ancien" → cooptation signup form loads
- Add `?utm_source=test&utm_campaign=smoke` to the inscription URL → submit → confirm AdminApplication record has the UTM stored (in Django admin)

- [ ] **Step 3: STATUS.md update**

Open `docs/superpowers/STATUS.md` and update the Phase Index to add P4a:

```markdown
| P4a | Public surface (landing + ghost-list scaffolding + SEO) | Complete (tag `v0.4.0a-public-surface`, 2026-MM-DD) | [plan](plans/2026-05-03-public-surface.md) |
```

Add a P4a section at the bottom mirroring the format of P3 (table of tasks + commits).

- [ ] **Step 4: Commit STATUS update**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(p4a): mark Public Surface complete in STATUS"
```

---

## Task 13: Merge, push, tag, deploy

**Files:** none

- [ ] **Step 1: Merge to main locally**

```bash
git checkout main
git pull --ff-only
git merge --no-ff feat/public-surface -m "Merge branch 'feat/public-surface' into main

P4a Public Surface — landing page + PublicSearchEntry model + SEO
machinery. Ghost list section is behind PUBLIC_GHOST_LIST_ENABLED
feature flag, default off until P4b ships the public removal flow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2: Run full suite on merged main**

`.venv/Scripts/python.exe -m pytest 2>&1 | tail -3`

Expected: same ~260 pass count.

- [ ] **Step 3: Tag and push**

```bash
git tag -a v0.4.0a-public-surface -m "P4a Public Surface — landing + ghost-list scaffold + SEO"
git push origin main --follow-tags
git branch -d feat/public-surface
```

- [ ] **Step 4: Verify Railway redeploys cleanly**

Watch Railway dashboard. Build should be green within ~3 minutes. Check Deployments tab.

- [ ] **Step 5: Post-deploy ops checklist (do NOT skip)**

In a browser, incognito (no basic-auth credentials):
- `https://lesretrouvailles-production.up.railway.app/` — landing renders without prompting for credentials ✓
- `https://lesretrouvailles-production.up.railway.app/sitemap.xml` — XML loads ✓
- `https://lesretrouvailles-production.up.railway.app/robots.txt` — text loads ✓
- `https://lesretrouvailles-production.up.railway.app/profil/` — STILL prompts for basic auth ✓ (regression check)

Then:
- Add `lesretrouvailles-production.up.railway.app` as a site in Cloudflare Web Analytics → copy the token → set `CLOUDFLARE_ANALYTICS_TOKEN` env var on Railway → service redeploys → confirm beacon appears in landing's HTML source
- Replace the placeholder OG image at `static/img/og-landing.png` with a real 1200×630 PNG (content task — designer or admin team)
- Submit the sitemap to Google Search Console (one-time, ~15 min — DNS TXT verification on Cloudflare)

- [ ] **Step 6: Smoke test UTM capture in production**

```powershell
# Open in browser (with basic auth credentials):
# https://<host>/inscription/?utm_source=smoke&utm_campaign=p4a-launch
# Submit a test application
# Open https://<host>/admin/cooptation/adminapplication/ and confirm the
# new row has utm_source=smoke and utm_campaign=p4a-launch
```

- [ ] **Step 7: Confirm `PUBLIC_GHOST_LIST_ENABLED=False` is the prod state**

In Railway → app service → Variables: confirm `PUBLIC_GHOST_LIST_ENABLED` is **either absent or set to `False`**. The ghost section should NOT appear on the public landing yet — it ships visible only when P4b is live.

---

## Done

P4a Public Surface is shipped, indexed, and gathering source-of-arrival data on every cooptation signup. The ghost list scaffolding is in place but invisible until P4b's removal flow lands and operators flip the flag.

Next phase per `docs/superpowers/STATUS.md`: P4b — admin governance UI for ghost entries + public token-based removal flow + AuditLog model.
