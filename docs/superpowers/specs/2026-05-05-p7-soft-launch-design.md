# P7 — Soft Launch (design + plan, combined)

**Status:** Approved.
**Phase:** P7 — Soft launch readiness for the existing ~200-member CEG1 Birni WhatsApp community.

## Goal

Give the operator the tools to onboard the existing WhatsApp roster onto the platform safely, at their own pace, and ship a `v1.0.0-soft-launch` milestone tag. The platform is feature-complete from earlier phases; P7 is the **launch enabler**, not feature work.

## Audience reality

The platform's user base is the existing Niger CEG1 Birni alumni WhatsApp group (~200 members, ages ~55-65). About **15-20% have a usable email address**; the remaining 80%+ identify primarily by WhatsApp number. Email-required auth would force us to fake addresses for the majority — a privacy and UX mess. The dominant onboarding path is therefore "admin generates a magic-link URL → admin shares it via WhatsApp DM → member sets a password and logs in."

## Non-goals

- **Member self-service onboarding flow.** Trusted WhatsApp members are admin-imported. Public cooptation flow (P3) remains the path for outside candidates post-launch.
- **SMS / WhatsApp-API magic-link automation.** Manual admin-to-WhatsApp sharing is fine at this scale (one-time onboarding, occasional password resets). Automation is a Phase 2 idea.
- **Phase 2 features.** No member-uploaded gallery, no map, no In Memoriam open submissions.
- **Bringing the platform online.** Already live on Railway. P7 is the rollout, not the deploy.

## Architecture (§A)

### A.1 — Auth: phone OR email

Migrate allauth from email-only auth to "username or email" auth, with username = WhatsApp digits-only. Use the new (non-deprecated) settings API while we're touching this — eliminates the 3 deprecation warnings we see in cron logs today.

```python
# alumni/settings/base.py — new
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email", "password1*", "password2*"]
# remove deprecated ACCOUNT_AUTHENTICATION_METHOD,
# ACCOUNT_EMAIL_REQUIRED, ACCOUNT_USERNAME_REQUIRED
```

`User.username` for imported members = WhatsApp number, digits only (e.g. `+22790000001` → `22790000001`). Phone is always present (CSV makes it required); email is optional.

Login template label: `"Email"` → `"Numéro WhatsApp ou email"`. Single text input accepts both. The autocomplete attribute stays `username` (allauth handles email lookup transparently).

### A.2 — Bulk import: `import_whatsapp_roster <csv>`

Reads a CSV (operator-prepared from the WhatsApp roster). Per row:

