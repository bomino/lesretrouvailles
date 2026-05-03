# P4b — Public Surface Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a public, friction-free "Retirer mon nom" removal flow with 30-day email-confirmation token, an append-only `AuditLog` model that records every governance action on the ghost list, and the operational unblock to flip `PUBLIC_GHOST_LIST_ENABLED=True`.

**Architecture:** Two new Django models (`AuditLog`, `RemovalRequest`) in `members/`. Removal flow is a 4-view full-page state machine: form (GET+POST) → "check email" page → email-confirmation handler (idempotent auto-execute) → expired page. Auto-execute on email-confirm per spec's "sans débat". AuditLog populated automatically via Django signals (post_save entry, m2m_changed signoffs, pre_delete RemovalRequest) so adding a new way to sign off / remove an entry doesn't require remembering to write to AuditLog.

**Tech Stack:** Django 5 · pytest + pytest-django · Tailwind/DaisyUI (already wired) · Postgres · Resend SDK (already wired in P3).

**Spec reference:** `docs/superpowers/specs/2026-05-03-public-surface-governance-design.md`.

---

## File map

**Files to CREATE:**
- `members/migrations/0008_auditlog_removalrequest_and_more.py` — two new models + tighten `removal_token`
- `members/emails.py` — 3 thin sender wrappers over `alumni.email.send_email`
- `members/templates/members/removal_request_form.html`
- `members/templates/members/removal_request_done.html`
- `members/templates/members/removal_confirmed.html`
- `members/templates/members/removal_expired_or_invalid.html`
- `members/templates/emails/members/removal_confirmation_pending.{subject.txt,txt,html}` (3 files)
- `members/templates/emails/members/removal_completed.{subject.txt,txt,html}` (3 files)
- `members/templates/emails/members/admin_removal_notification.{subject.txt,txt,html}` (3 files)
- `members/tests/test_audit_log.py` — model basics + admin append-only invariants
- `members/tests/test_removal_request.py` — model basics + cascade behavior
- `members/tests/test_removal_views.py` — 4 views, ~13 tests
- `members/tests/test_audit_signals.py` — 3 signal handlers, ~6 tests
- `members/tests/test_removal_emails.py` — 3 templates, ~5 tests

**Files to MODIFY:**
- `alumni/settings/base.py` — add `/retrait/` to `LOGIN_REQUIRED_WHITELIST`
- `core/middleware.py` — add `/retrait/` to `BASIC_AUTH_PUBLIC_PREFIXES`
- `members/models.py` — append `AuditLog`, `RemovalRequest`, `_make_token`; tighten `PublicSearchEntry.removal_token` to non-null with default
- `members/admin.py` — register `RemovalRequestAdmin`, `AuditLogAdmin`
- `members/signals.py` — append 3 receivers (post_save entry, m2m_changed signoffs, pre_delete RemovalRequest)
- `members/urls.py` — add 5 routes for the removal flow
- `members/views.py` — add 4 views (form, done, confirm, expired)
- `templates/core/landing.html` — add "Retirer mon nom" link in each rendered ghost card
- `core/tests/test_landing_view.py` — add 2 tests for the link rendering
- `core/tests/test_a11y.py` — add 1 test for the link's accessible name

---

## Task 1: Settings + middleware whitelist for `/retrait/`

**Files:**
- Modify: `alumni/settings/base.py`
- Modify: `core/middleware.py`
- Modify: `core/tests/test_basic_auth.py`

- [ ] **Step 1: Add `/retrait/` to `LOGIN_REQUIRED_WHITELIST`**

In `alumni/settings/base.py`, find the `LOGIN_REQUIRED_WHITELIST` list (currently 9 entries) and add `"/retrait/"`:

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
    "/retrait/",
]
```

- [ ] **Step 2: Add `/retrait/` to `BASIC_AUTH_PUBLIC_PREFIXES`**

In `core/middleware.py`, find:
```python
BASIC_AUTH_PUBLIC_PREFIXES = ("/static/", "/inscription/")
```

Replace with:
```python
BASIC_AUTH_PUBLIC_PREFIXES = ("/static/", "/inscription/", "/retrait/")
```

- [ ] **Step 3: Add the regression test for the bypass**

In `core/tests/test_basic_auth.py`, append:

```python
@pytest.mark.django_db
def test_basic_auth_bypasses_retrait_prefix(client, settings):
    """Public removal flow must be reachable without basic-auth credentials
    so people who want to opt out can do so even on the staging-gated env."""
    settings.MIDDLEWARE = PINNED_MIDDLEWARE
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    # 404 from the inner view is fine — we just need to confirm we got past
    # the 401 from BasicAuthMiddleware.
    response = client.get("/retrait/some-token-that-doesnt-match/")
    assert response.status_code != 401
```

(`PINNED_MIDDLEWARE` is the existing test-helper constant in `test_basic_auth.py` from Task 4 of P4a.)

- [ ] **Step 4: Run the test (should fail because the route doesn't exist yet, but bypass should work — Django returns 404 not 401)**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_basic_auth.py -k retrait -v 2>&1 | tail -10`

Expected: 1 passed (404 from URL resolver, which is `!=401`).

- [ ] **Step 5: Confirm Django boots**

Run: `.venv/Scripts/python.exe manage.py check 2>&1 | tail -3`

Expected: `System check identified 3 issues` (the 3 pre-existing allauth deprecation warnings).

- [ ] **Step 6: Commit**

```bash
git checkout -b feat/public-surface-governance
git add alumni/settings/base.py core/middleware.py core/tests/test_basic_auth.py
git commit -m "feat(p4b): whitelist /retrait/ for login + basic-auth bypass"
```

---

## Task 2: AuditLog model + migration + model tests

**Files:**
- Modify: `members/models.py` (append at bottom)
- Create: `members/tests/test_audit_log.py`

- [ ] **Step 1: Write the failing tests**

Create `members/tests/test_audit_log.py`:

```python
"""Tests for AuditLog — the append-only governance event log."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_audit_log_create_with_actor():
    from members.models import AuditLog

    User = get_user_model()  # noqa: N806
    u = User.objects.create_user(
        username="admin1", email="admin1@example.test", password="x", is_staff=True
    )
    log = AuditLog.objects.create(
        actor=u,
        action="ghost.entry.signed_off",
        target_type="members.PublicSearchEntry",
        target_id="42",
        metadata={"signoff_count_after": 1},
    )
    assert log.actor == u
    assert log.action == "ghost.entry.signed_off"
    assert log.target_id == "42"
    assert log.metadata == {"signoff_count_after": 1}


@pytest.mark.django_db
def test_audit_log_create_anonymous_actor():
    """Anonymous actions (e.g., a public removal request) have actor=None."""
    from members.models import AuditLog

    log = AuditLog.objects.create(
        actor=None,
        action="ghost.removal.requested",
        target_type="members.PublicSearchEntry",
        target_id="42",
        metadata={"requester_email": "x@y.test"},
    )
    assert log.actor is None
    assert log.metadata["requester_email"] == "x@y.test"


@pytest.mark.django_db
def test_audit_log_metadata_accepts_nested_structures():
    from members.models import AuditLog

    log = AuditLog.objects.create(
        actor=None,
        action="ghost.entry.created",
        target_type="members.PublicSearchEntry",
        target_id="1",
        metadata={
            "first_name": "Test",
            "tags": ["one", "two"],
            "deep": {"nested": True},
        },
    )
    log.refresh_from_db()
    assert log.metadata["tags"] == ["one", "two"]
    assert log.metadata["deep"]["nested"] is True


@pytest.mark.django_db
def test_audit_log_str_includes_action_and_target():
    from members.models import AuditLog

    log = AuditLog.objects.create(
        actor=None,
        action="ghost.removal.executed",
        target_type="members.PublicSearchEntry",
        target_id="7",
    )
    s = str(log)
    assert "ghost.removal.executed" in s
    assert "members.PublicSearchEntry:7" in s
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_audit_log.py -x -q 2>&1 | tail -5`

Expected: ImportError or `module 'members.models' has no attribute 'AuditLog'`.

- [ ] **Step 3: Add the AuditLog model and `_make_token` helper to `members/models.py`**

Append to the bottom of `members/models.py`:

