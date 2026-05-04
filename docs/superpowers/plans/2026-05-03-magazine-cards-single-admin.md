# P4d — Magazine Cards + Single-Admin Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign public ghost cards with magazine warmth (monogram + gold accent), drop the 2-signoff publication gate so a single admin's add publishes immediately, and email all other admins on creation.

**Architecture:** Three coupled changes to the existing ghost-list system: (1) view + visibility query change, (2) template redesign, (3) admin `save_model` hook for auto-cosign + email trigger. Plus filter simplification and a new email family (3 templates + sender). No DB migration. No model schema change.

**Tech Stack:** Django 5.0, PostgreSQL, pytest-django, Tailwind/DaisyUI utility classes (existing ceremonial-gold + secondary tokens only), Resend email (FakeResendBackend in tests).

**Spec:** `docs/superpowers/specs/2026-05-03-magazine-cards-single-admin-design.md`

---

## File Structure

**Create:**
- `members/templates/emails/members/admin_ghost_added.subject.txt` — one-line subject template.
- `members/templates/emails/members/admin_ghost_added.html` — HTML email body, mirrors `admin_removal_notification.html` style.
- `members/templates/emails/members/admin_ghost_added.txt` — plain-text email body.
- `members/tests/test_admin_publicsearchentry.py` — admin `save_model` behavior tests (auto-add creator on create, no re-add on edit).
- `members/tests/test_emails_ghost_added.py` — email send + recipients + content tests.

**Modify:**
- `core/views.py` — change `n__gte=2` to `n__gte=1` in `landing_view`.
- `core/tests/test_landing_view.py` — delete `test_ghost_section_hides_single_admin_entries`, replace with `test_single_signoff_entry_is_visible_on_landing`, add 2 new card-markup tests.
- `templates/core/landing.html` — replace ghost-card markup block with magazine layout (monogram + accent bar + warmer chrome).
- `members/admin.py` — add `save_model` to `PublicSearchEntryAdmin`, rewrite "Cosignature" fieldset header + description, simplify `GhostStatusFilter` to 3 buckets.
- `members/emails.py` — add `send_admin_ghost_added(entry, *, added_by)`.
- `members/tests/test_admin_filters.py` — update `test_ghost_status_filter_buckets` for new 3-bucket reality (drop draft/pending cases, adjust published/stale to require `n>=1`).
- `docs/superpowers/STATUS.md` — add P4d row + section.

---

## Task Order Rationale

1. **Task 1 (view gate change)** — smallest, isolated, immediately changes user-visible behavior on production data with 1+ signoffs. Replaces 1 test.
2. **Task 2 (card template + tests)** — pure template work, independent of governance changes.
3. **Task 3 (email infrastructure)** — templates + sender + tests, NOT yet wired to anything. Self-contained.
4. **Task 4 (admin save_model integration)** — auto-add creator + fire Task 3's sender + form copy update. Depends on Task 3's sender existing.
5. **Task 5 (GhostStatusFilter cleanup)** — independent UI cleanup; can ship anytime after Task 1.
6. **Task 6 (STATUS.md update)** — housekeeping.

---

## Task 1: Drop the 2-signoff visibility gate

**Files:**
- Modify: `core/views.py`
- Modify: `core/tests/test_landing_view.py`

- [ ] **Step 1: Add the new failing test that asserts single-signoff visibility**

Open `core/tests/test_landing_view.py`. Locate the existing `test_ghost_section_hides_single_admin_entries` test and ADD a new test directly above or below it:

```python
@pytest.mark.django_db
def test_single_signoff_entry_is_visible_on_landing(client, settings, make_admin):
    """P4d: a single admin's add immediately publishes the entry. Replaces
    the prior 2-signoff gate from P4a."""
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="SoloSignoff", last_name_initial="X.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin())  # Only one admin

    body = client.get("/").content.decode("utf-8")
    assert "SoloSignoff" in body
```

- [ ] **Step 2: Run the test — expect FAIL**

Run: `pytest core/tests/test_landing_view.py::test_single_signoff_entry_is_visible_on_landing -v`

Expected: FAIL — `assert "SoloSignoff" in body` fails because the current view filter requires 2+ signoffs.

- [ ] **Step 3: Change the view filter from `n__gte=2` to `n__gte=1`**

Edit `core/views.py:landing_view`. Locate the ghost query (around lines 44-50):