1. **Validate** — phone format (E.164 with `+`), year range (1980-1985), class pattern, required fields.
2. **Resolve photo** — if `photo_filename` is set, look for the file in `roster_photos/`; warn and skip-the-photo if missing (don't skip the member).
3. **Create User** — `username = phone digits`, `email = csv email or ""`. Random password (will be replaced by member). Allauth `EmailAddress` row only created if email is set, marked unverified.
4. **Create Member** — first_name, last_name, nickname, years_attended, classes, city, country, profession.
5. **Photo upload** — if a photo file was found, upload to Cloudinary at folder `members/<slug>/`; set `member.photo_public_id` to the returned ID.
6. **Send activation:**
   - **Email path** (member has email): use existing allauth `password_reset` to send a French-styled password-set email via Resend. Same flow as P3 cooptation approval.
   - **No-email path** (no email): generate the same signed key URL allauth would have emailed, but **don't send it**; write it to `magic_links.csv` for the operator.

After processing all rows, print a summary table and a final `magic_links.csv` location.

**Idempotency:** skip rows where `User.username` (= phone) already exists. Print a notice but don't fail. Lets the operator re-run after fixing typos.

**Flags:**
- `--dry-run` — validate everything; don't create users, don't send emails.
- `--no-emails` — create accounts; don't send any emails (writes a `welcome_emails.csv` with what would have gone out, for later batch send).
- `--limit N` — process only first N valid rows.
- `--csv path/to/file.csv` (default: positional arg).

### A.3 — `reissue_login_link <phone>`

For email-less members who forget their password (steady-state need, since we can't email them a reset link):

```bash
python manage.py reissue_login_link 22790000001
```

Looks up User by username, generates a fresh signed key URL, prints it. Operator copies to WhatsApp DM. No flags; idempotent (calling repeatedly issues new URLs that all work until either is consumed).

### A.4 — `audit_launch_readiness`

Single command operator runs before announcing the platform widely:

```
python manage.py audit_launch_readiness
```

Prints a checklist with current values vs. master-spec minimums:

| Check | Target | Current | Status |
|---|---|---|---|
| Active members | ≥ 1 (post-import: ~200) | 1 | ⚠ run import |
| Memory rows (Mur des souvenirs) | 10-20 | 0 | ⚠ admin needs to add |
| InMemoriamEntry published | 1-3 | 0 | ⚠ admin needs to add |
| PublicSearchEntry published | ≥ 3 | 0 | ⚠ admin needs to add |
| DMARC TXT record present | yes | dig … | ✓ / ⚠ |
| Last `backup_media` cron run | < 8 days ago | … | (manual check) |
| `BASIC_AUTH_REQUIRED` env | false | (manual; see runbook) | (manual check) |

Pure informational — never mutates anything. Exit 0 always; the warnings are advisory.

### A.5 — Tag `v1.0.0-soft-launch`

After the merge lands, tag the milestone. Resumes the convention from `v0.4.0c-public-surface-admin` (the last tag before the team switched to direct merges).

## Files (§H)

### Create

- `members/management/commands/import_whatsapp_roster.py`
- `members/management/commands/reissue_login_link.py`
- `members/management/commands/audit_launch_readiness.py`
- `members/tests/test_import_whatsapp_roster.py`
- `members/tests/test_reissue_login_link.py`
- `members/tests/test_audit_launch_readiness.py`
- `members/tests/test_username_login.py` (covers the auth-flip)
- `docs/runbooks/launch.md`
- `docs/runbooks/onboarding.md`
- `docs/runbooks/roster_template.csv` (the actual CSV template operator copies)

### Modify

- `alumni/settings/base.py` — replace deprecated allauth settings with `ACCOUNT_LOGIN_METHODS` + `ACCOUNT_SIGNUP_FIELDS`
- `templates/account/login.html` — label tweak
- `docs/superpowers/STATUS.md` — mark P7 complete, mark P6 / earlier as v1.0 baseline

### Optional polish (only if testing reveals it's needed)

- `templates/account/password_set.html` — verify it makes sense for the "first time setting password" case (vs. the existing post-cooptation case)

## Tests (§G)

| File | Count | Coverage |
|---|---|---|
| `test_username_login.py` | 3 | Login by email works; login by username (phone) works; settings are migrated to new keys (no deprecated values). |
| `test_import_whatsapp_roster.py` | 6 | Dry-run; happy path with both email and no-email rows; photo upload happens for rows with photo_filename; idempotency (skips existing username); validation rejects bad year/class; `magic_links.csv` written for no-email rows. |
| `test_reissue_login_link.py` | 2 | Generates URL for known username; refuses with helpful message for unknown. |
| `test_audit_launch_readiness.py` | 2 | Prints all sections; flags below-threshold items. |

Total: 13 new tests. Target full suite: 479 (current) + 13 = 492 passing.

## Operator-side (NOT in code, in runbooks)

The launch runbook (`docs/runbooks/launch.md`) walks the operator through:

1. **Step 0 — DB cleanup.** Inspect existing 6 seed Members → create new super admin via `createsuperuser` → delete seed Members via Django admin (cascades cleanly). Optional bucket cleanup for the 2 orphaned test photos.
2. **Step 1 — Pre-launch checklist:** `BASIC_AUTH_REQUIRED=false` (already done), DMARC verification (per `dmarc.md`), backup health (last `backup_media` cron run), `audit_launch_readiness` clean.
3. **Step 2 — Roster collection:** Google Form (or in-WhatsApp poll) to collect each member's name, years/classes, city, country, profession, optional email, optional WhatsApp profile photo. Dedupe + validate manually.
4. **Step 3 — CSV preparation:** fill `roster_template.csv`; place collected photos in `roster_photos/`.
5. **Step 4 — Dry-run import:** `python manage.py import_whatsapp_roster roster.csv --dry-run`. Fix any errors in the CSV.
6. **Step 5 — Pilot batch (5-10 members):** import a `pilot.csv` first; share magic links with pilots; ask for feedback.
7. **Step 6 — Full batch:** import the rest after the pilot signs off.
8. **Step 7 — WhatsApp announcement:** post the platform URL to the WhatsApp group with the announcement template.
9. **Step 8 — First-week monitoring:** member-count growth, error rate in Railway logs, member-reported issues.
10. **Step 9 — Steady state:** quarterly DMARC review, quarterly bucket-size check, quarterly restore drill.

The onboarding runbook (`docs/runbooks/onboarding.md`) holds the CSV column reference and the WhatsApp DM templates (welcome message for email-path members, magic-link share for no-email-path, password-reset share).

## Reasoning §A — why phone-or-email instead of phone-only

We could have switched fully to username-only auth (`ACCOUNT_LOGIN_METHODS = {"username"}`) and not bothered with email. But the 15-20% who DO have email expect email-based recovery flows — they'd find "you can't reset your password without messaging the admin" worse than the current state. And the cost of supporting both methods in allauth is essentially zero (just changing a set literal).

So: phone is the universal primary; email is a bonus for those who have one, surfacing the standard reset email flow as a quality-of-life upgrade.

## Risks (§J)

| Risk | Mitigation |
|---|---|
| Magic-link URLs leak (forwarded screenshot, etc.) | Allauth's signed keys expire after 7 days (already configured by P3's PASSWORD_RESET_TIMEOUT). Operator can re-issue at will via `reissue_login_link`. |
| Member loses their phone number | Admin updates `User.username` via Django admin to the new number. Has to be done manually; a future "phone change" admin action could automate. |
| 200 password-set emails hit Resend's daily limit (100/day on free tier) | Use `--no-emails` flag; spread sends over 2-3 days via a follow-up `send_pending_welcome_emails --batch=80` (deferred — can build if it actually becomes a problem). |
| Operator messes up the CSV (wrong years for someone) | `--dry-run` validates everything before any DB write. Idempotent re-runs let you fix mistakes individually. Worst case: the existing P6b RGPD purge undoes a wrongly-imported row cleanly. |
| Django/allauth deprecation warnings still appear | This phase migrates to the new settings format; the warnings should be gone. If new ones appear after the upgrade, those are a separate issue. |

---

## Tasks

- [ ] **Task 1**: Allauth settings flip + login template + 3 tests
- [ ] **Task 2**: `import_whatsapp_roster` command + 6 tests
- [ ] **Task 3**: `reissue_login_link` helper + 2 tests
- [ ] **Task 4**: `audit_launch_readiness` command + 2 tests
- [ ] **Task 5**: Launch runbook + onboarding runbook + CSV template
- [ ] **Task 6**: STATUS update; merge; tag `v1.0.0-soft-launch`
