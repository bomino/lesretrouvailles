# P6b — RGPD Admin Purge Design

**Status:** Approved.
**Phase:** P6b (subset of master spec §8 Ops & RGPD; implements §9.4 Politique de Suppression de Compte for the admin-initiated case).

## Goal

Give Super Admins a single tool that hard-deletes a member's PII from the platform — DB, Cloudinary, Tigris bucket, and any cross-domain references — in one auditable operation. Closes the actual legal gap from §9.4 (we currently have no way to fully delete a member). Builds the engine that a future member-self-service flow (P6c.x) will call into.

## Non-goals (P6b)

- **Member self-service deletion flow.** Master spec §9.4 describes a member-facing "delete my account" form with content-handling choices (delete vs anonymize for photos/témoignages). Deferred — at our scale and stage, RGPD requests come in via email and are handled by an admin. Self-service can ship later as a separate phase that calls into this engine.
- **Granular content choices** ("(a) suppression dure, ou (b) conservation avec auteur anonymisé"). This phase hard-deletes everything personal; anonymization is reserved for cross-domain references (audit trail, FKs that PROTECT). The choice menu can ship with the self-service flow.
- **AdminApplication 6-month retention cron.** Master spec §9.4 says rejected applications auto-purge after 6 months. The infrastructure (`retention_until` field, `purge()` method) exists; wiring it into the cooptation cron is a separate small phase.
- **AuditLog 12-month retention.** Master spec §9.4 says audit logs are kept 12 months then purged. This is a different cron, deferred.
- **DMARC monitoring.** P6c scope, not P6b.

## Architecture (§A)

Three components:

1. **`members/services.py::rgpd_purge_member(member, *, actor, dry_run=False)`** — the engine. Pure function returning a structured deletion summary `{"deleted_counts": {...}, "errors": [...]}`. Used by both the CLI and the admin action.
2. **`members/management/commands/rgpd_purge_member.py`** — CLI wrapper. `python manage.py rgpd_purge_member <email>` with `--dry-run` and `--yes` flags. Resolves the member, calls the service, prints a human summary, exits 0 on success, 1 on refused-precondition.
3. **Admin action on `MemberAdmin`** — "Purger RGPD (irréversible)" with Django's standard intermediate confirmation page. POST submits → calls the service with `actor=request.user` → renders success/error message.

## Member identification (§B)

The engine accepts a `Member` instance. The CLI resolves by email (via the user's email — Member doesn't have its own email field; it lives on the linked User). Admin action passes the queryset's selected Member directly.