```python
    ghosts = []
    if not request.user.is_authenticated and django_settings.PUBLIC_GHOST_LIST_ENABLED:
        ghosts = list(
            PublicSearchEntry.objects.filter(removed_at__isnull=True)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=2)
        )
```

Change `n__gte=2` to `n__gte=1`:

```python
    ghosts = []
    if not request.user.is_authenticated and django_settings.PUBLIC_GHOST_LIST_ENABLED:
        ghosts = list(
            PublicSearchEntry.objects.filter(removed_at__isnull=True)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=1)
        )
```

(The `annotate` + `filter(n__gte=1)` is preserved as a defensive guard against zero-signoff edge cases — see spec Section B.)

- [ ] **Step 4: Run the new test — expect PASS**

Run: `pytest core/tests/test_landing_view.py::test_single_signoff_entry_is_visible_on_landing -v`

Expected: PASS.

- [ ] **Step 5: Delete the now-inverted test `test_ghost_section_hides_single_admin_entries`**

In `core/tests/test_landing_view.py`, locate and DELETE this entire test:

```python
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
```

(This test asserted the now-removed behavior. Its replacement was added in Step 1.)

- [ ] **Step 6: Run the full landing test file — expect green (one fewer test)**

Run: `pytest core/tests/test_landing_view.py -v`

Expected: ALL PASS. Test count decreased by 1 (the deleted test) and increased by 1 (the new test) → net unchanged.

- [ ] **Step 7: Commit**

```bash
git add core/views.py core/tests/test_landing_view.py
git commit -m "feat(p4d): drop 2-signoff publication gate (single admin publishes)"
```

---

## Task 2: Magazine card redesign

**Files:**
- Modify: `templates/core/landing.html`
- Modify: `core/tests/test_landing_view.py`

- [ ] **Step 1: Add 2 failing tests for the new card markup**

In `core/tests/test_landing_view.py`, ADD these two new tests:

```python
@pytest.mark.django_db
def test_ghost_card_includes_monogram_initials(client, settings, make_admin):
    """P4d: each magazine card shows a monogram circle with the entry's
    initials (first letter of first_name + first letter of last_name_initial)."""
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    e.added_by_admins.add(make_admin())

    body = client.get("/").content.decode("utf-8")
    # Monogram disc has the warm-tinted background and contains "IS" as text.
    assert "bg-ceremonial-gold/20" in body
    assert ">IS<" in body


@pytest.mark.django_db
def test_ghost_card_uses_gold_accent_bar(client, settings, make_admin):
    """P4d: each card has a 4px left gold accent bar — the magazine chrome."""
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Hamidou", last_name_initial="A.", years_at_ceg=[1981, 1982]
    )
    e.added_by_admins.add(make_admin())

    body = client.get("/").content.decode("utf-8")
    # Tailwind 3+ syntax: border-l-{N} sets left-border width, border-l-{color}
    # sets left-border color specifically (vs border-{color} for all sides).
    assert "border-l-4" in body
    assert "border-l-ceremonial-gold" in body
```

- [ ] **Step 2: Run the tests — expect FAIL**

Run: `pytest core/tests/test_landing_view.py::test_ghost_card_includes_monogram_initials core/tests/test_landing_view.py::test_ghost_card_uses_gold_accent_bar -v`

Expected: 2 FAIL — the new markup hasn't been written yet.

- [ ] **Step 3: Replace the ghost-card markup in `templates/core/landing.html`**

Open `templates/core/landing.html`. Locate the ghost-card `{% for entry in ghosts %}` loop (around lines 106-122):

```html
            <div class="mt-10 space-y-4">
                {% for entry in ghosts %}
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
                               class="underline hover:text-tertiary">{% trans "Retirer mon nom" %}</a>
                        </p>
                    </article>
                {% endfor %}
            </div>
```

REPLACE with the magazine layout:

```html
            <div class="mt-10 space-y-4">
                {% for entry in ghosts %}
                    {% with initials=entry.first_name|slice:":1"|add:entry.last_name_initial|slice:":1" %}
                        <article class="overflow-hidden rounded-xl border border-secondary/15 border-l-4 border-l-ceremonial-gold bg-ceremonial-gold/5 p-6">
                            <div class="flex flex-col gap-4 md:flex-row md:items-start">
                                <div class="flex-shrink-0 mx-auto md:mx-0">
                                    <div class="flex h-12 w-12 items-center justify-center rounded-full bg-ceremonial-gold/20 font-display text-base font-semibold text-primary">
                                        {{ initials }}
                                    </div>
                                </div>
                                <div class="flex-1 min-w-0">
                                    <p class="font-display text-lg font-semibold text-primary">{{ entry.first_name }} {{ entry.last_name_initial }}</p>
                                    <p class="mt-0.5 text-sm text-secondary">{% trans "au CEG" %} {{ entry.first_year }}-{{ entry.last_year }}</p>
                                    {% if entry.note %}<p class="mt-1 text-sm italic text-secondary">{{ entry.note }}</p>{% endif %}
                                    <p class="mt-3 text-sm italic text-secondary">
                                        {% trans "Si vous le connaissez, partagez ce lien." %}
                                    </p>
                                    <p class="mt-3 text-xs text-secondary md:text-right">
                                        <a href="{% url 'members:removal_request_form' entry.removal_token %}"
                                           class="underline hover:text-tertiary">{% trans "Retirer mon nom" %}</a>
                                    </p>
                                </div>
                            </div>
                        </article>
                    {% endwith %}
                {% endfor %}
            </div>
```

Key Tailwind classes used (all from existing alumni theme — no new tokens):
- `border-l-4 border-l-ceremonial-gold` — gold accent bar on left edge
- `bg-ceremonial-gold/5` — very subtle warm tint card background
- `bg-ceremonial-gold/20` — warmer monogram disc background
- `rounded-xl` — slightly less round than current `rounded-2xl`, more editorial
- `p-6` — generous padding
- No `shadow-sm` — flat-elegant rather than card-stacked
- `flex-col gap-4 md:flex-row md:items-start` — avatar above on mobile, beside on desktop
- Initials computed via `{% with initials=entry.first_name|slice:":1"|add:entry.last_name_initial|slice:":1" %}` — no model change

- [ ] **Step 4: Run the new tests — expect PASS**

Run: `pytest core/tests/test_landing_view.py::test_ghost_card_includes_monogram_initials core/tests/test_landing_view.py::test_ghost_card_uses_gold_accent_bar -v`

Expected: 2 PASS.

- [ ] **Step 5: Run the full landing test file — confirm no regressions**

Run: `pytest core/tests/test_landing_view.py -v`

Expected: ALL PASS. Other tests still work because the test assertions check for entry name/years/"Retirer mon nom"/"Vivait à Maradi" — all of which are still rendered in the new markup.

- [ ] **Step 6: Commit**

```bash
git add templates/core/landing.html core/tests/test_landing_view.py
git commit -m "feat(p4d): magazine ghost cards with monogram + gold accent"
```

---

## Task 3: Notification email infrastructure

**Files:**
- Create: `members/templates/emails/members/admin_ghost_added.subject.txt`
- Create: `members/templates/emails/members/admin_ghost_added.html`
- Create: `members/templates/emails/members/admin_ghost_added.txt`
- Create: `members/tests/test_emails_ghost_added.py`
- Modify: `members/emails.py`

The sender exists but isn't wired into save_model yet — Task 4 does that.

- [ ] **Step 1: Write the failing tests**

Create `members/tests/test_emails_ghost_added.py`:

```python
"""Tests for the admin_ghost_added FYI email (P4d)."""

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
def test_notification_sent_to_other_staff_on_entry_create(fake_backend, make_admin):
    from members.emails import send_admin_ghost_added
    from members.models import PublicSearchEntry

    creator = make_admin()
    other_admin = make_admin()

    entry = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    send_admin_ghost_added(entry, added_by=creator)

    assert len(fake_backend.sent_messages) == 1
    msg = fake_backend.sent_messages[0]
    assert other_admin.email in msg["to"]
    assert "Idrissa" in msg["subject"]
    assert "Idrissa" in msg["text"]
    assert "S." in msg["text"]


@pytest.mark.django_db
def test_notification_excludes_creator_from_recipients(fake_backend, make_admin):
    from members.emails import send_admin_ghost_added
    from members.models import PublicSearchEntry

    creator = make_admin()
    other_admin = make_admin()

    entry = PublicSearchEntry.objects.create(
        first_name="Hamidou", last_name_initial="A.", years_at_ceg=[1981, 1982]
    )
    send_admin_ghost_added(entry, added_by=creator)

    msg = fake_backend.sent_messages[0]
    assert creator.email not in msg["to"]
    assert other_admin.email in msg["to"]


@pytest.mark.django_db
def test_notification_no_op_when_no_other_staff(fake_backend, make_admin):
    """If the creator is the only staff user, send no email (and no error)."""
    from members.emails import send_admin_ghost_added
    from members.models import PublicSearchEntry

    creator = make_admin()  # Only staff user

    entry = PublicSearchEntry.objects.create(
        first_name="Solo", last_name_initial="X.", years_at_ceg=[1980]
    )
    send_admin_ghost_added(entry, added_by=creator)

    assert len(fake_backend.sent_messages) == 0
```

