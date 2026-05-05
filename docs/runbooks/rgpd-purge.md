# RGPD member purge runbook

> Authoritative for **admin-initiated** account deletion (RGPD §17 right-to-erasure).
> Member-self-service flow is not yet shipped — incoming deletion requests today come via email and an admin executes the procedure below.

**Spec:** [docs/superpowers/specs/2026-05-05-rgpd-admin-purge-design.md](../superpowers/specs/2026-05-05-rgpd-admin-purge-design.md)
**Engine:** `members/services.py::rgpd_purge_member`
**CLI:** `python manage.py rgpd_purge_member <email>`
**Admin UI:** Django admin → Membres → select rows → action "Purger RGPD (irréversible)"

---

## When to use

A member emails an admin (or contacts the platform via another channel) requesting deletion of their personal data under RGPD §17. The platform must comply within 30 days.

This procedure does **not** apply to:
- Soft-suspending a member (set `Member.status = "suspended"` via the admin instead)
- Removing a deceased member's profile (see In Memoriam workflow — the fiche is a separate object)
- Deleting a public-search "ghost" entry (use the existing `RemovalRequest` flow)

---

## Procedure A — Admin UI (recommended for one-off cases)

1. Sign in to `/admin/` as a super-admin.
2. Navigate to **Membres → Members**.
3. Tick the checkbox next to the member to delete (or several, but **one at a time is safer**).
4. From the actions dropdown above the list, choose **"Purger RGPD (irréversible)"** → **Go**.
5. The confirmation page lists what will be deleted:
   - Member ID + email
   - Counts: souvenirs, cooptation requests, memoriam nominations, admin applications to anonymize, photos on Cloudinary.
6. **Type the member's email exactly** in the confirmation input. Submit is rejected on mismatch.
7. Click **Purger maintenant**. The page redirects back to the changelist with a green success banner showing how many members were purged.

**If a "Bloqué" message appears** instead of the deletion counts: the member has created In Memoriam fiches and we won't cascade-delete them silently. See [Edge case 1](#edge-case-1) below.

---

## Procedure B — CLI (recommended for scripted RGPD batch handling, or remote ops)

```bash
# 1. Always preview first
python manage.py rgpd_purge_member alice@example.com --dry-run

# 2. Execute with the interactive prompt (default)
python manage.py rgpd_purge_member alice@example.com

# 3. For non-interactive / scripted execution
python manage.py rgpd_purge_member alice@example.com --yes
```

Flags:

| Flag | Effect |
|---|---|
| `--dry-run` | Print the deletion plan; make no changes; never prompts. |
| `--yes` | Skip the interactive prompt. **Implies you've already done a dry run.** |
| `--member-id <N>` | Disambiguate when multiple members share the same email (rare). |
| `--actor <user_id>` | Record this user as the audit-log actor. Defaults to no actor (anonymous in the audit trail). |

The CLI prints a structured summary on success:

```
Purge complete:
  member_id              : 42
  email_hash             : 7a3b1c8e9d12
  memories               : 4
  cooptation_requests    : 1
  memoriam_nominations   : 0
  admin_apps_anonymized  : 1
  cloudinary_public_ids  : 5
  bucket_versions        : 5
  audit_log_id           : 119

structured: {"member_id": 42, "email_hash": "...", "deleted_counts": {...}, ...}
```

---

## What gets deleted (engine §C)

| Data | Action |
|---|---|
| Member row + linked User | Hard delete (cascade) |
| NotificationPreference, ConsentRecord | Hard delete (cascade) |
| Profile photo on Cloudinary + Tigris bucket | Hard delete (all versions) |
| Memories (Mur des souvenirs) authored by this member | Hard delete (rows + photos) |
| CooptationRequest rows where this member was parrain | Hard delete (the host AdminApplication is kept) |
| InMemoriamNomination rows submitted by this member | Hard delete (the linked fiche is kept) |
| Past AdminApplication rows with this member's email | Anonymized via `.purge()` (full_name/email/etc cleared, status=`purged`) |
| AuditLog entries about other things this member did | **Kept**, but `actor` becomes `NULL` (SET_NULL on the FK) |

**One canonical entry is appended to AuditLog** with action `rgpd.member.purged`, the deletion counts, and a 12-char SHA-1 of the email. No PII in the entry itself.

---

## Edge cases

### Edge case 1 — Member created In Memoriam fiches

`InMemoriamEntry.created_by` is a PROTECT FK to User. The engine refuses to cascade because the fiches are about **other people** (the deceased) and silently nulling that link would be a quiet data-quality regression.

**Resolution:**
1. Django admin → **In Memoriam → Fiches In Memoriam**.
2. Filter by **Created by** = the member being purged.
3. For each fiche: open it, change **Created by** to another super-admin (or to your own account), save.
4. Re-run the purge — it will succeed now.

### Edge case 2 — Self-purge attempt

The engine refuses if `actor.id == member.user.id`. **Ask another super-admin to run the procedure on your behalf.** (You'd lock yourself out mid-operation otherwise.)

### Edge case 3 — Multiple members share the email

Should never happen in practice (allauth enforces unique emails on User), but defensively: the CLI refuses with the matching IDs and asks you to re-run with `--member-id`. The admin UI selects by row, so this case doesn't apply there.

### Edge case 4 — Half-failed run (network, transient bucket failure)

The engine is idempotent end-to-end:
- External calls (Cloudinary delete, bucket delete_version) happen BEFORE the DB transaction. If they fail, the DB is untouched — re-run safely.
- DB mutations are inside `transaction.atomic()` — partial state is impossible.
- The AuditLog entry is the LAST step. **If you don't see an `rgpd.member.purged` audit entry, the operation didn't fully complete.** Re-run the same command; it will pick up where it left off.

### Edge case 5 — Verifying after the fact

Three things to check:

```python
# 1. AuditLog entry exists
from members.models import AuditLog
AuditLog.objects.filter(action="rgpd.member.purged").order_by("-created_at")[:5]
```

```bash
# 2. Tigris bucket no longer holds the member's profile photo (sample)
aws s3 ls "s3://media-backup-fissla9lsuj0/members/<their-slug-prefix>/" \
    --endpoint-url=https://t3.storageapi.dev
# expected: empty (or no objects under that prefix)
```

3. **Cloudinary dashboard** → Media Library → search for the public_id under `members/<slug>/`. Should return no results.

---

## RGPD reporting

For the requesting member's records (and for our compliance log if challenged), reply to their original email with:

> Bonjour,
>
> Conformément à votre demande au titre de l'article 17 du RGPD, nous avons procédé à la suppression définitive de votre compte et des données personnelles associées sur la plateforme Les Retrouvailles le {date}.
>
> Référence d'audit : `{audit_log_id}` (hash {email_hash}).
>
> Cordialement,
> {Admin signature}

The `audit_log_id` and `email_hash` come from the CLI/UI summary. They let a future investigator confirm the action without storing the original email.

---

## What's NOT in this procedure

- Self-service member-facing deletion flow (planned, not yet shipped — will call into the same engine).
- Granular content-handling choices (delete vs anonymize for gallery photos / témoignages — master spec §9.4 Phase B).
- AdminApplication 6-month retention auto-purge — separate cron, deferred.
- AuditLog 12-month retention auto-purge — separate cron, deferred.
- DMARC monitoring (P6c).