If multiple members match the email (data corruption — shouldn't happen since Member.user is OneToOne and User.email is unique by allauth config), the CLI refuses with the list and asks the operator to disambiguate by `--member-id`.

## What the engine deletes (§C)

The order matters because of PROTECT relationships.

### Step 1 — Pre-flight checks (refuse if any apply)

- **`InMemoriamEntry.created_by == member.user`** with at least one row → refuse. Message: *"Member has created N In Memoriam fiches. Reassign `created_by` manually (Django admin → In Memoriam → bulk-edit) or delete those fiches before purging this member."* This is rare (admin role + creating fiches + then asking to be purged) and easy for an admin to fix in seconds.

- **`actor.id == member.user.id`** → refuse. Message: *"Cannot purge yourself. Ask another admin."* Self-purge would lock you out mid-operation; not worth handling cleanly.

If the member has zero PROTECT-blocking rows and the actor is different, proceed.

### Step 2 — Collect every Cloudinary public_id tied to this member

- `member.photo_public_id` (profile photo)
- `Memory.objects.filter(created_by=member.user).values_list("photo_public_id")` (all gallery photos this member uploaded)

Build a single set of `public_ids` to delete from external systems.

### Step 3 — Delete from Cloudinary (per public_id)

`cloud.delete(public_id)` for each. The existing `RealCloudinary.delete()` already handles empty public_id and Cloudinary-side missing-key gracefully.

### Step 4 — Delete from the Tigris bucket (per public_id)

For each public_id:
- `storage.list_versions(prefix=public_id)` → list of `{file_id, path, size}`
- For each version: `storage.delete_version(path, file_id)`

This handles future versioning if Tigris ever supports it. Today (versioning off) it's effectively a single delete per path.

### Step 5 — Hard-delete dependent DB rows where this member is PROTECT-referenced

- `CooptationRequest.objects.filter(parrain=member).delete()` — deletes the requests where this member vouched. The host `AdminApplication` keeps its other fields; only the vouching record is gone.
- `InMemoriamNomination.objects.filter(nominator=member).delete()` — deletes nominations submitted by this member. The fiche they nominated (if accepted into an `InMemoriamEntry`) is unaffected — `linked_entry` already uses SET_NULL.

### Step 6 — Hard-delete the member's authored content

- `Memory.objects.filter(created_by=member.user).delete()` — gallery photos this member uploaded. Their `photo_public_id`s were already removed from Cloudinary + bucket in steps 3–4.

### Step 7 — Anonymize prior `AdminApplication` rows

- `AdminApplication.objects.filter(email=member.user.email).update(...)` — call `.purge()` on each (clears full_name, nickname, email, whatsapp, city, country, profession, review_note, source_ip, referrer; sets status=`purged`). Idempotent; no-op if already purged.

### Step 8 — Cascade delete via the User row

- `member.user.delete()` — Django cascades through:
  - Member (OneToOne CASCADE)
  - NotificationPreference (CASCADE on Member)
  - ConsentRecord (CASCADE on Member)
  - Sessions (auth_user FK)
  - SET_NULL on AuditLog.actor, Memory.created_by (no rows left), AdminApplication.reviewed_by, InMemoriamNomination.reviewed_by, InMemoriamEntry.created_by (already verified empty in step 1)

### Step 9 — Audit

Append a single `AuditLog` row:

```python
AuditLog.objects.create(
    actor=actor,                                  # the admin running the purge
    action="rgpd.member.purged",
    target_type="Member",
    target_id=str(member_id),                     # numeric ID, not email
    metadata={
        "email_hash": hashlib.sha1(member.user.email.encode()).hexdigest()[:12],
        "deleted_counts": {
            "memories": N,
            "cooptation_requests": N,
            "memoriam_nominations": N,
            "admin_applications_anonymized": N,
            "cloudinary_public_ids": N,
            "bucket_versions": N,
        },
    },
)
```

No PII in metadata. The `email_hash` lets an investigator confirm "the member with email X was purged on date Y" without storing the email itself.

## New AuditLog action (§D)

Add to `AuditLog.ACTION_CHOICES`:

```python
("rgpd.member.purged", "Membre purgé (RGPD)"),
```

This is a CharField choice — not a schema change at the DB level, just an `ALTER TABLE` no-op. Migration captures the new choice.

## Confirmation UX (§E)

### Management command

```
python manage.py rgpd_purge_member alice@example.com
```

Default behavior: pretty-prints what will be deleted (counts only, no PII), then prompts `Proceed? [y/N]:`. Aborts on anything other than `y`/`Y`.

Flags:
- `--dry-run` — print the plan and exit without prompting or executing.
- `--yes` — skip the prompt (for piping / CI). Still executes.
- `--member-id <int>` — disambiguate when multiple members share the same email (shouldn't happen but defensive).
- `--actor <user_id>` — override the audit actor (defaults to `User.objects.get(username="system")` if it exists, else `None`). Real admins should pass their own `--actor` via `--actor=$(id)` style; the admin action does this automatically.

### Admin action

`MemberAdmin.actions = [..., "rgpd_purge_action"]`. Selecting one or more members → "Purger RGPD (irréversible)" → intermediate page (Django's built-in confirmation pattern via `TemplateResponse`) showing:

- Member full name + email (visible to the admin who's about to do this; they need it for sanity check)
- Counts of what will be deleted (same shape as the CLI summary)
- A "Saisir l'email pour confirmer" text input (operator must type the email; submit button is disabled until match)
- Submit/Cancel buttons

On submit: calls `rgpd_purge_member(member, actor=request.user)`, redirects to the changelist with success or error message via Django's messages framework.

The "type the email" pattern is the same one GitHub uses for repo deletion. Adds 5 seconds of friction; eliminates 100% of fat-finger purges.

## Idempotency (§F)

- Missing member (CLI invocation with email that doesn't exist) → exit 0 with message `"No member found with email <email>. Already purged?"`.
- Cloudinary delete on already-missing public_id → SDK no-op (already handled in `RealCloudinary.delete()`).
- Bucket `list_versions` on already-missing prefix → empty list → no `delete_version` calls.
- Re-running the engine on a partially-completed purge → all the steps that already ran become no-ops; the missing pieces complete.

## Tests (§G)

10 tests in `members/tests/test_rgpd_purge.py`:

| # | Test | Coverage |
|---|---|---|
| 1 | `test_purge_member_with_profile_photo` | Cloudinary called with photo_public_id, bucket versions deleted, Member row gone, User row gone, NotificationPreference + ConsentRecord cascade-deleted, AuditLog rgpd.member.purged entry created |
| 2 | `test_purge_member_who_authored_memories` | Each Memory's photo_public_id deleted from Cloudinary + bucket, Memory rows hard-deleted |
| 3 | `test_purge_member_who_is_parrain` | CooptationRequest rows where parrain=member hard-deleted; the AdminApplication rows persist |
| 4 | `test_purge_member_who_nominated` | InMemoriamNomination rows hard-deleted; the linked InMemoriamEntry persists |
| 5 | `test_purge_refuses_when_member_created_inmemoriam_fiche` | SystemExit(1) with the "reassign created_by manually" message; nothing deleted |
| 6 | `test_purge_refuses_self_purge` | Refused when actor.id == member.user.id |
| 7 | `test_purge_idempotent_missing_member` | CLI on missing email exits 0 with informative message |
| 8 | `test_dry_run_makes_no_changes` | --dry-run prints plan; DB and external clients (FakeCloudinary, FakeStorage) record no mutations |
| 9 | `test_audit_log_entry_redacted` | AuditLog row's metadata has email_hash (12 chars) and deleted_counts; NO email, no full name, no city |
| 10 | `test_admin_action_intermediate_confirmation` | The admin action returns a confirmation page; POST without typed email refuses; POST with typed email succeeds |

The fixture `reset_fakes` (already in P6a tests) resets `cloudinary.reset_fake_client()` and `storage.reset_fake_client()` between tests so call recordings don't leak.

## Files (§H)

### Create

- `members/services.py` (or extend if exists) — `rgpd_purge_member()`
- `members/management/commands/rgpd_purge_member.py`
- `members/tests/test_rgpd_purge.py`
- `members/migrations/00XX_auditlog_rgpd_action.py` — adds `rgpd.member.purged` to choices
- `docs/runbooks/rgpd-purge.md` — operator runbook

### Modify

- `members/models.py` — add `("rgpd.member.purged", "Membre purgé (RGPD)")` to `AuditLog.ACTION_CHOICES`
- `members/admin.py` — register the `rgpd_purge_action` on `MemberAdmin`
- `docs/superpowers/STATUS.md` — mark P6b complete after ship

## Risks (§J)

| Risk | Mitigation |
|---|---|
| Admin fat-fingers and purges the wrong member | Two layers: CLI prompt (or `--yes` for intentional bypass), admin action's "type the email to confirm" pattern. |
| Engine partially fails halfway through (e.g., Cloudinary timeout mid-loop) | Each external step is idempotent. Re-running completes the remaining work. The AuditLog entry is the LAST step — if it's missing, the operation didn't fully complete. Operator re-runs. |
| Bucket purge misses a version because Tigris returns paginated `list_versions` and we don't iterate | `boto3`'s paginator (already used in `RealStorage.list_versions`) handles pagination. Tested. |
| `Member.user.delete()` cascades to something we didn't expect | The model graph survey in this spec is exhaustive. Tests cover each branch. New PROTECT-bound models added in future phases must extend `_collect_blockers()` in the service or they'll cascade incorrectly. Documented in the service module docstring. |
| AuditLog's `actor` set to None makes the trail look anonymous after purge | That's the design — once an admin is purged, their actor reference becomes None on past entries. The pre-purge entries still record `target_type` + `target_id` + `metadata` so the audit trail of *what they did* is preserved, just not *who they were*. RGPD-compliant. |
| Future admin needs to know "was member X purged?" | The `rgpd.member.purged` entry's `email_hash` lets them verify by hashing the email and comparing — without storing the original. |

## Reasoning §A — why hard-delete vs anonymize

Master spec §9.4 offers a choice for some content types (gallery photos, témoignages). For Option A (admin-only purge), we collapse the choice to **hard-delete for personal content, anonymize for cross-domain references**:

- **Personal content** (this member's profile photo, their gallery uploads, their nominations): **hard-delete**. The member explicitly wants their data gone; keeping it as "anonymous content by Ancien membre" is a feature for self-service flows where the member chose that option, not for admin-initiated purges where the request is "remove me."
- **Cross-domain references** (audit log entries about other people that mention this admin as actor; AdminApplication rows where this admin reviewed someone): **anonymize via SET_NULL**. The host record is about someone else; deleting it would corrupt their audit trail.

This is the strictest interpretation: nothing personal kept, nothing about other people corrupted. When the self-service flow ships, it'll override this default with the user's explicit choices.
