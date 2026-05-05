# P6b — RGPD Admin Purge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin-driven hard-purge of a member's PII from the platform — DB, Cloudinary, Tigris bucket, and cross-domain references — in one auditable operation. Closes the §9.4 RGPD deletion gap. Builds the engine that a future member-self-service flow will call into.

**Architecture:** A single service function `members.services.rgpd_purge_member(member, *, actor, dry_run=False)` is the engine. Two callers: a CLI (`python manage.py rgpd_purge_member <email>`) and a `MemberAdmin` action with an email-confirm intermediate page. Idempotent end-to-end so a half-failed run can be re-run safely.

**Tech Stack:** Django 5, existing `alumni.cloudinary`, existing `alumni.storage` (boto3 against the Tigris bucket), existing `members.models.AuditLog`. No new pip deps.

**Spec:** [`docs/superpowers/specs/2026-05-05-rgpd-admin-purge-design.md`](../specs/2026-05-05-rgpd-admin-purge-design.md)

---

## File touch list

### Create

- `members/services.py` (or extend if it exists — verify on Task 2)
- `members/management/commands/rgpd_purge_member.py`
- `members/tests/test_rgpd_purge.py`
- `members/migrations/00XX_auditlog_rgpd_action.py` (auto-generated)
- `members/templates/admin/members/member/rgpd_purge_confirm.html` (admin action intermediate page)
- `docs/runbooks/rgpd-purge.md`

### Modify

- `members/models.py` — add `("rgpd.member.purged", "Membre purgé (RGPD)")` to `AuditLog.ACTION_CHOICES`
- `members/admin.py` — register `rgpd_purge_action` on `MemberAdmin`
- `docs/superpowers/STATUS.md` — mark P6b complete after ship

---

## Task 1: AuditLog `rgpd.member.purged` action choice + migration

**Why first:** Foundation. The service function writes this action; the migration must exist before tests run. Trivial diff.

**Files:**
- Modify: `members/models.py`
- Create: `members/migrations/00XX_auditlog_rgpd_action.py` (via `makemigrations`)

- [ ] **Step 1: Add the choice tuple to `AuditLog.ACTION_CHOICES`**

In `members/models.py`, find `class AuditLog` and append to `ACTION_CHOICES`:

```python
("rgpd.member.purged", "Membre purgé (RGPD)"),
```

- [ ] **Step 2: Generate the migration**

```bash
python manage.py makemigrations members --name auditlog_rgpd_action
```

Verify the generated file has only an `AlterField` on `AuditLog.action` (no schema change beyond the choices list).

- [ ] **Step 3: Run migrations + full suite — no regressions**

```bash
python manage.py migrate
pytest -q
```

- [ ] **Step 4: Commit**

```bash
git add members/models.py members/migrations/
git commit -m "feat(audit): rgpd.member.purged action choice + migration"
```

---

## Task 2: `rgpd_purge_member` service function

**Files:**
- Create or extend: `members/services.py` (verify existence first)
- Create: `members/tests/test_rgpd_purge.py`

The service is a pure function — receives the resolved Member + actor User, optionally dry-run; returns a `PurgeSummary` dataclass-or-dict with deletion counts. Two refusal paths are explicit (precondition errors), distinct from operational errors.

**Function signature:**

```python
def rgpd_purge_member(
    member: Member,
    *,
    actor: User | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Hard-purge a member's PII. Returns a summary dict.

    Raises PurgeRefused on precondition violations (created In Memoriam
    fiches, self-purge). Other errors propagate as-is.
    """
```

Returns:
```python
{
    "member_id": int,
    "email_hash": str,                    # 12-char sha1
    "deleted_counts": {
        "memories": int,
        "cooptation_requests": int,
        "memoriam_nominations": int,
        "admin_applications_anonymized": int,
        "cloudinary_public_ids": int,
        "bucket_versions": int,
    },
    "audit_log_id": int | None,           # None on dry-run
    "dry_run": bool,
}
```

Define `PurgeRefused` as a custom exception in the same module.

### Tests first (10 total, all in `members/tests/test_rgpd_purge.py`)