- [ ] **Step 2: Run the tests — expect FAIL**

Run: `pytest members/tests/test_emails_ghost_added.py -v`

Expected: 3 FAIL — `send_admin_ghost_added` doesn't exist yet, and the templates don't exist either.

- [ ] **Step 3: Create the subject template**

Create `members/templates/emails/members/admin_ghost_added.subject.txt`:

```
Nouvelle fiche fantôme : {{ entry.first_name }} {{ entry.last_name_initial }}
```

- [ ] **Step 4: Create the plain-text body template**

Create `members/templates/emails/members/admin_ghost_added.txt`:

```
Bonjour,

{{ added_by.get_full_name|default:added_by.username }} vient d'ajouter une fiche à la liste des anciens recherchés.

Nom : {{ entry.first_name }} {{ entry.last_name_initial }}
Années au CEG : {{ entry.first_year }}-{{ entry.last_year }}{% if entry.note %}
Note : {{ entry.note }}{% endif %}
Ajoutée le : {{ entry.added_at|date:"d M Y à H:i" }}

Si cette fiche ne vous semble pas pertinente, vous pouvez la retirer immédiatement via l'admin :
{{ site_url }}/admin/members/publicsearchentry/{{ entry.pk }}/change/

Liste complète : {{ site_url }}/admin/members/publicsearchentry/
Page publique : {{ site_url }}/

L'équipe Les Retrouvailles
```

- [ ] **Step 5: Create the HTML body template**

Create `members/templates/emails/members/admin_ghost_added.html`:

```html
<!DOCTYPE html>
<html lang="fr">
    <body style="font-family: Inter, system-ui, sans-serif; color: #1a1c1e">
        <p>Bonjour,</p>
        <p>
            <strong>{{ added_by.get_full_name|default:added_by.username }}</strong>
            vient d'ajouter une fiche à la liste des anciens recherchés.
        </p>
        <table style="border-collapse: collapse; margin: 12px 0">
            <tr>
                <td style="padding: 4px 12px 4px 0; color: #6c7278">Nom</td>
                <td>
                    <strong>{{ entry.first_name }} {{ entry.last_name_initial }}</strong>
                </td>
            </tr>
            <tr>
                <td style="padding: 4px 12px 4px 0; color: #6c7278">Années au CEG</td>
                <td>{{ entry.first_year }}-{{ entry.last_year }}</td>
            </tr>
            {% if entry.note %}
                <tr>
                    <td style="padding: 4px 12px 4px 0; color: #6c7278">Note</td>
                    <td>{{ entry.note }}</td>
                </tr>
            {% endif %}
            <tr>
                <td style="padding: 4px 12px 4px 0; color: #6c7278">Ajoutée le</td>
                <td>{{ entry.added_at|date:"d M Y à H:i" }}</td>
            </tr>
        </table>
        <p>
            Si cette fiche ne vous semble pas pertinente, vous pouvez la
            <a href="{{ site_url }}/admin/members/publicsearchentry/{{ entry.pk }}/change/">
                retirer immédiatement via l'admin</a>.
        </p>
        <p style="color: #6c7278; font-size: 12px">
            <a href="{{ site_url }}/admin/members/publicsearchentry/" style="color: #6c7278">Liste complète</a>
            ·
            <a href="{{ site_url }}/" style="color: #6c7278">Page publique</a>
        </p>
        <p>L'équipe Les Retrouvailles</p>
    </body>
</html>
```

- [ ] **Step 6: Add the sender function to `members/emails.py`**

Open `members/emails.py`. Append this function at the end of the file (after `send_admin_quarterly_ghost_digest`):

