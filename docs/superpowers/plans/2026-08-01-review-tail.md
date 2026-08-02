# Review-tail batch — combined spec + plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Executed inline in the same session that wrote it; findings verified against code before planning.

**Goal:** Close the medium/low tail of the 2026-08-01 full-codebase review (everything except the deliberately deferred items listed at the bottom), grouped into nine TDD'd commits on `fix/review-tail`.

**Architecture:** All surgical: email sends moved out of transactions, row locks on racy paths, guards on public forms, AuditLog coverage extended (one `members` migration for all new action choices), template/infra hygiene. No new models.

## Global Constraints

- French user copy / English code. One commit per group below. Suite count must grow (970 → ~1000).
- A behavior change ships with a test; pure hygiene (comments, dead code, infra files) ships with a source-text test only where regression is plausible.

---

### T1 `fix(cooptation+members): emails out of transactions` — review M-emails
- `cooptation/views.py::parrain_vouch_view`: move `send_cooptation_accepted/refused` AFTER the atomic block, try/except-log (pattern: `approve_application`). Test: monkeypatch send to raise → response still 302, response recorded.
- `members/views.py::removal_request_form_view`: wrap `send_removal_confirmation_pending` in try/except-log — a Resend outage 500ed after the rows committed, and a retry created a duplicate request. Test: raise in send → 302 to /retrait/merci/, single RemovalRequest.
- `members/views.py::removal_confirm_view`: same for the two post-execution notification emails. Test: raise → 200 confirmed page.

### T2 `fix(cooptation): lock the vouch/approve races` — review M3/M4
- `parrain_vouch_view` POST: inside the atomic block, `select_for_update()` all of the application's CooptationRequests before writing mine and computing `_resolve_outcome` from the locked rows — two near-simultaneous vouches could each see the other as pending, leaving the app stuck in `cooptation_pending` for up to 24h.
- `approve_application`: wrap `User.objects.create` in try/except `IntegrityError` → `ApprovalError` (TOCTOU between the exists() check and create; the loser used to 500 the gestion view). Test: pre-create the user between check bypass via monkeypatch — simpler: call approve twice concurrently is hard; instead create a user with username=email AFTER form of the check by patching the exists() to return False. Acceptable: monkeypatch `User.objects.filter(...).exists` is fragile — instead test that IntegrityError inside maps to ApprovalError by pre-creating the user and patching the guard method. Keep simple: extract `_email_collides()` helper? NO — simplest test: monkeypatch `approve_application.__globals__` is overkill. Test via mock: `mock.patch.object(User.objects, "create", side_effect=IntegrityError)`.

### T3 `fix(cooptation): admin action honesty` — review M5/L1/L2
- `message_user` override: catch only `MessageFailure` (was `except (TypeError, Exception): pass` — swallowed every warning).
- `reject_action`: drop the dead `request.POST.get("reason")` — no admin UI supplies it; explicit constant + comment pointing reasoned rejections at /gestion/.
- `resend_password_link_action`: look up by `username=app.email` first (approve creates username=email; email is mutable/non-unique), fall back to `email=` ordered by pk; add 0.5s pacing between sends (Resend 429).

### T4 `fix(cooptation): questionnaire + duplicate-signup guards` — review L3/L5
- `questionnaire_view`: all-blank POST re-renders with a French error instead of storing empty rows + flipping status. Zero active questions → flip to `awaiting_admin`, render done (the form used to stay live forever because the `responses.exists()` gate never engaged).
- `signup_view`: block a duplicate application — same email with an application already in `cooptation_pending`/`awaiting_admin` → form error «Une candidature avec cet email est déjà en cours.» (each dupe used to fan out 5 emails and start its own PII-retention clock).

### T5 `fix(cooptation): retention, digest idempotency, audit trail` — review M6/L4/L6/L7
- New `_purge_stale_undecided(now)` in the deadlines command: purge applications still `awaiting_admin` 180+ days after `submitted_at` (same `purge()` engine; rejected candidates get 180 days — undecided ones must not keep PII forever).
- Quarterly digest: replace `now.day == 1` with `now.day <= 7` + "no `ghost.digest.sent` AuditLog row this month" guard; write that row after a successful send. (Missed cron on the 1st used to skip a whole quarter; a double run double-sent.)
- AuditLog coverage: `cooptation.application.approved/rejected/purged` written from services; `ghost.digest.sent`; plus T8's `memoires.memory.deleted` / `memoriam.entry.deleted`. ONE migration in members for all new ACTION_CHOICES.
- `smoke_test_cooptation._cleanup`: run the parrain cleanup BEFORE the candidate SKIP early-return (SKIP used to strand SmokeParrain members visible in /annuaire/).