- [ ] **Step 1: Write the failing tests**

Test bodies cover the spec's §G test list. Use the same `reset_fakes` fixture pattern as P6a (resets `cloudinary` and `storage` fake clients between tests). Use the existing `_make_member` helper pattern from `core/tests/test_backup_media.py`.

Helpers needed:
- `_make_admin_user(username, *, is_staff=True)`
- `_make_member(suffix, *, photo_public_id="")` — wraps User+Member creation
- `_make_memory(member, public_id)` — Memory with created_by=member.user
- `_make_cooptation_request(parrain, application)` — CooptationRequest with parrain=member
- `_make_inmemoriam_nomination(member)` — InMemoriamNomination with nominator=member
- `_make_inmemoriam_entry(creator_user)` — InMemoriamEntry with created_by=creator_user (for the refusal test)

Test list:

| # | Test | Asserts |
|---|---|---|
| 1 | `test_purge_member_with_profile_photo` | After call: cloud.delete_calls includes member's photo_public_id; storage.upload+delete_calls reflect bucket version cleanup; Member/User rows gone; AuditLog entry created |
| 2 | `test_purge_member_who_authored_memories` | Memory rows gone; Cloudinary delete called for each Memory.photo_public_id; bucket cleared for each |
| 3 | `test_purge_member_who_is_parrain` | CooptationRequest rows where parrain=member gone; AdminApplication rows persist |
| 4 | `test_purge_member_who_nominated` | InMemoriamNomination rows gone; the linked InMemoriamEntry persists |
| 5 | `test_purge_refuses_when_member_created_inmemoriam_fiche` | Raises `PurgeRefused`; nothing deleted (DB and fake-client call lists unchanged) |
| 6 | `test_purge_refuses_self_purge` | Raises `PurgeRefused` when actor.id == member.user.id |
| 7 | `test_purge_idempotent_on_already_partial` | Pre-delete the member's photo from FakeCloudinary, then purge — no error; remaining steps still run |
| 8 | `test_dry_run_makes_no_changes` | Returns the summary; DB and fake clients unchanged; no AuditLog row created |
| 9 | `test_audit_log_entry_redacted` | AuditLog metadata has email_hash (12 chars hex), deleted_counts; NO email/full_name/city in metadata or target_id |
| 10 | `test_purge_anonymizes_admin_application` | Pre-create an AdminApplication with email=member's email; after purge, application row exists but full_name/email/etc are blank, status='purged' |

- [ ] **Step 2: Run tests, expect failure**

```bash
pytest members/tests/test_rgpd_purge.py -q
```

Expected: ImportError on `from members.services import rgpd_purge_member, PurgeRefused`.

- [ ] **Step 3: Implement `members/services.py`**

Skeleton:

```python
"""Member-level service operations.

P6b adds rgpd_purge_member() — hard-deletes a member's PII end-to-end.
See docs/superpowers/specs/2026-05-05-rgpd-admin-purge-design.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction

from alumni import cloudinary as cloud_mod
from alumni import storage as storage_mod
from members.models import AuditLog, Member

logger = logging.getLogger(__name__)


class PurgeRefused(Exception):
    """Precondition violation that blocks a clean cascade.

    Distinct from operational errors so callers can render a friendly
    message instead of a stack trace.
    """


def rgpd_purge_member(
    member: Member,
    *,
    actor: Any | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    # ... step 1: preflight
    # ... step 2: collect public_ids
    # ... step 3: cloudinary deletes
    # ... step 4: bucket version deletes
    # ... step 5: hard-delete dependent rows (CooptationRequest, InMemoriamNomination)
    # ... step 6: hard-delete member's authored Memories
    # ... step 7: anonymize prior AdminApplications via .purge()
    # ... step 8: cascade-delete via member.user.delete()
    # ... step 9: AuditLog entry
    return {...}
```

Key implementation notes:
- Wrap steps 5-8 in `transaction.atomic()` so a mid-step DB failure doesn't leave half-deleted state.
- External calls (Cloudinary, bucket) happen BEFORE the DB transaction. If they fail, the DB is untouched and the operator can retry.
- Step 9 (AuditLog) happens AFTER the transaction commits — the entry's existence is the signal that the purge fully completed. If it's missing, operator knows to re-run.