```python
def send_admin_ghost_added(entry, *, added_by) -> None:
    """FYI to all other active staff when a new ghost entry is created.
    Excludes the creator (they already know they just added it). Replaces
    the 2-signoff pre-publication safety with a post-publication tripwire
    (P4d spec §C). Mirrors send_admin_removal_notification's no-op when
    no recipients exist."""
    User = get_user_model()  # noqa: N806
    recipients = list(
        User.objects.filter(is_staff=True, is_active=True)
        .exclude(pk=added_by.pk)
        .values_list("email", flat=True)
    )
    recipients = [e for e in recipients if e]
    if not recipients:
        return
    send_email(
        recipients,
        "members/admin_ghost_added",
        {"entry": entry, "added_by": added_by},
    )
```

- [ ] **Step 7: Run the tests — expect PASS**

Run: `pytest members/tests/test_emails_ghost_added.py -v`

Expected: 3 PASS.

- [ ] **Step 8: Commit**

```bash
git add members/templates/emails/members/admin_ghost_added.subject.txt members/templates/emails/members/admin_ghost_added.html members/templates/emails/members/admin_ghost_added.txt members/tests/test_emails_ghost_added.py members/emails.py
git commit -m "feat(p4d): admin_ghost_added FYI email (templates + sender)"
```

---

## Task 4: Admin save_model — auto-add creator + fire notification

**Files:**
- Modify: `members/admin.py`
- Create: `members/tests/test_admin_publicsearchentry.py`

This task adds a `save_model` override to `PublicSearchEntryAdmin` that does two things on entry creation: (1) adds the creating admin to `added_by_admins`, (2) fires the `send_admin_ghost_added` notification.

- [ ] **Step 1: Write the failing tests for save_model behavior**

Create `members/tests/test_admin_publicsearchentry.py`:

```python
"""Tests for PublicSearchEntryAdmin.save_model — auto-cosign creator and
fire admin_ghost_added notification (P4d)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def fake_backend(settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.DEFAULT_FROM_EMAIL = "smoke@example.test"
    settings.SITE_URL = "https://prod.example.test"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    return FakeResendBackend


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
def test_admin_save_auto_adds_creator_to_signoffs(fake_backend, make_admin):
    """When an admin creates a PublicSearchEntry through the admin form,
    they are automatically added to added_by_admins — no manual checkbox
    required."""
    from members.models import PublicSearchEntry

    creator = make_admin()
    make_admin()  # second admin so the email has a recipient

    client = Client()
    client.force_login(creator)

    response = client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Idrissa",
            "last_name_initial": "S.",
            "years_at_ceg": "1980,1981,1982,1983",
            "note": "",
        },
    )
    assert response.status_code in (302, 200), f"got {response.status_code}, body={response.content[:500]}"

    entry = PublicSearchEntry.objects.get(first_name="Idrissa")
    assert creator in entry.added_by_admins.all()


@pytest.mark.django_db
def test_admin_save_does_not_re_add_creator_on_edit(fake_backend, make_admin):
    """Re-saving an existing entry doesn't re-fire the auto-add logic."""
    from members.models import PublicSearchEntry

    creator = make_admin()
    make_admin()  # second admin so first save's email has a recipient

    client = Client()
    client.force_login(creator)

    # Create
    client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Hamidou",
            "last_name_initial": "A.",
            "years_at_ceg": "1981,1982",
            "note": "",
        },
    )
    entry = PublicSearchEntry.objects.get(first_name="Hamidou")
    initial_count = entry.added_by_admins.count()

    # Edit (changes nothing material, just re-saves)
    client.post(
        f"/admin/members/publicsearchentry/{entry.pk}/change/",
        {
            "first_name": "Hamidou",
            "last_name_initial": "A.",
            "years_at_ceg": "1981,1982",
            "note": "Updated note",
            "added_by_admins": [creator.pk],
        },
    )
    entry.refresh_from_db()
    assert entry.added_by_admins.count() == initial_count


@pytest.mark.django_db
def test_admin_save_fires_notification_email_on_create(fake_backend, make_admin):
    """Creating a new entry through the admin fires the admin_ghost_added
    email to other staff — but not to the creator themselves."""
    from members.models import PublicSearchEntry  # noqa: F401

    creator = make_admin()
    other = make_admin()

    client = Client()
    client.force_login(creator)

    client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Aïssa",
            "last_name_initial": "D.",
            "years_at_ceg": "1982,1983",
            "note": "",
        },
    )
    assert len(fake_backend.sent_messages) == 1
    msg = fake_backend.sent_messages[0]
    assert other.email in msg["to"]
    assert creator.email not in msg["to"]
    assert "Aïssa" in msg["subject"]


@pytest.mark.django_db
def test_admin_save_does_not_fire_email_on_edit(fake_backend, make_admin):
    """Re-saving an existing entry doesn't fire a duplicate notification."""
    from members.models import PublicSearchEntry

    creator = make_admin()
    make_admin()

    client = Client()
    client.force_login(creator)

    client.post(
        "/admin/members/publicsearchentry/add/",
        {
            "first_name": "Aïcha",
            "last_name_initial": "B.",
            "years_at_ceg": "1980",
            "note": "",
        },
    )
    fake_backend.sent_messages.clear()

    entry = PublicSearchEntry.objects.get(first_name="Aïcha")
    client.post(
        f"/admin/members/publicsearchentry/{entry.pk}/change/",
        {
            "first_name": "Aïcha",
            "last_name_initial": "B.",
            "years_at_ceg": "1980,1981",
            "note": "",
            "added_by_admins": [creator.pk],
        },
    )
    assert len(fake_backend.sent_messages) == 0
```