### T6 `fix(members): search escaping, import, claim/removal races` — review B-group
- `members/search.py`: escape `\`, `%`, `_` in tokens before `Value(token)` — Django does NOT escape LIKE wildcards in expression RHS, so `q=%` matched every member.
- `import_whatsapp_roster`: magic-links CSV opens in append mode (header only when new) — re-runs used to truncate links not yet DM'd.
- `import_whatsapp_roster`: `_upload_photo` moves out of the per-row transaction (photo failure warns instead of rolling back the created member; no more network I/O holding a transaction open).
- `services.unclaim_entry`: re-fetch under `select_for_update` (parity with `claim_entry`).
- `removal_confirm_view` POST: atomic + `select_for_update` on the RemovalRequest, re-check status inside (double-click sent 6 emails / 4 audit rows).
- `services.rgpd_purge_member`: make the "sessions" claim true — sweep the purged user's DB sessions (sessions aren't FK'd to User; the blob with `_auth_user_id` survived until natural expiry) and fix the comment.
- `create_member`: `filter().first()` instead of `get_or_create` on non-unique email; `full_clean()` before persistence.
- `photo_upload_view`: verify magic bytes via Pillow (`Image.open` + format in JPEG/PNG/WEBP) — the content-type check trusts a client header.
- Move the misplaced "suggestion chips" comment onto `DIRECTORY_EMPTY_STATE_SUGGESTIONS`.

### T7 `fix(gestion+core+aide): console/template hygiene` — review C-group
- `member_list.html` + `memory_list.html`: `{{ q|urlencode }}` in pagination/filter hrefs (a `&`/`#`/`%` in the search term silently mangled page-2 results).
- `member_login_link.html`: drop the dead `nonce=""`.
- `core/middleware.py`: `secrets.compare_digest` for basic-auth credentials.
- `core/views.py`: delete `landing_placeholder` (unrouted since P4; grep for template references first).
- `aide/index.html`: single-`blocktrans` guide link via `{% url ... as guide_url %}` (the string used to end mid-attribute).

### T8 `fix(memoriam+memoires): nomination quota, delete audit, upload guards` — review C-group
- `memoriam/views.py::nominate_view`: resolve the Member BEFORE `is_ratelimited(increment=True)`; no Member row → French error render (was: quota burned, then 404, typed form lost).
- `memoires/admin.py` + `memoriam/admin.py`: `delete_model`/`delete_queryset` write `memoires.memory.deleted` / `memoriam.entry.deleted` AuditLog rows with human-readable metadata (deleting a family-consented tribute is the most auditable act in these apps).
- Upload guards on both admin forms: ≤8 MB + content-type in JPEG/PNG/WebP (mirrors the gestion form).

### T9 `chore(infra): toolchain + repo hygiene` — review D-group
- Node 20 → 22 in `Dockerfile` and both `test.yml` jobs.
- `.dockerignore`: add `private-data/`, `*.xlsx`, and the six missing `*/tests/` dirs.
- Remove the vestigial `COPY DESIGN.md` layer.
- `prod.py:15` comment corrected (describes the actual LocMem→DatabaseCache swap).
- CI: `concurrency` + `timeout-minutes`, pip `cache-dependency-path: pyproject.toml`.
- `docker-compose.yml`: healthcheck on the app service.
- Delete the stray empty `5.2` file (shell-redirect artifact from the Django 5.2 upgrade commit).
- Report-only CSP: small middleware in `core/middleware.py` emitting `Content-Security-Policy-Report-Only` (self + Cloudinary images + the origins actually present in base.html), enabled in staging/prod. Report-only = zero breakage; flipping to enforce is a later decision once the owner's own browsing shows no violations.

### T10 Wrap-up
Full suite (two halves), lint, STATUS.md + CLAUDE.md count, merge `--no-ff`, push, watch the Railway deploy.

## Deferred, with reasons (not part of this batch)
- **Dependency lock**: a correct lock must be compiled for the Linux/py3.12 deploy platform (pip-tools in CI or a container), not from the Windows dev venv — it is its own small project, and doing it wrong pins Windows wheels.
- **bleach → nh3**: dependency swap on the sanitization path for user-visible content; needs its own test pass over every markdown surface.
- **Staff session absolute cap / CSP enforce mode**: product/rollout decisions for the owner.
- **Actions SHA-pinning + docker layer caching in CI**: nice-to-haves, low risk today.
- **H2 (email-only parrainage)**: product decision, already surfaced.
- **`docs/archives/*.docx` content eyeball**: owner action (repo is public).