```python
def _make_token() -> str:
    """Opaque random token. Used for PublicSearchEntry.removal_token and
    RemovalRequest.confirm_token. Mirrors cooptation.models._make_token."""
    import secrets
    return secrets.token_urlsafe(32)


class AuditLog(models.Model):
    """Append-only governance event log.

    Domain audit fields (e.g., AdminApplication.reviewed_by) stay on
    their respective models — this table records cross-domain events
    that would otherwise be invisible to a future "who did what when"
    query. Never mutated after insert. Retention: indefinite.
    """

    ACTION_CHOICES = [
        ("ghost.entry.created", "Fiche fantôme créée"),
        ("ghost.entry.signed_off", "Cosignature ajoutée"),
        ("ghost.entry.signoff_removed", "Cosignature retirée"),
        ("ghost.removal.requested", "Demande de retrait soumise"),
        ("ghost.removal.confirmed", "Demande de retrait confirmée"),
        ("ghost.removal.executed", "Retrait exécuté"),
        ("ghost.removal.cancelled", "Demande de retrait annulée par admin"),
        ("ghost.entry.purged", "Fiche purgée"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_log_entries",
        help_text="Null for anonymous actions (e.g., a public removal request).",
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=64)
    target_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} on {self.target_type}:{self.target_id} @ {self.created_at:%Y-%m-%d %H:%M}"
```

- [ ] **Step 4: Generate the migration**

Run (PowerShell):
```powershell
$env:DJANGO_SETTINGS_MODULE='alumni.settings.dev'; & .\.venv\Scripts\python.exe manage.py makemigrations members
```

Expected: creates `members/migrations/0008_auditlog.py` (or similar — Django auto-names).

- [ ] **Step 5: Apply the migration**

```powershell
& .\.venv\Scripts\python.exe manage.py migrate members
```

Expected: `Applying members.0008_... OK`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_audit_log.py -v 2>&1 | tail -10`

Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add members/models.py members/migrations/0008_*.py members/tests/test_audit_log.py
git commit -m "feat(p4b): add AuditLog append-only governance event log"
```

---

## Task 3: RemovalRequest model + migration + tighten PublicSearchEntry.removal_token

**Files:**
- Modify: `members/models.py` (append RemovalRequest, modify PublicSearchEntry.removal_token)
- Create: `members/tests/test_removal_request.py`

- [ ] **Step 1: Write the failing tests**

Create `members/tests/test_removal_request.py`:

```python
"""Tests for RemovalRequest — the public 'Retirer mon nom' record."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone


@pytest.fixture
def make_admin(db):
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


@pytest.fixture
def entry(db, make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    e.added_by_admins.add(make_admin(), make_admin())
    return e


@pytest.mark.django_db
def test_removal_request_default_status_pending(entry):
    from members.models import RemovalRequest

    r = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    assert r.status == "pending_confirmation"


@pytest.mark.django_db
def test_removal_request_expires_at_30_days_default(entry):
    from members.models import RemovalRequest

    r = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    delta = r.expires_at - r.requested_at
    assert timedelta(days=29, hours=23) <= delta <= timedelta(days=30, minutes=1)


@pytest.mark.django_db
def test_removal_request_confirm_token_unique(entry):
    from django.db import transaction

    from members.models import RemovalRequest

    RemovalRequest.objects.create(
        entry=entry, requester_email="a@x.test", confirm_token="dup-token"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RemovalRequest.objects.create(
                entry=entry, requester_email="b@x.test", confirm_token="dup-token"
            )


@pytest.mark.django_db
def test_removal_request_confirm_token_auto_generated(entry):
    from members.models import RemovalRequest

    r1 = RemovalRequest.objects.create(entry=entry, requester_email="a@x.test")
    r2 = RemovalRequest.objects.create(entry=entry, requester_email="b@x.test")
    assert r1.confirm_token
    assert r2.confirm_token
    assert r1.confirm_token != r2.confirm_token


@pytest.mark.django_db
def test_removal_request_cascade_delete_with_entry(entry):
    """Deleting an entry deletes its RemovalRequests; AuditLog rows stay
    (covered separately in test_audit_signals.py)."""
    from members.models import RemovalRequest

    r = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    rid = r.pk
    entry.delete()
    assert not RemovalRequest.objects.filter(pk=rid).exists()


@pytest.mark.django_db
def test_public_search_entry_removal_token_auto_generated_and_unique(make_admin):
    """P4b tightens removal_token to non-null with default. Two entries
    must get distinct tokens automatically."""
    from members.models import PublicSearchEntry

    e1 = PublicSearchEntry.objects.create(
        first_name="A", last_name_initial="A.", years_at_ceg=[1980]
    )
    e2 = PublicSearchEntry.objects.create(
        first_name="B", last_name_initial="B.", years_at_ceg=[1980]
    )
    assert e1.removal_token
    assert e2.removal_token
    assert e1.removal_token != e2.removal_token
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_removal_request.py -x -q 2>&1 | tail -5`

Expected: ImportError on `RemovalRequest`.

- [ ] **Step 3: Add the RemovalRequest model**

Append to `members/models.py` (after `AuditLog`):

```python
class RemovalRequest(models.Model):
    """A public 'Retirer mon nom' request awaiting email confirmation.

    Created when the visitor submits the removal form; rendered
    redundant once the entry is removed (via on_delete=CASCADE) but
    the AuditLog entries about the request remain.
    """

    STATUS_CHOICES = [
        ("pending_confirmation", "En attente de confirmation"),
        ("confirmed", "Confirmée — retrait exécuté"),
        ("expired", "Expirée — non confirmée"),
    ]

    entry = models.ForeignKey(
        "members.PublicSearchEntry",
        on_delete=models.CASCADE,
        related_name="removal_requests",
    )
    requester_email = models.EmailField()
    reason = models.CharField(max_length=200, blank=True)
    confirm_token = models.CharField(
        max_length=64, unique=True, db_index=True, default=_make_token
    )
    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default="pending_confirmation"
    )
    requester_ip = models.GenericIPAddressField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.expires_at:
            from datetime import timedelta

            from django.utils import timezone

            self.expires_at = (self.requested_at or timezone.now()) + timedelta(days=30)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [models.Index(fields=["status", "expires_at"])]
```

- [ ] **Step 4: Tighten `PublicSearchEntry.removal_token`**

Find the existing field in `PublicSearchEntry`:

```python
removal_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
```

Replace with:

```python
removal_token = models.CharField(max_length=64, unique=True, default=_make_token)
```

(Drops `null=True, blank=True` and adds a default. `_make_token` is defined above the class.)

- [ ] **Step 5: Generate the migration**

```powershell
$env:DJANGO_SETTINGS_MODULE='alumni.settings.dev'; & .\.venv\Scripts\python.exe manage.py makemigrations members
```

Django will likely prompt about removing `null` from `removal_token` — accept (any existing rows have NULL but the auto-generated default will fill them on application of the migration).

If the prompt asks for a one-off default to apply to existing NULLs: choose option 1 (provide a default), then enter:
```python
__import__('secrets').token_urlsafe(32)
```

This generates a random token for any pre-existing rows. (At deploy time there should be zero, since P4a kept the section hidden.)

- [ ] **Step 6: Apply the migration**

```powershell
& .\.venv\Scripts\python.exe manage.py migrate members
```