- [ ] **Step 4: Run tests, expect pass (10 passing)**

```bash
pytest members/tests/test_rgpd_purge.py -q
```

- [ ] **Step 5: Run full suite — no regressions**

```bash
pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add members/services.py members/tests/test_rgpd_purge.py
git commit -m "feat(rgpd): rgpd_purge_member service (engine + 10 tests)"
```

---

## Task 3: `rgpd_purge_member` management command

**Files:**
- Create: `members/management/commands/rgpd_purge_member.py`
- Extend: `members/tests/test_rgpd_purge.py` (add CLI-flow tests)

Resolves the member by email (or `--member-id`), confirms with the operator (or accepts `--yes`), invokes the service, prints a summary, exits with the right code.

- [ ] **Step 1: Write the failing CLI tests** (3 new, appended to the existing test file)

| # | Test | Asserts |
|---|---|---|
| 11 | `test_cli_dry_run_reports_plan` | `call_command("rgpd_purge_member", "alice@example.com", "--dry-run")` prints summary; DB unchanged |
| 12 | `test_cli_unknown_email_exits_zero` | Email with no match: stdout informative message, exit code 0 (caught via SystemExit assertion) |
| 13 | `test_cli_executes_with_yes_flag` | `--yes` skips prompt; member is purged; AuditLog entry created |

- [ ] **Step 2: Run, expect failure** (`Unknown command: 'rgpd_purge_member'`)

- [ ] **Step 3: Implement the command**

Key elements:
- Args: `email` (positional), `--dry-run`, `--yes`, `--member-id <int>`, `--actor <user_id>`.
- Resolution: filter Member where `user__email__iexact=email`; refuse if multiple match unless `--member-id` given.
- Default actor: `User.objects.filter(username="system").first()` if exists, else `None`.
- Confirmation: when not `--yes` and not `--dry-run`, print plan and read `input("Proceed? [y/N]: ")`. Anything other than `y`/`Y` aborts (exit 0, not an error).
- Catch `PurgeRefused` and print the message cleanly; exit 1.

- [ ] **Step 4: Run tests, expect pass (13 total)**

- [ ] **Step 5: Full suite, no regressions**

- [ ] **Step 6: Commit**

```bash
git add members/management/ members/tests/test_rgpd_purge.py
git commit -m "feat(rgpd): rgpd_purge_member management command (--dry-run, --yes)"
```

---

## Task 4: Admin action with email-confirm intermediate page

**Files:**
- Modify: `members/admin.py`
- Create: `members/templates/admin/members/member/rgpd_purge_confirm.html`
- Extend: `members/tests/test_rgpd_purge.py`

**The action's contract:**
- Selecting one or more members in the changelist + choosing "Purger RGPD (irréversible)" renders the confirmation template.
- The template shows each selected member's full name + email + counts (one section per member if multiple were selected).
- For each member, an `<input type="text" name="confirm_email_<id>">` must be filled with the exact email before the submit button enables (JS) or the form rejects on POST (server-side defense).
- POST: validates each typed email matches; calls `rgpd_purge_member()` per member; aggregates results into a Django messages summary.

- [ ] **Step 1: Write the admin-action tests** (1 new)

| # | Test | Asserts |
|---|---|---|
| 14 | `test_admin_action_intermediate_confirmation` | Posting the action with no `confirm_email_<id>` field renders the template (no purge); posting with a wrong email refuses; posting with the correct email succeeds and redirects |

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Implement `rgpd_purge_action`**

```python
@admin.action(description="Purger RGPD (irréversible)")
def rgpd_purge_action(self, request, queryset):
    if "apply" in request.POST:
        # validate typed-emails
        # call service per member, collect results
        # messages.success / messages.error
        # return redirect to changelist
    else:
        # render confirmation template
```

The "type to confirm" input is checked BOTH on the client (disable submit if any input mismatches) AND on the server (refuse if `request.POST.get(f"confirm_email_{m.id}") != m.user.email`).