- [ ] **Step 2: Run the tests — expect FAIL**

Run: `pytest members/tests/test_admin_publicsearchentry.py -v`

Expected: 4 FAIL — `save_model` override doesn't exist yet, so creator isn't auto-added and email isn't fired.

- [ ] **Step 3: Add `save_model` to `PublicSearchEntryAdmin`**

Open `members/admin.py`. Locate `PublicSearchEntryAdmin` (around line 172). Add this method INSIDE the class (after the `fieldsets` definition, before `def signoff_count` if it exists):

```python
    def save_model(self, request, obj, form, change):
        """P4d: on first save, auto-cosign the creating admin (so the entry
        publishes immediately) and fire the admin_ghost_added FYI email
        to other staff. Skipped on subsequent edits — the creator is
        already in added_by_admins by then, and a re-edit shouldn't
        re-notify."""
        super().save_model(request, obj, form, change)
        if not change:
            obj.added_by_admins.add(request.user)
            from .emails import send_admin_ghost_added
            send_admin_ghost_added(obj, added_by=request.user)
```

- [ ] **Step 4: Update the "Cosignature" fieldset section copy**

Still in `members/admin.py:PublicSearchEntryAdmin.fieldsets`, locate the second fieldset block (around lines 203-211):

```python
        (
            "Cosignature (2 admins requis pour publication)",
            {
                "fields": ("added_by_admins",),
                "description": (
                    "Ajoutez-vous à la liste pour cosigner. Au moins 2 admins "
                    "distincts requis avant que le nom n'apparaisse publiquement."
                ),
            },
        ),
```

REPLACE with:

```python
        (
            "Cosignataires (optionnel)",
            {
                "fields": ("added_by_admins",),
                "description": (
                    "Vous êtes ajouté·e automatiquement à l'enregistrement. "
                    "D'autres admins peuvent ajouter leur nom pour étoffer la "
                    "trace d'audit, mais ce n'est plus requis pour la publication."
                ),
            },
        ),
```

- [ ] **Step 5: Run the tests — expect PASS**