- [ ] **Step 7: Run the new tests + the existing PublicSearchEntry tests to confirm no regression**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_removal_request.py members/tests/test_public_search_entry.py -v 2>&1 | tail -15`

Expected: 6 (new) + 7 (existing) = 13 passed.

- [ ] **Step 8: Commit**

```bash
git add members/models.py members/migrations/0009_*.py members/tests/test_removal_request.py
git commit -m "feat(p4b): add RemovalRequest + tighten PublicSearchEntry.removal_token"
```

---

## Task 4: Audit signal handlers + tests

**Files:**
- Modify: `members/signals.py` (append 3 receivers)
- Create: `members/tests/test_audit_signals.py`

- [ ] **Step 1: Write the failing tests**

Create `members/tests/test_audit_signals.py`:

```python
"""Tests that ORM events on PublicSearchEntry / RemovalRequest write
the right AuditLog entries."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def make_admin(db):
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
def test_creating_entry_writes_audit_entry_created(make_admin):
    from members.models import AuditLog, PublicSearchEntry

    AuditLog.objects.all().delete()  # clear any prior signal noise
    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    log = AuditLog.objects.get(
        action="ghost.entry.created",
        target_type="members.PublicSearchEntry",
        target_id=str(e.pk),
    )
    assert log.metadata["first_name"] == "Idrissa"
    assert log.metadata["last_name_initial"] == "S."


@pytest.mark.django_db
def test_adding_admin_to_signoffs_writes_signed_off(make_admin):
    from members.models import AuditLog, PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    AuditLog.objects.filter(action="ghost.entry.signed_off").delete()
    a = make_admin()
    e.added_by_admins.add(a)
    log = AuditLog.objects.get(
        action="ghost.entry.signed_off",
        target_id=str(e.pk),
    )
    assert log.actor == a
    assert log.metadata["signer_pk"] == a.pk
    assert log.metadata["signoff_count_after"] == 1


@pytest.mark.django_db
def test_adding_two_admins_in_one_call_writes_two_audit_entries(make_admin):
    from members.models import AuditLog, PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    AuditLog.objects.filter(action="ghost.entry.signed_off").delete()
    a, b = make_admin(), make_admin()
    e.added_by_admins.add(a, b)
    logs = AuditLog.objects.filter(
        action="ghost.entry.signed_off", target_id=str(e.pk)
    )
    assert logs.count() == 2


@pytest.mark.django_db
def test_removing_admin_from_signoffs_writes_signoff_removed(make_admin):
    from members.models import AuditLog, PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    a = make_admin()
    e.added_by_admins.add(a)
    AuditLog.objects.filter(action="ghost.entry.signoff_removed").delete()
    e.added_by_admins.remove(a)
    log = AuditLog.objects.get(
        action="ghost.entry.signoff_removed", target_id=str(e.pk)
    )
    assert log.actor == a


@pytest.mark.django_db
def test_deleting_pending_removal_request_writes_cancelled(make_admin):
    from members.models import AuditLog, PublicSearchEntry, RemovalRequest

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    r = RemovalRequest.objects.create(entry=e, requester_email="x@y.test")
    rid = r.pk

    AuditLog.objects.filter(action="ghost.removal.cancelled").delete()
    r.delete()
    log = AuditLog.objects.get(
        action="ghost.removal.cancelled", target_id=str(rid)
    )
    assert log.metadata["entry_pk"] == e.pk
    assert log.metadata["requester_email"] == "x@y.test"


@pytest.mark.django_db
def test_deleting_confirmed_removal_request_does_not_write_cancelled(make_admin):
    """Only pending status triggers the cancellation hook — once confirmed,
    the existing 'requested'/'confirmed'/'executed' chain has the history."""
    from django.utils import timezone

    from members.models import AuditLog, PublicSearchEntry, RemovalRequest

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    r = RemovalRequest.objects.create(
        entry=e, requester_email="x@y.test", status="confirmed", confirmed_at=timezone.now()
    )
    AuditLog.objects.filter(action="ghost.removal.cancelled").delete()
    r.delete()
    assert not AuditLog.objects.filter(action="ghost.removal.cancelled").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_audit_signals.py -x -q 2>&1 | tail -5`

Expected: failures (signal handlers don't exist).

- [ ] **Step 3: Add signal handlers**

Open `members/signals.py`. The file already exists with one receiver for `Member` post_save. Replace its content with (preserves the existing receiver):

```python
"""Signal handlers for the membership app.

These hooks intentionally use signals (not explicit calls in admin /
service code) so the audit trail is automatic — adding a new way to
sign off or remove an entry doesn't require remembering to write to
AuditLog. The cost: signal handlers are easy to miss when grepping;
each handler has an explicit comment naming the audit hook.
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_save, pre_delete
from django.dispatch import receiver

from .models import AuditLog, Member, NotificationPreference, PublicSearchEntry, RemovalRequest


@receiver(post_save, sender=Member)
def create_preferences_for_new_member(sender, instance, created, **kwargs):
    """Existing P2 hook — auto-create NotificationPreference for new Members."""
    if created:
        NotificationPreference.objects.create(member=instance)


@receiver(post_save, sender=PublicSearchEntry)
def _audit_entry_created(sender, instance, created, **kwargs):
    """Audit hook for PublicSearchEntry creation."""
    if created:
        AuditLog.objects.create(
            actor=None,
            action="ghost.entry.created",
            target_type="members.PublicSearchEntry",
            target_id=str(instance.pk),
            metadata={
                "first_name": instance.first_name,
                "last_name_initial": instance.last_name_initial,
            },
        )


@receiver(m2m_changed, sender=PublicSearchEntry.added_by_admins.through)
def _audit_signoff_change(sender, instance, action, pk_set, **kwargs):
    """Audit hook for ghost-entry signoffs. Fires post_add and post_remove."""
    if action not in ("post_add", "post_remove"):
        return
    audit_action = (
        "ghost.entry.signed_off" if action == "post_add" else "ghost.entry.signoff_removed"
    )
    User = get_user_model()  # noqa: N806
    for admin_pk in pk_set or ():
        admin = User.objects.filter(pk=admin_pk).only("pk", "email").first()
        AuditLog.objects.create(
            actor=admin,
            action=audit_action,
            target_type="members.PublicSearchEntry",
            target_id=str(instance.pk),
            metadata={
                "signer_pk": admin_pk,
                "signer_email": admin.email if admin else "",
                "signoff_count_after": instance.added_by_admins.count(),
            },
        )


@receiver(pre_delete, sender=RemovalRequest)
def _audit_removal_request_cancelled(sender, instance, **kwargs):
    """Audit hook for admin-cancellation of a pending RemovalRequest.

    Only fires when status is still 'pending_confirmation'. Confirmed and
    expired requests have their history in the existing
    'requested'/'confirmed'/'executed' chain.
    """
    if instance.status != "pending_confirmation":
        return
    AuditLog.objects.create(
        actor=None,
        action="ghost.removal.cancelled",
        target_type="members.RemovalRequest",
        target_id=str(instance.pk),
        metadata={
            "entry_pk": instance.entry_id,
            "requester_email": instance.requester_email,
            "reason": instance.reason,
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_audit_signals.py -v 2>&1 | tail -15`

Expected: 6 passed.

- [ ] **Step 5: Run full members suite to confirm no regression**

Run: `.venv/Scripts/python.exe -m pytest members/tests/ -q 2>&1 | tail -3`

Expected: all members tests pass (P2 + P4a + new P4b).

- [ ] **Step 6: Commit**

```bash
git add members/signals.py members/tests/test_audit_signals.py
git commit -m "feat(p4b): audit signal handlers (entry create, signoff M2M, request cancel)"
```

---

## Task 5: Email senders + templates

**Files:**
- Create: `members/emails.py`
- Create: `members/templates/emails/members/removal_confirmation_pending.subject.txt`
- Create: `members/templates/emails/members/removal_confirmation_pending.txt`
- Create: `members/templates/emails/members/removal_confirmation_pending.html`
- Create: `members/templates/emails/members/removal_completed.subject.txt`
- Create: `members/templates/emails/members/removal_completed.txt`
- Create: `members/templates/emails/members/removal_completed.html`
- Create: `members/templates/emails/members/admin_removal_notification.subject.txt`
- Create: `members/templates/emails/members/admin_removal_notification.txt`
- Create: `members/templates/emails/members/admin_removal_notification.html`
- Create: `members/tests/test_removal_emails.py`

- [ ] **Step 1: Write the failing tests**

Create `members/tests/test_removal_emails.py`:

```python
"""Tests that the 3 P4b email templates render and contain the right data."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def fake_backend(settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.DEFAULT_FROM_EMAIL = "smoke@example.test"
    settings.SITE_URL = "https://prod.example.test"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    return FakeResendBackend


@pytest.fixture
def removal_request(db):
    from members.models import PublicSearchEntry, RemovalRequest

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa",
        last_name_initial="S.",
        years_at_ceg=[1980, 1981, 1982, 1983],
    )
    return RemovalRequest.objects.create(
        entry=e,
        requester_email="candidate@example.test",
        reason="Je veux disparaître",
    )


@pytest.mark.django_db
def test_removal_confirmation_pending_contains_confirm_url(fake_backend, removal_request):
    from members.emails import send_removal_confirmation_pending

    send_removal_confirmation_pending(removal_request)
    msg = fake_backend.sent_messages[0]
    assert msg["to"] == ["candidate@example.test"]
    expected_url = (
        f"https://prod.example.test/retrait/confirme/{removal_request.confirm_token}/"
    )
    assert expected_url in msg["text"]
    assert "Idrissa" in msg["text"]
    assert "S." in msg["text"]


@pytest.mark.django_db
def test_removal_completed_acknowledges_entry(fake_backend, removal_request):
    from members.emails import send_removal_completed

    send_removal_completed(removal_request)
    msg = fake_backend.sent_messages[0]
    assert msg["to"] == ["candidate@example.test"]
    assert "Idrissa" in msg["text"]
    assert "S." in msg["text"]


@pytest.mark.django_db
def test_admin_removal_notification_to_all_staff(fake_backend, removal_request):
    User = get_user_model()  # noqa: N806
    User.objects.create_user(
        username="staff1", email="staff1@example.test", password="x", is_staff=True
    )
    User.objects.create_user(
        username="staff2", email="staff2@example.test", password="x", is_staff=True
    )
    User.objects.create_user(
        username="user1", email="user1@example.test", password="x"
    )  # not staff

    from members.emails import send_admin_removal_notification

    send_admin_removal_notification(removal_request)
    msg = fake_backend.sent_messages[0]
    assert sorted(msg["to"]) == ["staff1@example.test", "staff2@example.test"]


@pytest.mark.django_db
def test_admin_removal_notification_no_op_with_no_staff(fake_backend, removal_request):
    """No staff users → don't send (and don't crash)."""
    from members.emails import send_admin_removal_notification

    send_admin_removal_notification(removal_request)
    assert len(fake_backend.sent_messages) == 0


@pytest.mark.django_db
def test_all_three_templates_use_french(fake_backend, removal_request):
    User = get_user_model()  # noqa: N806
    User.objects.create_user(
        username="staff", email="staff@example.test", password="x", is_staff=True
    )
    from members.emails import (
        send_admin_removal_notification,
        send_removal_completed,
        send_removal_confirmation_pending,
    )

    send_removal_confirmation_pending(removal_request)
    send_removal_completed(removal_request)
    send_admin_removal_notification(removal_request)
    french_markers = ["bonjour", "votre", "retrait", "demande", "merci", "équipe"]
    for m in fake_backend.sent_messages:
        body = m["text"].lower()
        assert any(marker in body for marker in french_markers), m["subject"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_removal_emails.py -x -q 2>&1 | tail -5`

Expected: ImportError on `members.emails`.

- [ ] **Step 3: Create `members/emails.py`**

```python
"""Email senders for the membership app — thin wrappers over send_email."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from alumni.email import send_email

from .models import RemovalRequest


def send_removal_confirmation_pending(removal_request: RemovalRequest) -> None:
    """To the requester after they submit the form. Contains the
    confirmation link and the entry preview so they can verify they're
    removing the right person."""
    send_email(
        removal_request.requester_email,
        "members/removal_confirmation_pending",
        {"request": removal_request, "entry": removal_request.entry},
    )


def send_removal_completed(removal_request: RemovalRequest) -> None:
    """To the requester after auto-execution. Acknowledgment, no action
    required."""
    send_email(
        removal_request.requester_email,
        "members/removal_completed",
        {"request": removal_request, "entry": removal_request.entry},
    )


def send_admin_removal_notification(removal_request: RemovalRequest) -> None:
    """FYI to all active staff after auto-execution. Transparency, not
    action-required. Lets admins notice patterns (e.g., 5 removals in
    1 minute = bot attack)."""
    User = get_user_model()  # noqa: N806
    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True)
        .values_list("email", flat=True)
    )
    if not staff_emails:
        return
    send_email(
        staff_emails,
        "members/admin_removal_notification",
        {"request": removal_request, "entry": removal_request.entry},
    )