- [ ] **Step 4: Build the template**

Inherits from `admin/base_site.html`. Renders one row per selected member with their identifying details and the confirm input.

- [ ] **Step 5: Run tests, expect pass (14 total)**

- [ ] **Step 6: Full suite, no regressions**

- [ ] **Step 7: Commit**

```bash
git add members/admin.py members/templates/admin/ members/tests/test_rgpd_purge.py
git commit -m "feat(rgpd): admin action 'Purger RGPD' with type-to-confirm intermediate page"
```

---

## Task 5: Operator runbook

**Files:**
- Create: `docs/runbooks/rgpd-purge.md`

Operator-facing reference. No code, no tests.

Sections:
1. **When to use** — incoming RGPD §17 deletion request via email, admin needs to comply within 30 days.
2. **CLI walkthrough** — basic invocation, --dry-run first, --yes for batch.
3. **Admin-action walkthrough** — Django admin → Members → select → action → confirmation page → type email → submit.
4. **What gets deleted** — table from spec §C, restated in operator-friendly French.
5. **Edge cases**:
   - "Member created In Memoriam fiches" → reassign created_by in admin first
   - "Self-purge" → ask another admin
   - "Multiple members with same email" → use --member-id
   - "Half-failed run" → re-run; engine is idempotent
6. **Verifying the purge** — check AuditLog for the `rgpd.member.purged` entry; verify member's photo_public_id is gone from Cloudinary dashboard; verify bucket via `aws s3 ls --endpoint-url=...`.

- [ ] **Step 1: Write the runbook**
- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/rgpd-purge.md
git commit -m "docs(runbook): RGPD admin purge — when to use, walkthroughs, edge cases"
```

---

## Task 6: STATUS update + final verification

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Update Phase Index**

Replace the current `P6` row with two rows:

```markdown
| P6a | Ops — media backup (Cloudinary→Railway bucket) | Complete (2026-05-05) | [plan](plans/2026-05-04-media-backup.md) |
| P6b | Ops — RGPD admin purge | Complete (2026-05-05) | [plan](plans/2026-05-05-rgpd-admin-purge.md) |
| P6 | Ops & RGPD (full) | In progress (P6a + P6b complete; P6c not started) | — |
```

- [ ] **Step 2: Append a P6b section** with task table, commit shas, test count, and design decisions.

- [ ] **Step 3: Run the full test suite one final time**

```bash
pytest -q
```

Expected: 463 (P6a baseline) + 14 (new P6b tests) = ~477 passing.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(p6b): mark P6b complete in STATUS"
```

- [ ] **Step 5: Verify branch state**

```bash
git status
git log --oneline main..HEAD
```

Expected: working tree clean, ~6–7 commits on `feat/p6b-rgpd-admin-purge`.

---

## Self-review summary

**Spec coverage:**
- §A architecture — Tasks 2 (engine) + 3 (CLI) + 4 (admin action) cover all three components.
- §B member identification — Task 3 (CLI resolves by email; multi-match refuses unless `--member-id`).
- §C deletion steps — Task 2 implements steps 1–9 in order.
- §D AuditLog action — Task 1.
- §E confirmation UX — Task 3 (CLI prompt + --yes + --dry-run); Task 4 (intermediate page + type-to-confirm).
- §F idempotency — Task 2 implementation + tests 7, 12.
- §G tests — distributed: 10 in Task 2, 3 in Task 3, 1 in Task 4 = 14 total.
- §H file touch list — covered.
- §J risks — admin friction in Tasks 3, 4; idempotency in Task 2; documented in runbook (Task 5).

**Type/name consistency:**
- Function: `members.services.rgpd_purge_member()`. Exception: `PurgeRefused`. Action choice: `"rgpd.member.purged"`. Command: `rgpd_purge_member`. Action method: `rgpd_purge_action`. All consistent across Tasks 1, 2, 3, 4.
- Returned summary dict shape (see Task 2 docstring) is the same in service, CLI output, and admin action's success message.

No placeholder strings or TBD markers in code.