Run: `pytest members/tests/test_admin_publicsearchentry.py -v`

Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add members/admin.py members/tests/test_admin_publicsearchentry.py
git commit -m "feat(p4d): admin auto-cosigns creator + fires FYI email on save"
```

---

## Task 5: GhostStatusFilter cleanup (5 buckets → 3)

**Files:**
- Modify: `members/admin.py` (`GhostStatusFilter` class)
- Modify: `members/tests/test_admin_filters.py` (existing test)

The `draft` (0 cosigners) and `pending` (1 cosigner) buckets are no longer meaningful: with auto-cosign on save, brand-new entries always have ≥1 cosigner. The 3 remaining buckets (`published`, `stale`, `removed`) are the meaningful lifecycle states.

- [ ] **Step 1: Update the existing filter test for the new 3-bucket reality**

Open `members/tests/test_admin_filters.py`. REPLACE the entire `test_ghost_status_filter_buckets` function (lines 32-93) with this updated version:

```python
@pytest.mark.django_db
def test_ghost_status_filter_buckets(client, make_admin):
    """Each filter value returns the right entries and excludes the others.

    P4d simplified buckets (5 → 3):
      published — n>=1, not removed, < 365 days old
      stale     — n>=1, not removed, >= 365 days old
      removed   — removed_at is set (regardless of cosigners)
    """
    from members.models import PublicSearchEntry

    admin_user = make_admin()
    a, b = make_admin(), make_admin()

    client.force_login(admin_user)

    e_published = PublicSearchEntry.objects.create(
        first_name="Published", last_name_initial="B.", years_at_ceg=[1980]
    )
    e_published.added_by_admins.add(a)

    e_stale = PublicSearchEntry.objects.create(
        first_name="Stale", last_name_initial="T.", years_at_ceg=[1980]
    )
    e_stale.added_by_admins.add(a, b)
    PublicSearchEntry.objects.filter(pk=e_stale.pk).update(
        added_at=timezone.now() - timedelta(days=400)
    )

    e_removed = PublicSearchEntry.objects.create(
        first_name="Removed", last_name_initial="R.", years_at_ceg=[1980]
    )
    e_removed.added_by_admins.add(a, b)
    e_removed.removed_at = timezone.now()
    e_removed.save()

    cases = [
        ("published", "Published", ["Stale", "Removed"]),
        ("stale", "Stale", ["Published", "Removed"]),
        ("removed", "Removed", ["Published", "Stale"]),
    ]
    for value, expected_present, expected_absent in cases:
        response = client.get(f"/admin/members/publicsearchentry/?ghost_status={value}")
        assert response.status_code == 200, f"GET ?ghost_status={value} failed"
        body = response.content.decode("utf-8")
        assert expected_present in body, f"?ghost_status={value} should include {expected_present}"
        for absent in expected_absent:
            assert absent not in body, f"?ghost_status={value} should NOT include {absent}"
```

- [ ] **Step 2: Run the test — expect FAIL**

Run: `pytest members/tests/test_admin_filters.py -v`

Expected: FAIL — the filter still offers 5 buckets (including `draft` and `pending`), but the test expects only 3 to work, and the `published` bucket query still requires `n__gte=2`.

- [ ] **Step 3: Simplify the `GhostStatusFilter` class**

Open `members/admin.py`. Locate `class GhostStatusFilter` (around line 127). REPLACE the entire class with:

```python
class GhostStatusFilter(admin.SimpleListFilter):
    """Lifecycle status of a PublicSearchEntry, computed from signoff
    count + removed_at + added_at. P4d simplified to 3 meaningful
    buckets (was 5 before single-admin governance)."""

    title = "Statut publication"
    parameter_name = "ghost_status"

    def lookups(self, request, model_admin):
        return [
            ("published", "Publiée"),
            ("stale", "Périmée (>12 mois)"),
            ("removed", "Retirée"),
        ]

    def queryset(self, request, queryset):
        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        value = self.value()
        if value is None:
            return queryset

        if value == "removed":
            return queryset.filter(removed_at__isnull=False)

        qs = queryset.filter(removed_at__isnull=True).annotate(n=Count("added_by_admins"))
        if value == "published":
            cutoff = timezone.now() - timedelta(days=365)
            return qs.filter(n__gte=1, added_at__gt=cutoff)
        if value == "stale":
            cutoff = timezone.now() - timedelta(days=365)
            return qs.filter(n__gte=1, added_at__lte=cutoff)
        return queryset