```

- [ ] **Step 4: Create the 3 subject template files**

`members/templates/emails/members/removal_confirmation_pending.subject.txt`:
```
Confirmez le retrait de votre nom — Les Retrouvailles
```

`members/templates/emails/members/removal_completed.subject.txt`:
```
Votre nom a été retiré — Les Retrouvailles
```

`members/templates/emails/members/admin_removal_notification.subject.txt`:
```
[admin] Retrait exécuté : {{ entry.first_name }} {{ entry.last_name_initial }}
```

- [ ] **Step 5: Create the 3 plain-text bodies**

`members/templates/emails/members/removal_confirmation_pending.txt`:
```
Bonjour,

Vous avez demandé le retrait du nom suivant de la liste publique des Retrouvailles :

{{ entry.first_name }} {{ entry.last_name_initial }} — années {{ entry.first_year }}-{{ entry.last_year }}

Pour confirmer cette demande, cliquez sur le lien ci-dessous (valable 30 jours) :

{{ site_url }}/retrait/confirme/{{ request.confirm_token }}/

Si vous n'êtes pas à l'origine de cette demande, ignorez ce message — aucune action ne sera prise sans confirmation.

L'équipe Les Retrouvailles
```

`members/templates/emails/members/removal_completed.txt`:
```
Bonjour,

Le nom suivant a été retiré de la liste publique des Retrouvailles :

{{ entry.first_name }} {{ entry.last_name_initial }} — années {{ entry.first_year }}-{{ entry.last_year }}

Cette action est définitive. Si c'était une erreur, contactez l'équipe en répondant à ce message.

L'équipe Les Retrouvailles
```

`members/templates/emails/members/admin_removal_notification.txt`:
```
Bonjour,

Un retrait public a été exécuté.

Détails :
- Nom retiré : {{ entry.first_name }} {{ entry.last_name_initial }} (années {{ entry.first_year }}-{{ entry.last_year }})
- Email du demandeur : {{ request.requester_email }}
- Raison fournie : {{ request.reason|default:"(aucune)" }}
- Date et heure : {{ request.confirmed_at }}

Lien admin : {{ site_url }}/admin/members/publicsearchentry/{{ entry.pk }}/change/

L'équipe Les Retrouvailles
```

- [ ] **Step 6: Create the 3 HTML bodies**

`members/templates/emails/members/removal_confirmation_pending.html`:
```html
<!DOCTYPE html>
<html lang="fr">
    <body style="font-family: Inter, system-ui, sans-serif; color: #1a1c1e">
        <p>Bonjour,</p>
        <p>
            Vous avez demandé le retrait du nom suivant de la liste publique
            des Retrouvailles :
        </p>
        <p>
            <strong>{{ entry.first_name }} {{ entry.last_name_initial }}</strong>
            — années {{ entry.first_year }}-{{ entry.last_year }}
        </p>
        <p>
            Pour confirmer cette demande, cliquez sur le bouton ci-dessous
            (valable 30 jours) :
        </p>
        <p>
            <a href="{{ site_url }}/retrait/confirme/{{ request.confirm_token }}/"
               style="display:inline-block;padding:12px 24px;background:#a04a2c;color:#fff;text-decoration:none;border-radius:8px;">
                Confirmer le retrait
            </a>
        </p>
        <p>
            Si vous n'êtes pas à l'origine de cette demande, ignorez ce
            message — aucune action ne sera prise sans confirmation.
        </p>
        <p>L'équipe Les Retrouvailles</p>
    </body>
</html>
```

`members/templates/emails/members/removal_completed.html`:
```html
<!DOCTYPE html>
<html lang="fr">
    <body style="font-family: Inter, system-ui, sans-serif; color: #1a1c1e">
        <p>Bonjour,</p>
        <p>Le nom suivant a été retiré de la liste publique des Retrouvailles :</p>
        <p>
            <strong>{{ entry.first_name }} {{ entry.last_name_initial }}</strong>
            — années {{ entry.first_year }}-{{ entry.last_year }}
        </p>
        <p>
            Cette action est définitive. Si c'était une erreur, contactez
            l'équipe en répondant à ce message.
        </p>
        <p>L'équipe Les Retrouvailles</p>
    </body>
</html>
```

`members/templates/emails/members/admin_removal_notification.html`:
```html
<!DOCTYPE html>
<html lang="fr">
    <body style="font-family: Inter, system-ui, sans-serif; color: #1a1c1e">
        <p>Bonjour,</p>
        <p>Un retrait public a été exécuté.</p>
        <table style="border-collapse: collapse">
            <tr>
                <td style="padding: 4px 12px 4px 0; color: #6c7278">Nom retiré</td>
                <td>
                    <strong>{{ entry.first_name }} {{ entry.last_name_initial }}</strong>
                    (années {{ entry.first_year }}-{{ entry.last_year }})
                </td>
            </tr>
            <tr>
                <td style="padding: 4px 12px 4px 0; color: #6c7278">
                    Email du demandeur
                </td>
                <td>{{ request.requester_email }}</td>
            </tr>
            <tr>
                <td style="padding: 4px 12px 4px 0; color: #6c7278">
                    Raison fournie
                </td>
                <td>{{ request.reason|default:"(aucune)" }}</td>
            </tr>
            <tr>
                <td style="padding: 4px 12px 4px 0; color: #6c7278">
                    Date et heure
                </td>
                <td>{{ request.confirmed_at }}</td>
            </tr>
        </table>
        <p>
            <a href="{{ site_url }}/admin/members/publicsearchentry/{{ entry.pk }}/change/">
                Voir la fiche dans l'admin
            </a>
        </p>
        <p>L'équipe Les Retrouvailles</p>
    </body>