```

(Changes vs. before: dropped `draft` and `pending` lookup tuples; dropped their `if value == "..."` branches; `published` and `stale` now use `n__gte=1` instead of `n__gte=2`.)

- [ ] **Step 4: Run the test — expect PASS**

Run: `pytest members/tests/test_admin_filters.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add members/admin.py members/tests/test_admin_filters.py
git commit -m "refactor(p4d): simplify GhostStatusFilter from 5 buckets to 3"
```

---

## Task 6: STATUS.md update + final verification

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Add the P4d row to the Phase Index table**

Open `docs/superpowers/STATUS.md`. Locate the Phase Index table near the top. The table currently has a P3.1 row (which we added in P3.1) between P4c and P5. Insert a new P4d row immediately AFTER P4c and BEFORE P3.1 (so the P4* phases stay grouped):

```markdown
| P4d | Public surface — magazine cards + single-admin governance | Complete (2026-05-03) | [plan](plans/2026-05-03-magazine-cards-single-admin.md) |
```

After your edit, the relevant section should read:

```markdown
| P4c | Public surface — quarterly review automation + admin status filter | Complete (tag `v0.4.0c-public-surface-admin`, 2026-05-03) | [plan](plans/2026-05-03-public-surface-admin.md) |
| P4d | Public surface — magazine cards + single-admin governance | Complete (2026-05-03) | [plan](plans/2026-05-03-magazine-cards-single-admin.md) |
| P3.1 | Parrain UX Polish (pending-vouches dashboard + 90-day session) | Complete (2026-05-03) | [plan](plans/2026-05-03-parrain-ux-polish.md) |
| P5 | Mémoire seed | Not started | — |
```

- [ ] **Step 2: Add the P4d phase section**

Append a new section to `docs/superpowers/STATUS.md`. Place it AFTER the existing P4c section and BEFORE the existing P3.1 section (so the P4* phase sections stay grouped). The format mirrors the existing P3.1 section:

```markdown
## P4d — Magazine cards + single-admin governance

**Shipped:** 2026-05-03
**Plan:** [plans/2026-05-03-magazine-cards-single-admin.md](plans/2026-05-03-magazine-cards-single-admin.md)
**Spec:** [specs/2026-05-03-magazine-cards-single-admin-design.md](specs/2026-05-03-magazine-cards-single-admin-design.md)
**Test suite:** all passing

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Drop 2-signoff publication gate | [x] | _filled by implementer_ |
| 2 | Magazine ghost cards (monogram + accent + warm chrome) | [x] | _filled by implementer_ |
| 3 | admin_ghost_added FYI email infrastructure | [x] | _filled by implementer_ |
| 4 | Admin save_model — auto-cosign + fire notification | [x] | _filled by implementer_ |
| 5 | GhostStatusFilter cleanup (5 → 3 buckets) | [x] | _filled by implementer_ |
| 6 | STATUS.md update | [x] | (this commit) |

---
```

- [ ] **Step 3: Fill in the commit SHAs**

Run: `git log --oneline | head -10`

Expected output: a list of P4d-related commits in reverse chronological order. Map each Task # to its terminal commit SHA. Replace each `_filled by implementer_` placeholder with the appropriate short SHA.

- [ ] **Step 4: Run the full test suite to confirm green**

Run: `pytest --tb=short --ignore=members/tests/test_cloudinary_sign.py` (the `--ignore` skips an environmental failure unrelated to P4d — see commit history for context).

Expected: ALL PASS. Test count should increase by ~7 over the prior baseline (~365 vs ~347 prior).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(p4d): mark Magazine cards + single-admin governance complete"
```

---

## Final verification checklist

After Task 6 commits:

- [ ] `pytest --ignore=members/tests/test_cloudinary_sign.py` exits clean.
- [ ] `git log --oneline | head -20` shows all P4d commits in order.
- [ ] Manual smoke (against local runserver, with PUBLIC_GHOST_LIST_ENABLED=True, with seeded ghost entries):
  1. Visit `/` as an anonymous user. Confirm the "NOUS RECHERCHONS AUSSI…" section renders with the new magazine cards: monogram circle on the left (or top on mobile), gold accent bar on the left edge, warm cream chrome, "Si vous le connaissez, partagez ce lien." copy.
  2. Log in as admin. Visit `/admin/members/publicsearchentry/add/`. Fill the form (no need to check your name in the cosignature widget). Click Save.
  3. Confirm the entry appears immediately at `/` (in another browser as anonymous, or after logging out).
  4. Confirm an email lands in the configured email backend (Resend in staging/prod; FakeResendBackend in tests; console in dev).
  5. Visit `/admin/members/publicsearchentry/?ghost_status=published` and confirm the new entry shows up under the simplified 3-bucket filter.

---

## What this plan does NOT do (per spec §Non-goals)

- No new "ghost reviewer" role/group — all `is_staff=True, is_active=True` users receive the notification.
- No approval-queue UI — create-publishes-immediately is the whole point.
- No timed grace period.
- No HTML editor for the `note` field.
- No member-facing ghost-add path — admins only via Django admin.
- No model schema changes, no migrations.