</html>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_removal_emails.py -v 2>&1 | tail -15`

Expected: 5 passed.

- [ ] **Step 8: Commit**

```bash
git add members/emails.py members/templates/emails/ members/tests/test_removal_emails.py
git commit -m "feat(p4b): 3 removal-flow email templates + senders"
```

---

## Task 6: Removal request form view + done page

**Files:**
- Modify: `members/views.py` (append views)
- Modify: `members/urls.py` (append routes)
- Create: `members/templates/members/removal_request_form.html`
- Create: `members/templates/members/removal_request_done.html`
- Create: `members/tests/test_removal_views.py` (this task creates the file with the form-view tests; later tasks append to it)

- [ ] **Step 1: Write the failing tests**

Create `members/tests/test_removal_views.py`:

```python
"""Tests for the public 'Retirer mon nom' flow views."""

from __future__ import annotations

import pytest


@pytest.fixture
def entry(db):
    from members.models import PublicSearchEntry

    return PublicSearchEntry.objects.create(
        first_name="Idrissa",
        last_name_initial="S.",
        years_at_ceg=[1980, 1981, 1982, 1983],
    )


@pytest.mark.django_db
def test_form_get_valid_token_returns_200_with_preview(client, entry):
    response = client.get(f"/retrait/{entry.removal_token}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Idrissa" in body
    assert "S." in body
    # Form fields present
    assert 'name="email"' in body
    assert 'name="reason"' in body


@pytest.mark.django_db
def test_form_get_unknown_token_404(client):
    response = client.get("/retrait/unknown-token/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_form_post_creates_request_and_sends_email(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.SITE_URL = "https://prod.example.test"
    from alumni.email import FakeResendBackend

    from members.models import RemovalRequest

    FakeResendBackend.sent_messages.clear()
    response = client.post(
        f"/retrait/{entry.removal_token}/",
        {"email": "candidate@example.test", "reason": "Je veux disparaître"},
        REMOTE_ADDR="203.0.113.7",
    )
    assert response.status_code == 302
    assert response["Location"] == "/retrait/merci/"

    r = RemovalRequest.objects.get(entry=entry, requester_email="candidate@example.test")
    assert r.reason == "Je veux disparaître"
    assert r.requester_ip == "203.0.113.7"
    assert r.status == "pending_confirmation"

    # Email sent
    assert len(FakeResendBackend.sent_messages) == 1
    msg = FakeResendBackend.sent_messages[0]
    assert msg["to"] == ["candidate@example.test"]
    assert r.confirm_token in msg["text"]


@pytest.mark.django_db
def test_form_post_writes_audit_requested(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import AuditLog

    AuditLog.objects.filter(action="ghost.removal.requested").delete()
    client.post(
        f"/retrait/{entry.removal_token}/",
        {"email": "candidate@example.test", "reason": ""},
    )
    log = AuditLog.objects.get(action="ghost.removal.requested")
    assert log.metadata["requester_email"] == "candidate@example.test"


@pytest.mark.django_db
def test_form_post_works_when_flag_off(client, entry, settings):
    """Removal respects consent independent of public visibility."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.PUBLIC_GHOST_LIST_ENABLED = False
    from members.models import RemovalRequest

    response = client.post(
        f"/retrait/{entry.removal_token}/",
        {"email": "candidate@example.test"},
    )
    assert response.status_code == 302
    assert RemovalRequest.objects.filter(entry=entry).exists()


@pytest.mark.django_db
def test_done_page_returns_200(client):
    response = client.get("/retrait/merci/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Vérifiez votre boîte mail" in body or "Vérifiez votre boite mail" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_removal_views.py -x -q 2>&1 | tail -10`

Expected: 404s and `NoReverseMatch` errors (URLs not wired).

- [ ] **Step 3: Add the views to `members/views.py`**

Find the existing imports at the top of `members/views.py`. Make sure these are present (add any missing):

```python
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
from django.utils import timezone
```

Append to the bottom of `members/views.py`:

```python
from .models import RemovalRequest  # noqa: E402  (grouped with members imports)
from . import emails as members_emails  # noqa: E402


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def removal_request_form_view(request, entry_token: str):
    from .models import PublicSearchEntry

    entry = get_object_or_404(PublicSearchEntry, removal_token=entry_token)

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()[:254]
        reason = (request.POST.get("reason") or "").strip()[:200]
        if not email:
            return render(
                request,
                "members/removal_request_form.html",
                {"entry": entry, "error": "Email requis."},
                status=400,
            )

        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")

        rreq = RemovalRequest.objects.create(
            entry=entry,
            requester_email=email,
            reason=reason,
            requester_ip=ip,
        )

        # Audit + email outside the create call so a failure here doesn't
        # leave a half-initialized record (the email send is best-effort
        # but its absence on disk would be noticed by the requester not
        # getting a confirmation mail — they can just resubmit).
        from .models import AuditLog

        AuditLog.objects.create(
            actor=None,
            action="ghost.removal.requested",
            target_type="members.RemovalRequest",
            target_id=str(rreq.pk),
            metadata={
                "entry_pk": entry.pk,
                "requester_email": email,
                "reason": reason,
            },
        )
        members_emails.send_removal_confirmation_pending(rreq)
        return HttpResponseRedirect("/retrait/merci/")

    return render(request, "members/removal_request_form.html", {"entry": entry})


@require_http_methods(["GET"])
def removal_request_done_view(request):
    return render(request, "members/removal_request_done.html")
```

- [ ] **Step 4: Wire the URLs in `members/urls.py`**

Find the existing `urlpatterns` and append:

```python
    path(
        "retrait/<str:entry_token>/",
        views.removal_request_form_view,
        name="removal_request_form",
    ),
    path(
        "retrait/merci/",
        views.removal_request_done_view,
        name="removal_request_done",
    ),
```

> Note: Order matters. `/retrait/merci/` must come AFTER `/retrait/<str:entry_token>/` because Django evaluates URL patterns top-to-bottom… **wait**, actually `<str:entry_token>` is greedy so `/retrait/merci/` would match it as `entry_token="merci"` and 404. **Put `/retrait/merci/` BEFORE the token pattern**, OR use a path converter that excludes literal "merci". The simpler fix: put `/retrait/merci/` first, and the same for `/retrait/expire/` and `/retrait/confirme/...` in later tasks.

Corrected order:
```python
    path(
        "retrait/merci/",
        views.removal_request_done_view,
        name="removal_request_done",
    ),
    path(
        "retrait/<str:entry_token>/",
        views.removal_request_form_view,
        name="removal_request_form",
    ),
```

- [ ] **Step 5: Create the form template**

`members/templates/members/removal_request_form.html`:

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Retirer mon nom" %}{% endblock %}
{% block content %}
    <section class="mx-auto max-w-2xl px-4 py-10 md:py-16">
        <h1 class="font-display text-3xl font-semibold tracking-tight md:text-4xl">
            {% trans "Retirer mon nom" %}
        </h1>
        <p class="mt-4 text-secondary">
            {% trans "Vous demandez le retrait du nom suivant de la liste publique :" %}
        </p>
        <article class="mt-4 rounded-2xl border border-secondary/15 bg-surface/70 p-5 shadow-sm">
            <strong class="font-display text-lg">{{ entry.first_name }} {{ entry.last_name_initial }}</strong>
            <p class="mt-1 text-sm text-secondary">
                {% trans "années" %} {{ entry.first_year }}-{{ entry.last_year }}
            </p>
        </article>

        {% if error %}
            <p class="mt-6 rounded-md bg-red-50 p-3 text-sm text-red-800">{{ error }}</p>
        {% endif %}

        <form method="post" class="mt-8 space-y-5">
            {% csrf_token %}
            <div>
                <label for="email" class="mb-1 block text-sm font-medium">
                    {% trans "Votre email" %}
                </label>
                <input id="email"
                       type="email"
                       name="email"
                       required
                       class="block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2 text-base shadow-sm focus:border-tertiary focus:outline-none focus:ring-2 focus:ring-tertiary/30">
                <p class="mt-1 text-xs text-secondary">
                    {% trans "Un email de confirmation vous sera envoyé. Le lien expire dans 30 jours." %}
                </p>
            </div>
            <div>
                <label for="reason" class="mb-1 block text-sm font-medium">
                    {% trans "Raison (optionnel)" %}
                </label>
                <textarea id="reason"
                          name="reason"
                          rows="3"
                          maxlength="200"
                          class="block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2 text-base shadow-sm focus:border-tertiary focus:outline-none focus:ring-2 focus:ring-tertiary/30"></textarea>
            </div>
            <button type="submit"
                    class="inline-flex items-center gap-2 rounded-lg bg-tertiary px-6 py-3 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 transition min-h-tap">
                {% trans "Envoyer la demande" %}
            </button>
        </form>
    </section>
{% endblock %}
```

- [ ] **Step 6: Create the done template**

`members/templates/members/removal_request_done.html`:

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Demande envoyée" %}{% endblock %}
{% block content %}
    <section class="mx-auto max-w-2xl px-4 py-16 text-center">
        <span class="inline-flex h-14 w-14 items-center justify-center rounded-full bg-tertiary/10 text-tertiary text-3xl">✉️</span>
        <h1 class="mt-6 font-display text-3xl font-semibold tracking-tight md:text-4xl">
            {% trans "Demande envoyée" %}
        </h1>
        <p class="mx-auto mt-4 max-w-md text-lg text-secondary">
            {% trans "Vérifiez votre boîte mail. Un message de confirmation vient de partir. Le lien expire dans 30 jours." %}
        </p>
        <p class="mx-auto mt-2 max-w-md text-sm text-secondary">
            {% trans "Si vous ne le voyez pas, vérifiez le dossier spam." %}
        </p>
    </section>
{% endblock %}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_removal_views.py -v 2>&1 | tail -15`

Expected: 6 passed.

- [ ] **Step 8: Commit**

```bash
git add members/views.py members/urls.py members/templates/members/ members/tests/test_removal_views.py
git commit -m "feat(p4b): public removal request form + done page"
```

---

## Task 7: Removal confirmation view + idempotent state machine + remaining templates

**Files:**
- Modify: `members/views.py` (append `removal_confirm_view` + `removal_expired_view`)
- Modify: `members/urls.py` (append 2 routes)
- Create: `members/templates/members/removal_confirmed.html`
- Create: `members/templates/members/removal_expired_or_invalid.html`
- Modify: `members/tests/test_removal_views.py` (append confirm-view tests)

- [ ] **Step 1: Append failing tests to `members/tests/test_removal_views.py`**

```python
@pytest.mark.django_db
def test_confirm_valid_pending_executes_removal(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from django.contrib.auth import get_user_model
    from alumni.email import FakeResendBackend

    from members.models import RemovalRequest

    User = get_user_model()  # noqa: N806
    User.objects.create_user(
        username="staff", email="staff@example.test", password="x", is_staff=True
    )

    rreq = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    FakeResendBackend.sent_messages.clear()

    response = client.get(f"/retrait/confirme/{rreq.confirm_token}/")
    assert response.status_code == 200

    entry.refresh_from_db()
    rreq.refresh_from_db()
    assert entry.removed_at is not None
    assert rreq.status == "confirmed"
    assert rreq.confirmed_at is not None

    # 2 emails sent: requester + admin
    recipients = [tuple(m["to"]) for m in FakeResendBackend.sent_messages]
    assert ("x@y.test",) in recipients
    assert ("staff@example.test",) in recipients


@pytest.mark.django_db
def test_confirm_writes_two_audit_entries(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from members.models import AuditLog, RemovalRequest

    rreq = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    AuditLog.objects.filter(
        action__in=["ghost.removal.confirmed", "ghost.removal.executed"]
    ).delete()

    client.get(f"/retrait/confirme/{rreq.confirm_token}/")
    assert AuditLog.objects.filter(action="ghost.removal.confirmed").count() == 1
    assert AuditLog.objects.filter(action="ghost.removal.executed").count() == 1


@pytest.mark.django_db
def test_confirm_already_confirmed_is_idempotent(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from django.utils import timezone
    from alumni.email import FakeResendBackend

    from members.models import RemovalRequest

    rreq = RemovalRequest.objects.create(
        entry=entry,
        requester_email="x@y.test",
        status="confirmed",
        confirmed_at=timezone.now(),
    )
    entry.removed_at = timezone.now()
    entry.save()
    FakeResendBackend.sent_messages.clear()

    response = client.get(f"/retrait/confirme/{rreq.confirm_token}/")
    assert response.status_code == 200
    # No second-execution side effects: no new email
    assert len(FakeResendBackend.sent_messages) == 0


@pytest.mark.django_db
def test_confirm_expired_marks_status_and_renders_expired_page(client, entry, settings):
    from datetime import timedelta
    from django.utils import timezone

    from members.models import RemovalRequest

    rreq = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    # Backdate so expires_at is in the past
    rreq.expires_at = timezone.now() - timedelta(days=1)
    rreq.save()

    response = client.get(f"/retrait/confirme/{rreq.confirm_token}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "expir" in body.lower()

    rreq.refresh_from_db()
    assert rreq.status == "expired"
    entry.refresh_from_db()
    assert entry.removed_at is None  # not removed


@pytest.mark.django_db
def test_confirm_unknown_token_renders_expired_page(client):
    response = client.get("/retrait/confirme/this-token-does-not-exist/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "expir" in body.lower() or "invalide" in body.lower()


@pytest.mark.django_db
def test_entry_not_in_public_queryset_after_confirm(client, entry, settings, db):
    """Once removed, the entry must disappear from the public ghost queryset."""
    from django.contrib.auth import get_user_model
    from django.db.models import Count

    from members.models import PublicSearchEntry, RemovalRequest

    User = get_user_model()  # noqa: N806
    e = entry
    a, b = (
        User.objects.create_user(
            username=f"a{i}", email=f"a{i}@x.test", password="x", is_staff=True
        )
        for i in range(2)
    )
    e.added_by_admins.add(a, b)

    # Verify visible before removal
    qs = PublicSearchEntry.objects.filter(removed_at__isnull=True).annotate(
        n=Count("added_by_admins")
    ).filter(n__gte=2)
    assert e in qs

    rreq = RemovalRequest.objects.create(entry=e, requester_email="x@y.test")
    client.get(f"/retrait/confirme/{rreq.confirm_token}/")

    # Verify gone after removal
    qs = PublicSearchEntry.objects.filter(removed_at__isnull=True).annotate(
        n=Count("added_by_admins")
    ).filter(n__gte=2)
    assert e not in qs


@pytest.mark.django_db
def test_form_post_rate_limited_after_5_per_hour(client, entry, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.RATELIMIT_ENABLE = True
    from django.core.cache import cache

    cache.clear()
    for i in range(5):
        client.post(
            f"/retrait/{entry.removal_token}/",
            {"email": f"r{i}@x.test"},
        )
    response = client.post(
        f"/retrait/{entry.removal_token}/",
        {"email": "r6@x.test"},
    )
    assert response.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_removal_views.py -v 2>&1 | tail -15`

Expected: confirm-view tests fail (NoReverseMatch / 404).

- [ ] **Step 3: Add `removal_confirm_view` and `removal_expired_view` to `members/views.py`**

Append:

```python
@require_http_methods(["GET"])
def removal_confirm_view(request, confirm_token: str):
    from .models import AuditLog, RemovalRequest

    try:
        rreq = RemovalRequest.objects.select_related("entry").get(confirm_token=confirm_token)
    except RemovalRequest.DoesNotExist:
        return render(request, "members/removal_expired_or_invalid.html", status=200)

    now = timezone.now()

    if rreq.status == "expired":
        return render(request, "members/removal_expired_or_invalid.html", status=200)

    if rreq.status == "confirmed":
        # Idempotent: clicking again shows success without re-running side effects
        return render(
            request,
            "members/removal_confirmed.html",
            {"entry": rreq.entry, "request": rreq},
        )

    # status == "pending_confirmation"
    if rreq.expires_at <= now:
        rreq.status = "expired"
        rreq.save(update_fields=["status"])
        return render(request, "members/removal_expired_or_invalid.html", status=200)

    # Execute the removal — set entry.removed_at, write 2 AuditLog entries,
    # send 2 emails, mark request as confirmed.
    entry = rreq.entry
    entry.removed_at = now
    entry.removed_reason = (
        rreq.reason or "Retrait demandé par la personne concernée"
    )[:200]
    entry.save(update_fields=["removed_at", "removed_reason"])

    rreq.status = "confirmed"
    rreq.confirmed_at = now
    rreq.save(update_fields=["status", "confirmed_at"])

    AuditLog.objects.create(
        actor=None,
        action="ghost.removal.confirmed",
        target_type="members.RemovalRequest",
        target_id=str(rreq.pk),
        metadata={"requester_email": rreq.requester_email},
    )
    AuditLog.objects.create(
        actor=None,
        action="ghost.removal.executed",
        target_type="members.PublicSearchEntry",
        target_id=str(entry.pk),
        metadata={
            "removal_request_id": rreq.pk,
            "reason_at_request": rreq.reason,
        },
    )

    members_emails.send_removal_completed(rreq)
    members_emails.send_admin_removal_notification(rreq)

    return render(
        request,
        "members/removal_confirmed.html",
        {"entry": entry, "request": rreq},
    )


@require_http_methods(["GET"])
def removal_expired_view(request):
    return render(request, "members/removal_expired_or_invalid.html")
```

- [ ] **Step 4: Wire the URLs**

In `members/urls.py`, ensure the order (literal paths before the token pattern):

```python
    path(
        "retrait/merci/",
        views.removal_request_done_view,
        name="removal_request_done",
    ),
    path(
        "retrait/expire/",
        views.removal_expired_view,
        name="removal_expired",
    ),
    path(
        "retrait/confirme/<str:confirm_token>/",
        views.removal_confirm_view,
        name="removal_confirm",
    ),
    path(
        "retrait/<str:entry_token>/",
        views.removal_request_form_view,
        name="removal_request_form",
    ),
```

- [ ] **Step 5: Create `members/templates/members/removal_confirmed.html`**

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Retrait confirmé" %}{% endblock %}
{% block content %}
    <section class="mx-auto max-w-2xl px-4 py-16 text-center">
        <span class="inline-flex h-14 w-14 items-center justify-center rounded-full bg-whatsapp-green/15 text-whatsapp-green text-3xl">✓</span>
        <h1 class="mt-6 font-display text-3xl font-semibold tracking-tight md:text-4xl">
            {% trans "Retrait confirmé" %}
        </h1>
        <p class="mx-auto mt-4 max-w-md text-lg text-secondary">
            {% blocktrans with name=entry.first_name initial=entry.last_name_initial %}Le nom <strong>{{ name }} {{ initial }}</strong> a été retiré de la liste publique.{% endblocktrans %}
        </p>
        <p class="mx-auto mt-3 max-w-md text-sm text-secondary">
            {% trans "Si c'était une erreur, contactez l'équipe en répondant à l'email de confirmation." %}
        </p>
        <a href="/"
           class="mt-8 inline-flex items-center gap-2 rounded-lg border border-secondary/25 bg-surface px-5 py-3 text-base font-medium hover:border-tertiary/40 hover:text-tertiary transition">
            {% trans "Retour à l'accueil" %}
            <span aria-hidden="true">→</span>
        </a>
    </section>
{% endblock %}
```

- [ ] **Step 6: Create `members/templates/members/removal_expired_or_invalid.html`**

```django
{% extends "base.html" %}
{% load i18n %}
{% block title %}{% trans "Lien expiré" %}{% endblock %}
{% block content %}
    <section class="mx-auto max-w-2xl px-4 py-16 text-center">
        <span class="inline-flex h-14 w-14 items-center justify-center rounded-full bg-ceremonial-gold/15 text-ceremonial-gold text-3xl">⚠</span>
        <h1 class="mt-6 font-display text-3xl font-semibold tracking-tight md:text-4xl">
            {% trans "Lien expiré ou invalide" %}
        </h1>
        <p class="mx-auto mt-4 max-w-md text-lg text-secondary">
            {% trans "Le lien que vous avez suivi a expiré ou n'est pas reconnu. Vous pouvez recommencer la procédure depuis la page d'accueil." %}
        </p>
        <a href="/"
           class="mt-8 inline-flex items-center gap-2 rounded-lg bg-tertiary px-6 py-3 text-base font-medium text-on-tertiary shadow-sm hover:opacity-95 transition">
            {% trans "Retour à l'accueil" %}
            <span aria-hidden="true">→</span>
        </a>
    </section>
{% endblock %}
```

- [ ] **Step 7: Run all view tests**

Run: `.venv/Scripts/python.exe -m pytest members/tests/test_removal_views.py -v 2>&1 | tail -25`

Expected: 13 passed (6 from Task 6 + 7 new).

- [ ] **Step 8: Commit**

```bash
git add members/views.py members/urls.py members/templates/members/ members/tests/test_removal_views.py
git commit -m "feat(p4b): removal confirmation view (idempotent auto-execute) + expired page"
```

---

## Task 8: Admin registrations for AuditLog + RemovalRequest

**Files:**
- Modify: `members/admin.py`

- [ ] **Step 1: Append admin registrations to `members/admin.py`**

Find the existing `from .models import` line and extend it:

```python
from .models import (
    AuditLog,
    ConsentRecord,
    Member,
    NotificationPreference,
    PublicSearchEntry,
    RemovalRequest,
)
```

Append at the bottom of `members/admin.py`:

```python
@admin.register(RemovalRequest)
class RemovalRequestAdmin(admin.ModelAdmin):
    """Public removal requests. Read-only on body fields; deletion of a
    pending request fires the ghost.removal.cancelled audit hook."""

    list_display = (
        "entry",
        "requester_email",
        "status",
        "requested_at",
        "expires_at",
    )
    list_filter = ("status",)
    search_fields = ("requester_email", "entry__first_name", "entry__last_name_initial")
    readonly_fields = (
        "entry",
        "requester_email",
        "reason",
        "confirm_token",
        "requester_ip",
        "requested_at",
        "confirmed_at",
        "expires_at",
    )

    def has_add_permission(self, request):
        return False  # always created by the public flow


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Append-only governance log. No add/change/delete from admin."""

    list_display = (
        "created_at",
        "actor",
        "action",
        "target_type",
        "target_id",
    )
    list_filter = ("action", "target_type")
    search_fields = ("action", "target_type", "target_id")
    readonly_fields = (
        "actor",
        "action",
        "target_type",
        "target_id",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 2: Add admin tests to `members/tests/test_audit_log.py`**

Append:

```python
@pytest.mark.django_db
def test_audit_log_admin_is_append_only():
    """AuditLogAdmin disables add/change/delete in all paths."""
    from django.contrib import admin

    from members.models import AuditLog

    cls = admin.site._registry[AuditLog].__class__
    a = cls(AuditLog, admin.site)
    assert a.has_add_permission(None) is False
    assert a.has_change_permission(None) is False
    assert a.has_delete_permission(None) is False
```

- [ ] **Step 3: Run admin + audit tests**

```powershell
.venv/Scripts/python.exe manage.py check 2>&1 | tail -3
```

Expected: no new issues.

```powershell
.venv/Scripts/python.exe -m pytest members/tests/test_audit_log.py -v 2>&1 | tail -10
```

Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add members/admin.py members/tests/test_audit_log.py
git commit -m "feat(p4b): RemovalRequestAdmin + AuditLogAdmin (append-only)"
```

---

## Task 9: Landing template — "Retirer mon nom" link in each ghost card

**Files:**
- Modify: `templates/core/landing.html`
- Modify: `core/tests/test_landing_view.py` (append 2 tests)
- Modify: `core/tests/test_a11y.py` (append 1 test)

- [ ] **Step 1: Add the failing tests**

Append to `core/tests/test_landing_view.py`:

```python
@pytest.mark.django_db
def test_ghost_card_includes_removal_link_when_flag_on(client, settings, make_admin):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    e.added_by_admins.add(make_admin(), make_admin())

    body = client.get("/").content.decode("utf-8")
    assert "Retirer mon nom" in body
    assert f"/retrait/{e.removal_token}/" in body


@pytest.mark.django_db
def test_no_removal_link_when_flag_off(client, settings):
    settings.PUBLIC_GHOST_LIST_ENABLED = False
    body = client.get("/").content.decode("utf-8")
    assert "Retirer mon nom" not in body
```

Append to `core/tests/test_a11y.py`:

```python
@pytest.mark.django_db
def test_removal_link_has_accessible_text_when_flag_on(client, settings, db):
    """The 'Retirer mon nom' link must have visible text (not just an icon)."""
    from django.contrib.auth import get_user_model
    from members.models import PublicSearchEntry

    settings.PUBLIC_GHOST_LIST_ENABLED = True
    User = get_user_model()  # noqa: N806
    a, b = (
        User.objects.create_user(
            username=f"a{i}", email=f"a{i}@x.test", password="x", is_staff=True
        )
        for i in range(2)
    )
    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(a, b)

    body = client.get("/").content
    soup = BeautifulSoup(body, "html.parser")
    removal_links = [
        a for a in soup.find_all("a") if "/retrait/" in (a.get("href") or "")
    ]
    assert removal_links, "Expected at least one removal link in the rendered ghost card"
    for link in removal_links:
        text = link.get_text(strip=True)
        assert text, f"Removal link {link} has no visible text"
        assert text == "Retirer mon nom"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_landing_view.py core/tests/test_a11y.py -k "removal" -v 2>&1 | tail -10`

Expected: failures (template doesn't have the link yet).

- [ ] **Step 3: Add the link in `templates/core/landing.html`**

Find the ghost card `<article>` block (inside the `{% for entry in ghosts %}` loop) and add a paragraph with the removal link inside it. The current article ends with the italic CTA paragraph; add the new link below it:

```django
                        <article class="rounded-2xl border border-secondary/15 bg-surface/70 p-5 shadow-sm">
                            <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                                <strong class="font-display text-lg">{{ entry.first_name }} {{ entry.last_name_initial }}</strong>
                                <span class="text-sm text-secondary">{% trans "au CEG" %} {{ entry.first_year }}-{{ entry.last_year }}</span>
                            </div>
                            {% if entry.note %}<p class="mt-1 text-sm text-secondary">{{ entry.note }}</p>{% endif %}
                            <p class="mt-2 text-sm italic text-secondary">
                                {% trans "Vous le reconnaissez ? Partagez cette page avec votre entourage." %}
                            </p>
                            <p class="mt-2 text-xs text-secondary">
                                <a href="{% url 'members:removal_request_form' entry.removal_token %}"
                                   class="underline hover:text-tertiary">
                                    {% trans "Retirer mon nom" %}
                                </a>
                            </p>
                        </article>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest core/tests/test_landing_view.py core/tests/test_a11y.py -v 2>&1 | tail -15`

Expected: all pass (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add templates/core/landing.html core/tests/test_landing_view.py core/tests/test_a11y.py
git commit -m "feat(p4b): add 'Retirer mon nom' link in each ghost card"
```

---

## Task 10: Full suite + STATUS update

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest 2>&1 | tail -3`

Expected: ~310 passed (was 286 + ~24 new across the 5 new test files).

- [ ] **Step 2: Manual local smoke**

Run the dev server:
```powershell
& .\.venv\Scripts\python.exe manage.py runserver
```

In a browser:
- Django admin → Members → PublicSearchEntries → create one with 2 cosigners
- Visit `http://localhost:8000/retrait/<that-entry's-token>/` (you can copy the token from the admin's change-form readonly field)
- Submit the form with your real email
- Should land on `/retrait/merci/` (with refresh-resistant URL)
- (Console-backend prints the email; in dev no real send happens)

- [ ] **Step 3: Update STATUS.md**

Open `docs/superpowers/STATUS.md`. In the Phase Index, find the P4b row:

```markdown
| P4b | Public surface — admin governance UI + token-based removal flow + AuditLog | Not started | — |
```

Replace with:

```markdown
| P4b | Public surface — token-based removal flow + AuditLog (governance UI deferred to P4c) | Complete (tag `v0.4.0b-public-surface-governance`, 2026-MM-DD) | [plan](plans/2026-05-03-public-surface-governance.md) |
```

(Also add a new "P4c" row below P4b with "Not started" for the deferred custom UI + quarterly review.)

Append a new P4b section at the bottom of the file (mirror the format of P4a's section):

```markdown
## P4b — Public surface (token-based removal flow + AuditLog)

**Shipped:** 2026-MM-DD (branch `feat/public-surface-governance`, tag `v0.4.0b-public-surface-governance`)
**Plan:** [plans/2026-05-03-public-surface-governance.md](plans/2026-05-03-public-surface-governance.md)
**Spec:** [specs/2026-05-03-public-surface-governance-design.md](specs/2026-05-03-public-surface-governance-design.md)
**Test suite:** ~310 passing (286 from prior + ~24 new across audit log, removal request, signals, view, email, landing template tests).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Whitelist /retrait/ for login + basic-auth bypass | [x] | _SHA_ |
| 2 | AuditLog model + migration + tests | [x] | _SHA_ |
| 3 | RemovalRequest model + tighten removal_token + tests | [x] | _SHA_ |
| 4 | Audit signal handlers (entry create, signoff M2M, request cancel) | [x] | _SHA_ |
| 5 | 3 removal-flow email templates + senders | [x] | _SHA_ |
| 6 | Public removal request form view + done page | [x] | _SHA_ |
| 7 | Removal confirmation view (idempotent auto-execute) + expired page | [x] | _SHA_ |
| 8 | RemovalRequestAdmin + AuditLogAdmin (append-only) | [x] | _SHA_ |
| 9 | Landing template "Retirer mon nom" link in each ghost card | [x] | _SHA_ |
| 10 | Full suite + smoke + STATUS update | [x] | _this commit_ |
| 11 | Merge, tag, push, deploy | _next commit_ | _pending_ |

**Notable design decisions:**
- "sans débat" interpretation: auto-execute on email confirmation. No admin gatekeeping.
- 30-day expiry on RemovalRequest aligns with GDPR Art. 12's one-month response window.
- AuditLog populated automatically via Django signals so adding a new way to sign off / remove an entry doesn't require remembering to write to AuditLog.
- P3 cooptation actions are NOT retrofitted into AuditLog — domain audit fields stay where they are.
- Custom admin governance UI and quarterly review automation deferred to P4c.
```

- [ ] **Step 4: Commit STATUS update**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(p4b): mark Public Surface governance complete in STATUS"
```

---

## Task 11: Merge, tag, push, deploy

**Files:** none

- [ ] **Step 1: Merge to main locally**

```bash
git checkout main
git pull --ff-only
git merge --no-ff feat/public-surface-governance -m "Merge branch 'feat/public-surface-governance' into main

P4b Public Surface Governance — token-based removal flow + AuditLog.

Unblocks the PUBLIC_GHOST_LIST_ENABLED=True flag flip by shipping a
public friction-free 'Retirer mon nom' removal flow with 30-day email
confirmation token, and an append-only AuditLog model that records
every governance action on the ghost list.

Auto-execute on email confirmation per spec's 'sans débat' reading —
no admin gatekeeping; the email confirmation IS the gate.

Custom admin governance UI and quarterly-review automation deferred
to P4c.

~310 tests passing (was 286; ~24 new).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2: Run full suite on merged main**

Run: `.venv/Scripts/python.exe -m pytest 2>&1 | tail -3`

Expected: same ~310 pass count.

- [ ] **Step 3: Tag and push**

```bash
git tag -a v0.4.0b-public-surface-governance -m "P4b Public Surface — removal flow + AuditLog"
git push origin main --follow-tags
git branch -d feat/public-surface-governance
```

- [ ] **Step 4: Verify Railway redeploys cleanly**

Watch Railway dashboard. Build should be green within ~3 minutes. Check Deployments tab.

- [ ] **Step 5: Post-deploy smoke (10 min)**

In a browser (with basic-auth credentials so we get past the staging gate, even though `/retrait/` bypasses it — habit):

1. **Create a test entry:** Django admin → Members → PublicSearchEntries → Add. Fill `first_name="Test"`, `last_name_initial="Z."`, `years_at_ceg=[1980]`. Save.
2. **Cosign:** edit the just-created entry. In `Cosignature` fieldset, add yourself + 1 other admin to `added_by_admins`. Save. Note the auto-generated `removal_token`.
3. **Visit the form:** open `https://villageretrouvailles.com/retrait/<that-token>/` in incognito (no auth — this should work without basic-auth thanks to the bypass). Form renders with entry preview.
4. **Submit:** enter your real email, optional reason. Land on `/retrait/merci/`.
5. **Check inbox:** receive `removal_confirmation_pending` email with a confirmation link.
6. **Click the link:** lands on `/retrait/confirme/<token>/`. Page shows "Retrait confirmé". Entry is now removed.
7. **Verify auto-execution:** Django admin → PublicSearchEntries → the test entry now has `removed_at` set.
8. **Verify the 2 emails:** your inbox got `removal_completed`; staff inboxes got `admin_removal_notification`.
9. **Verify AuditLog:** Django admin → Audit logs → at least 5 entries for this test (entry.created, signed_off ×2, removal.requested, removal.confirmed, removal.executed).
10. **Idempotency:** click the same email confirmation link again → still shows "Retrait confirmé", no duplicate emails sent, no new AuditLog entries beyond the original 5.

- [ ] **Step 6: Flip the feature flag**

In Railway → app service → Variables tab:
- Add (or edit) variable `PUBLIC_GHOST_LIST_ENABLED` → set to `true`
- Save → Railway redeploys
- After redeploy, visit `https://villageretrouvailles.com/` in incognito → the "Nous recherchons aussi…" section should now render (likely with the empty-state copy "Liste en cours de constitution — bientôt", since the test entry was removed in step 6 of smoke)

- [ ] **Step 7: (Optional) Add a real ghost entry**

Ask one or two trusted admins to add a real ghost entry via Django admin and add themselves + you as cosigners. Verify the entry now appears publicly with its "Retirer mon nom" link.

---

## Done

P4b Public Surface Governance is shipped. The public ghost list is now RGPD-complete: every published name has a self-service removal path, every governance action is in the audit log, and the feature flag is on.

Next phase per `docs/superpowers/STATUS.md`: P4c — custom admin governance UI (approval queue, signoff status indicators) + quarterly-review automation (12-month auto-removal sweep).
