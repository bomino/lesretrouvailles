# Project Status

**Project:** Les Retrouvailles — CEG1 Birni alumni platform
**Spec:** [specs/2026-05-01-alumni-platform-design.md](specs/2026-05-01-alumni-platform-design.md)

Single dashboard for tracking phase and task completion across all plans. Update when a plan is written, when a task ships, and when a phase ships.

## Phase Index

| Phase | Title | Status | Plan |
|-------|-------|--------|------|
| P1 | Foundation | Complete (tag `v0.1.0-foundation`, 2026-05-02) | [plan](plans/2026-05-01-foundation.md) |
| P2 | Membership | Complete (tag `v0.2.0-membership`, 2026-05-02) | [plan](plans/2026-05-02-membership.md) |
| P3 | Cooptation | Complete (tag `v0.3.0-cooptation`, 2026-05-02) | [plan](plans/2026-05-02-cooptation.md) |
| P4a | Public surface — landing + ghost-list scaffold + SEO | Complete (tag `v0.4.0a-public-surface`, 2026-05-03) | [plan](plans/2026-05-03-public-surface.md) |
| P4b | Public surface — token-based removal flow + AuditLog (governance UI deferred to P4c) | Complete (tag `v0.4.0b-public-surface-governance`, 2026-05-03) | [plan](plans/2026-05-03-public-surface-governance.md) |
| P4c | Public surface — quarterly review automation + admin status filter | Complete (tag `v0.4.0c-public-surface-admin`, 2026-05-03) | [plan](plans/2026-05-03-public-surface-admin.md) |
| P4d | Public surface — magazine cards + single-admin governance | Complete (2026-05-03) | [plan](plans/2026-05-03-magazine-cards-single-admin.md) |
| P3.1 | Parrain UX Polish (pending-vouches dashboard + 90-day session) | Complete (2026-05-03) | [plan](plans/2026-05-03-parrain-ux-polish.md) |
| P5a | Mur des souvenirs (member-only photo gallery) | Complete (2026-05-03) | [plan](plans/2026-05-03-mur-souvenirs.md) |
| Allauth styling | Allauth template overrides (full /accounts/* visual coverage) | Complete (2026-05-04) | [plan](plans/2026-05-04-styled-allauth-templates.md) |
| P5b | In Memoriam (member-only fiches + nomination form) | Complete (2026-05-04) | [plan](plans/2026-05-04-in-memoriam.md) |
| P5 | Mémoire seed | Complete (P5a + P5b shipped 2026-05-04) | — |
| P6a | Ops — media backup (Cloudinary→Railway bucket) | Complete (2026-05-05) | [plan](plans/2026-05-04-media-backup.md) |
| P6b | Ops — RGPD admin purge | Complete (2026-05-05) | [plan](plans/2026-05-05-rgpd-admin-purge.md) |
| P6c | Ops — DMARC monitoring + AuditLog retention | Complete (2026-05-05) | [spec](specs/2026-05-05-p6c-dmarc-retention-design.md) |
| P6 | Ops & RGPD | Complete (P6a + P6b + P6c shipped 2026-05-05) | — |
| P7 | Soft launch (auth flip + bulk-import tooling + launch runbooks) | Complete (tag `v1.0.0-soft-launch`, 2026-05-05) | [spec](specs/2026-05-05-p7-soft-launch-design.md) |

---

## P1 — Foundation

**Shipped:** 2026-05-02 (merged into `main`, tag `v0.1.0-foundation`)
**Plan:** [plans/2026-05-01-foundation.md](plans/2026-05-01-foundation.md)
**Test suite:** 19/19 passing (smoke, health, base template, i18n, design tokens, auth, static assets, basic-auth)

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Repo skeleton and Python project metadata | [x] | `69d411d` |
| 2 | Postgres via Docker Compose | [x] | `2d6f1f1` |
| 3 | Django project scaffold with split settings | [x] | `7bb7089` |
| 4 | pytest setup with first passing test | [x] | `dc06c67` |
| 5 | Health check endpoint with database probe | [x] | `8fcba59` |
| 6 | Tailwind + DaisyUI build pipeline | [x] | `1f98116` |
| 6.5 | DESIGN.md and Tailwind theme export | [x] | `42a093f` |
| 7 | Vendor HTMX and base template with a11y baseline | [x] | `8c9f3ba` |
| 8 | i18n machinery for French (Hausa-ready) | [x] | `f00cd06` |
| 9 | Allauth integration (login only, signup disabled) | [x] | `af58eda` |
| 10 | Pre-commit hooks | [x] | `1c41d1c` |
| 11 | GitHub Actions CI | [x] | `5cf4f88` |
| 12 | Makefile for common dev commands | [x] | `0644c88` |
| 13 | Compiled CSS wired into Django static pipeline | [x] | `8f391dd` |
| 14 | Staging environment hardening (basic-auth) | [x] | `4e8c241` |
| 15 | Final verification — full test suite green | [x] | `203282a` |

---

## P2 — Membership

**Shipped:** 2026-05-02 (branch `feat/membership`, tag `v0.2.0-membership`)
**Plan:** [plans/2026-05-02-membership.md](plans/2026-05-02-membership.md)
**Spec:** [specs/2026-05-02-membership-design.md](specs/2026-05-02-membership-design.md)
**Test suite:** 128 passing (19 P1 + 109 new in `members/`)

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Scaffold members app + add P2 dependencies | [x] | `0d56289` (+ `be6f0f3` review nits) |
| 2 | Cloudinary client with fake adapter and lazy URL builder | [x] | `69897f7` |
| 3 | Cloudinary env vars and ratelimit cache config | [x] | `bb59314` |
| 4 | Member model with split name, array fields, soft-delete status | [x] | `1a249aa` |
| 5 | NotificationPreference with GDPR-safe defaults and auto-create signal | [x] | `0c3fb25` |
| 6 | Append-only ConsentRecord model | [x] | `c59605b` |
| 7 | Postgres unaccent extension, functional indexes, CHECK constraints | [x] | `01033dc` |
| 8 | Admin registrations for Member, NotificationPreference, ConsentRecord | [x] | `9be9a65` |
| 9 | Versioned charter package with v1.0 French content | [x] | `3cd8c79` |
| 10 | LoginRequiredMiddleware with public-paths whitelist | [x] | `e661abd` |
| 11 | ConsentRequiredMiddleware with session caching | [x] | `cf22cb7` |
| 12 | CharterView with markdown render and consent capture | [x] | `1aac593` |
| 13 | member_avatar template tag with initials fallback | [x] | `6ae5773` |
| 14 | Context processor exposing member_prefs to templates | [x] | `2cd2296` |
| 15 | ProfileDetailView with status gating and privacy toggles | [x] | `a9853f3` |
| 16 | ProfileEditView with locked fields and notification preferences form | [x] | `dbe5780` |
| 17 | Rate-limited cloudinary sign endpoint with folder pinning | [x] | `99a9494` |
| 18 | Cloudinary photo persistence with folder validation and old-photo cleanup | [x] | `5e76a77` |
| 19 | DirectoryView with pagination and HTMX-aware partial | [x] | `5863559` |
| 20 | Accent-insensitive search and filters in directory | [x] | `4e11651` |
| 21 | HTMX partial behavior tests | [x] | `2f1ec75` |
| 22 | create_member management command for dev seeding | [x] | `d0ee077` |
| 23 | Seed fixture with 6 representative members | [x] | `a1bc809` |
| 24 | French translations generated and compiled | [x] | `8c233cb` |
| 25 | a11y baseline assertions (label, aria-live, aria-label) | [x] | `b02d422` |

---

## P3 — Cooptation

**Shipped:** 2026-05-02 (branch `feat/cooptation`, tag `v0.3.0-cooptation`)
**Plan:** [plans/2026-05-02-cooptation.md](plans/2026-05-02-cooptation.md)
**Spec:** [specs/2026-05-02-cooptation-design.md](specs/2026-05-02-cooptation-design.md)
**Test suite:** 217 passing total

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Scaffold cooptation app + P3 deps | [x] | `6b49649` |
| 2 | Resend backend + send_email helper | [x] | `d309b98` |
| 3 | AdminApplication model with 5-state machine + purge() | [x] | `96be728` |
| 4 | CooptationRequest with token + parrain PROTECT | [x] | `89d57de` |
| 5 | KnowledgeQuestion + QuestionnaireResponse | [x] | `f51bbc6` |
| 6 | seed_questions management command | [x] | `ac436cb` |
| 7 | 10 email templates + emails.py wrappers | [x] | `a639a9f` |
| 8 | services.py approve/reject/purge with Allauth URL | [x] | `cc63e13` |
| 9 | Public signup form, view, success page | [x] | `b32b4bb` (+ `ecdd3c4` cache fix) |
| 10 | Parrain vouch view with identity check + 410 pages | [x] | `81a4097` |
| 11 | Questionnaire view with accent-insensitive auto-grading | [x] | `43cbe29` |
| 12 | Admin moderation UI with custom actions | [x] | `4f2998a` |
| 13 | process_cooptation_deadlines cron command | [x] | `79ed951` |
| 14 | a11y + e2e happy path tests | [x] | `541e99a` |
| 15 | Settings, runbook, STATUS.md, tag | [x] | `<this commit>` |

---

## P4a — Public surface (landing + ghost-list scaffold + SEO)

**Shipped:** 2026-05-03 (branch `feat/public-surface`, tag `v0.4.0a-public-surface`)
**Plan:** [plans/2026-05-03-public-surface.md](plans/2026-05-03-public-surface.md)
**Spec:** [specs/2026-05-03-public-surface-design.md](specs/2026-05-03-public-surface-design.md)
**Test suite:** 286 passing (234 from prior phases + 52 new across noindex audit, a11y, SEO, UTM, ghost-list model, basic-auth bypass, and landing view).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Settings — `PUBLIC_GHOST_LIST_ENABLED`, `CLOUDFLARE_ANALYTICS_TOKEN`, sitemap/robots whitelist | [x] | `e49c6be` (+ `48e4c6f` `.env.example`) |
| 2 | `PublicSearchEntry` model + migration + 7 model tests | [x] | `393fcca` |
| 3 | `AdminApplication` UTM fields + admin filter + purge() guard | [x] | `353b002` |
| 4 | `BasicAuthMiddleware` bypass for public paths (exact-match + prefix) | [x] | `4ac680b` |
| 5 | UTM capture in `signup_view` (sanitization + session stash) | [x] | `a3b3742` |
| 6 | `/sitemap.xml` exposing landing + inscription only | [x] | `41e3186` |
| 7 | `/robots.txt` with explicit allow/disallow + sitemap reference | [x] | `484fbaa` |
| 8 | `PublicSearchEntry` admin registration with 2-cosigner UX | [x] | `860f212` |
| 9 | Landing view + template (hero, ghost section, OG/JSON-LD, namespaced URLs, year sort) | [x] | `0615459` |
| 10 | Cloudflare Web Analytics beacon (anonymous-only, env-gated) | [x] | `7a0a3fc` |
| 11 | Noindex audit + landing a11y assertions (5+4 tests) | [x] | `505a82f` |
| 12 | Full suite + smoke + STATUS update | [x] | _this commit_ |
| 13 | Merge, tag, push, deploy | _next commit_ | _pending_ |

**Notable design decisions:**
- Ghost list section is gated by env-var feature flag `PUBLIC_GHOST_LIST_ENABLED` (default off). RGPD safety net so admin signoffs can't accidentally publish names before P4b's removal flow ships.
- Two-admin M2M publication gate enforced at queryset level (no single-toggle boolean).
- UTM fields kept on `AdminApplication` after `purge()` (aggregate labels with no PII); `referrer` cleared (group-invite URLs leak membership).
- `protocol = "https"` hardcoded on the sitemap class to force https://-prefixed URLs even when Django receives the request over plain HTTP behind Railway's TLS proxy.
- Open Graph image at `static/img/og-landing.png` is a 1×1 placeholder; replace with a real 1200×630 PNG before deploy.
- Narrative copy in the landing template is the implementer's first-draft placeholder; team to refine before deploy.

---

## P4b — Public surface (token-based removal flow + AuditLog)

**Shipped:** 2026-05-03 (branch `feat/public-surface-governance`, tag `v0.4.0b-public-surface-governance`)
**Plan:** [plans/2026-05-03-public-surface-governance.md](plans/2026-05-03-public-surface-governance.md)
**Spec:** [specs/2026-05-03-public-surface-governance-design.md](specs/2026-05-03-public-surface-governance-design.md)
**Test suite:** 324 passing (286 from prior phases + 38 new across audit log, removal request, signals, view, email, landing template tests).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Whitelist /retrait/ for login + basic-auth bypass | [x] | `8efdf41` |
| 2 | AuditLog model + migration + tests | [x] | `3f009ff` |
| 3 | RemovalRequest model + tighten removal_token + tests | [x] | `e390cc1` |
| 4 | Audit signal handlers (entry create, signoff M2M, request cancel) | [x] | `4eecfc4` |
| 5 | 3 removal-flow email templates + senders | [x] | `bbdaebb` |
| 6 | Public removal request form view + done page | [x] | `968722d` |
| 7 | Removal confirmation view (idempotent auto-execute) + expired page | [x] | `61fde34` |
| 8 | RemovalRequestAdmin + AuditLogAdmin (append-only) | [x] | `d4e58e3` |
| 9 | Landing template "Retirer mon nom" link in each ghost card | [x] | `d5f1f72` |
| 10 | Full suite + STATUS update | [x] | _this commit_ |
| 11 | Merge, tag, push, deploy | _next commit_ | _pending_ |

**Notable design decisions:**
- "sans débat" interpretation: auto-execute on email confirmation. No admin gatekeeping.
- 30-day expiry on RemovalRequest aligns with GDPR Art. 12's one-month response window.
- AuditLog populated automatically via Django signals so adding a new way to sign off / remove an entry doesn't require remembering to write to AuditLog.
- P3 cooptation actions are NOT retrofitted into AuditLog — domain audit fields stay where they are.
- Custom admin governance UI and quarterly review automation deferred to P4c.

---

## P4c — Public surface (quarterly review automation + admin status filter)

**Shipped:** 2026-05-03 (branch `feat/public-surface-admin`, tag `v0.4.0c-public-surface-admin`)
**Plan:** [plans/2026-05-03-public-surface-admin.md](plans/2026-05-03-public-surface-admin.md)
**Spec:** [specs/2026-05-03-public-surface-admin-design.md](specs/2026-05-03-public-surface-admin-design.md)
**Test suite:** 336 passing (324 from prior phases + 12 new across cron handler, quarterly digest, and admin filter tests).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Stale-ghost auto-removal handler in daily cron | [x] | `21d3f26` |
| 2 | Quarterly admin digest — handler + email + 3 templates | [x] | `ce68eda` |
| 3 | GhostStatusFilter on PublicSearchEntryAdmin (5 buckets) | [x] | `5a97670` |
| 4 | Full suite + STATUS update | [x] | _this commit_ |
| 5 | Merge, tag, push, deploy | _next commit_ | _pending_ |

**Notable design decisions:**
- Master spec's "Revue trimestrielle" honored as a **quarterly digest** (Jan/Apr/Jul/Oct day 1) — auto-removal itself fires daily so entries never stay public >12 months + 1 day, but the human-facing review cadence is quarterly.
- 12-month boundary uses `added_at` rather than a "first published" date — slightly conservative for entries that took weeks to cosign, but no schema change. P4d adds `published_at` if admins find it annoying.
- New cron handler lives in the existing `process_cooptation_deadlines` command despite the naming mismatch — the cross-app housekeeping is documented in the module docstring.
- `GhostStatusFilter` uses `Count("added_by_admins")` annotation only when a filter value is selected; default changelist load is unaffected. The "published" bucket excludes entries ≥365 days old (filtered into "stale") — strict partition, no overlap.
- `PublicSearchEntryAdmin.list_display` now uses a custom `retrait_at` method (label: "Retiré le") instead of the raw `removed_at` field — more on-brand French + sidesteps a brittle test-vs-column-header collision.
- "Custom admin dashboard view" deferred indefinitely — list filter + quarterly digest cover the operational need at our scale.

---

## P4d — Magazine cards + single-admin governance

**Shipped:** 2026-05-03
**Plan:** [plans/2026-05-03-magazine-cards-single-admin.md](plans/2026-05-03-magazine-cards-single-admin.md)
**Spec:** [specs/2026-05-03-magazine-cards-single-admin-design.md](specs/2026-05-03-magazine-cards-single-admin-design.md)
**Test suite:** all passing

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Drop 2-signoff publication gate | [x] | `eab44fd` (+ purge fix `2e6a85d`) |
| 2 | Magazine ghost cards (monogram + accent + warm chrome) | [x] | `a2de38b` (+ a11y fix `cc450cc`) |
| 3 | admin_ghost_added FYI email infrastructure | [x] | `d508c92` |
| 4 | Admin save_model — auto-cosign + fire notification | [x] | `ce1a79b` (+ test fix `ca3225b`, plan correction `89b7120`) |
| 5 | GhostStatusFilter cleanup (5 → 3 buckets) | [x] | `8072d0f` (+ docstring fix `48f3b81`) |
| 6 | STATUS.md update | [x] | (this commit) |

---

## P3.1 — Parrain UX Polish

**Shipped:** 2026-05-03
**Plan:** [plans/2026-05-03-parrain-ux-polish.md](plans/2026-05-03-parrain-ux-polish.md)
**Spec:** [specs/2026-05-03-parrain-ux-polish-design.md](specs/2026-05-03-parrain-ux-polish-design.md)
**Test suite:** all passing

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | 90-day sliding session lifetime | [x] | `104b570` |
| 2 | Pending-vouches dashboard view + URL + template | [x] | `c057b76` |
| 3 | `pending_vouches_count` context processor | [x] | `8e387f8` |
| 4 | Nav link + badge in `base.html` (desktop + mobile) | [x] | `c5bd0e0` |
| 5 | STATUS.md update | [x] | (this commit) |

---

## P5a — Mur des souvenirs

**Shipped:** 2026-05-03
**Plan:** [plans/2026-05-03-mur-souvenirs.md](plans/2026-05-03-mur-souvenirs.md)
**Spec:** [specs/2026-05-03-mur-souvenirs-design.md](specs/2026-05-03-mur-souvenirs-design.md)
**Test suite:** all passing (~18 new tests across alumni/test_cloudinary_extensions and memoires/tests/*)

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Cloudinary client extension (upload_file + URL helpers) | [x] | `231a020` |
| 2 | Scaffold memoires app + Memory model + migration | [x] | `cf2cdd7` |
| 3 | Gallery view + URL + template + memory_photo tags | [x] | `d188d35` |
| 4 | Detail view + template | [x] | `c61304b` |
| 5 | Admin (form + save_model + Cloudinary upload) | [x] | `fae5202` (+ review fix `453215c`) |
| 6 | Nav link in base.html (desktop + mobile) | [x] | `140084d` |
| 7 | STATUS.md update | [x] | `b30179a` |

---

## Allauth template styling

**Shipped:** 2026-05-04
**Plan:** [plans/2026-05-04-styled-allauth-templates.md](plans/2026-05-04-styled-allauth-templates.md)
**Spec:** [specs/2026-05-04-styled-allauth-templates-design.md](specs/2026-05-04-styled-allauth-templates-design.md)
**Test suite:** all passing (18 new tests in core/tests/test_allauth_templates.py; full suite 405 passing)

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Shared partials (_input + _form_card) + smoke tests | [x] | `28a32d6` (+ fix `ea68e61`) |
| 2 | Password-reset request flow (2 templates) | [x] | `e29f0fb` |
| 3 | Password-reset-from-key flow (2 templates incl. token_fail) | [x] | `143145f` |
| 4 | Logged-in password mgmt (2 templates) | [x] | `0fac2e4` |
| 5 | Email management (4 templates) | [x] | `c67c97d` |
| 6 | Edge-case templates (3 templates) | [x] | `ea1c362` |
| 7 | Signup resilience override + negative POST test | [x] | `4f52539` |
| 8 | STATUS.md update | [x] | (this commit) |

---

## P5 — Mémoire seed

**Status:** Not started.
**Scope:** `Memory` model, Mur des souvenirs admin-only gallery, `InMemoriamEntry`, In Memoriam seed page.
**Plan:** not yet written.

---

## P6 — Ops & RGPD

**Status:** Complete (P6a + P6b + P6c shipped 2026-05-05).
**Scope shipped:** Media backup (P6a), RGPD admin-driven purge (P6b), AuditLog 12-month retention + DMARC monitoring runbook (P6c). AdminApplication 6-month auto-purge cron was already shipped in P3 (`process_cooptation_deadlines._purge_old_rejections`).
**Plans:** P6a [plan](plans/2026-05-04-media-backup.md); P6b [plan](plans/2026-05-05-rgpd-admin-purge.md); P6c [spec](specs/2026-05-05-p6c-dmarc-retention-design.md).
**Acknowledged gap:** Master spec §8.2 specifies media-backup retention via a 30-day rotation. Tigris on Railway does not support `PutBucketLifecycleConfiguration` with non-trivial rules (P6a discovery, runbook §1.2). The 30-day rotation is therefore not enforced today. Path-dedup keeps the bucket small (~500 MB peak at our scale); manual cleanup is the operational alternative. Revisit when Tigris adds support, or when scale forces a move to a different S3-compatible target.

---

## P7 — Soft launch

**Shipped:** 2026-05-05 (tag `v1.0.0-soft-launch`).
**Spec (combined design + plan):** [specs/2026-05-05-p7-soft-launch-design.md](specs/2026-05-05-p7-soft-launch-design.md)
**Test suite:** 492 passing total (13 new tests across `members/tests/test_username_login.py`, `test_import_whatsapp_roster.py`, `test_reissue_login_link.py`, `test_audit_launch_readiness.py`).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Allauth phone-or-email auth + new settings API | [x] | `8f8b8aa` |
| 2 | `import_whatsapp_roster` bulk-import command | [x] | `d54eba7` |
| 3 + 4 | `reissue_login_link` + `audit_launch_readiness` | [x] | `3203521` |
| 5 | Launch + onboarding runbooks + CSV template | [x] | `4185b90` |
| 6 | STATUS update + tag `v1.0.0-soft-launch` | [x] | _this commit_ |

**Notable design decisions:**
- **Phone-or-email login, not phone-only.** With ~80% of the cohort email-less, phone (WhatsApp digits) is the universal identifier; the 15-20% with email keep the standard email-based recovery flow they expect. New allauth settings API (`ACCOUNT_LOGIN_METHODS = {"email", "username"}`) replaces the deprecated trio — drops the 3 deprecation warnings cron logs were emitting on every startup.
- **Two onboarding paths from one CSV.** Email-bearing rows go through the standard Resend password-set email; email-less rows get a magic-link URL written to `magic_links.csv` for the operator to copy-paste into a WhatsApp DM. Reuses cooptation's `_build_password_set_url()` so both paths produce allauth-compatible signed URLs.
- **`reissue_login_link` for steady-state password resets.** The dominant path (no email) means the standard email-based password-reset flow doesn't work for most members. Pattern: member messages admin via WhatsApp; admin re-issues; admin shares URL via WhatsApp DM. One-line CLI command.
- **No member self-service deletion or onboarding.** The cooptation flow (P3) remains for outside candidates; existing-WhatsApp-member self-service is deferred (P6b's RGPD purge engine is the building block when that flow ships).
- **Pre-launch DB cleanup is operator-driven, not code.** Launch runbook Step 0 walks the operator through `createsuperuser` → manual deletion via Django admin → optional bucket cleanup. Avoids a one-shot management command that would never be reused after launch.
- **Photo upload during import is best-effort.** A failed photo upload doesn't fail the row; the member is created without a photo and can upload their own via Profile → Modifier later. Most of the 200 members won't have a pre-loaded photo anyway.

---

## P5b — In Memoriam

**Shipped:** 2026-05-04
**Plan:** [plans/2026-05-04-in-memoriam.md](plans/2026-05-04-in-memoriam.md)
**Spec:** [specs/2026-05-04-in-memoriam-design.md](specs/2026-05-04-in-memoriam-design.md)
**Test suite:** 445 passing total (37 new memoriam tests across `memoriam/tests/*` and `core/tests/test_settings_memoriam.py`).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Scaffold memoriam app + Dockerfile + INSTALLED_APPS | [x] | `5adf1f0` (+ review nits `53efe97`) |
| 2 | Extend AuditLog ACTION_CHOICES with memoriam.* actions | [x] | `0e6b231` |
| 3 | InMemoriamEntry model with clean() + queryset method | [x] | `dfc889e` (+ DRY fix `79fa6ff`) |
| 4 | InMemoriamNomination model | [x] | `b4c6343` |
| 5 | Settings + context processor (MEMORIAM_CONTACT_EMAIL) | [x] | `8ada59f` |
| 6 | InMemoriamEntryAdmin with full save_model logic | [x] | `b5874c2` (+ cleanup `bdad459`) |
| 7 | InMemoriamNominationAdmin (no manual add) | [x] | `8289912` |
| 8 | AuditLog signal handlers | [x] | `aa9fcd1` |
| 9 | Email senders + 6 templates | [x] | `fdd1cc9` |
| 10 | List + Detail views with templates | [x] | `e5f8ce8` |
| 11 | Nomination form + view + rate limit | [x] | `6d17193` |
| 12 | Nav link + landing card wire | [x] | `0fb5fe4` |
| 13 | STATUS.md update | [x] | _this commit_ |

**Notable design decisions:**
- Status lifecycle adds `archived` (P5a's `Memory` model has only draft/published) — required by Annexe D §D.4 retrait flow which hides without hard-deleting.
- `approved_content_version` is a counter, not a content snapshot. P9 (Ops & RGPD) can add a snapshot table or use `django-simple-history`; counter is the documented MVP tradeoff.
- Email recipients filter `status="active"` to avoid emailing soft-deleted members.
- Members never publish content. They submit nominations via `/in-memoriam/nominer/`; the admin runs the family-consent process offline before creating the fiche.
- `MEMORIAM_CONTACT_EMAIL` defaults to `parseaddr(DEFAULT_FROM_EMAIL)[1]` so the `mailto:` in the detail-page footer works out of the box.
- `alumni.cloudinary.get_client()` was upgraded to a singleton pattern for `FakeCloudinary` (test mode) to enable inspection of `delete_calls` across multiple `get_client()` calls within a single test. `reset_fake_client()` helper added for fixture-driven isolation.

---

## P6a — Ops: media backup

**Shipped:** 2026-05-05
**Plan:** [plans/2026-05-04-media-backup.md](plans/2026-05-04-media-backup.md)
**Spec:** [specs/2026-05-04-media-backup-design.md](specs/2026-05-04-media-backup-design.md)
**Test suite:** 463 passing total (12 new tests across `alumni/tests/test_storage.py`, `alumni/tests/test_cloudinary_download.py`, `core/tests/test_backup_media.py`).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Cloudinary `download(public_id)` method | [x] | `9028d13` |
| 2 | S3-compatible storage client wrapper + settings + `boto3` dep | [x] | `15de40c` |
| 3 | `backup_media` management command | [x] | `060c1b0` |
| 4 | Restore + provisioning runbook | [x] | `59210ff` |
| 5 | STATUS update | [x] | _this commit_ |

**Notable design decisions:**
- **Backup target = Railway-native S3-compatible bucket**, not Backblaze B2. The master spec §8.2 originally specified B2 + GitHub Actions for cross-cloud DR; we explicitly downgraded to single-cloud (Railway) for operational simplicity. Reasoning: spec §A. The architecture supports a future swap to true off-cloud DR cleanly (any S3-compatible client; or write to two clients in parallel).
- Cron runs as a Railway scheduled service (`media-backup-cron`), sibling to `lesretrouvailles` in the same Railway project. Schedule: `0 3 * * 0` (Sunday 03:00 UTC).
- **Path dedup, not hash dedup.** The bucket path mirrors the Cloudinary `public_id` exactly; `head_file(path)` short-circuits already-backed-up photos. Simpler than maintaining a manifest, correct for our use case.
- **95% success-rate exit threshold.** Cloudinary occasionally has 5xx flakes; we don't want every weekly run to alert on transient noise. Below the threshold, the command exits 1 and Railway flags the deploy as failed.
- **Lifecycle = 90-day rolling retention** via S3 lifecycle rule (configured manually once via the AWS CLI against the bucket endpoint). Runbook §1.2 documents.
- **One-time provisioning** (Railway bucket creation, lifecycle rule, cron service creation, env var wiring) is operator-driven via runbook §1; not in code.
- **Cloudinary-disaster fallback** (master spec §8.2 "Plan de bascule médias") is documented as a manual procedure in runbook §5; not a built-in code path. Deferred per the spec's non-goals.
- **Photo-bearing model discovery is hardcoded** (`Member`, `Memory`, `InMemoriamEntry`). Future phases adding a `photo_public_id` field must update `_collect_photo_public_ids()` in `core/management/commands/backup_media.py`. Acceptable until ≥5 such models exist.
- **Database backup is NOT in P6a** — relies on Railway's automatic daily Postgres snapshots (7-day retention). Documented in runbook §6.
- The command lives in `core/management/commands/` (already an installed app) instead of `alumni/management/`. Avoids promoting `alumni/` (the project package) to a Django app just for command discovery.

---

## P6b — Ops: RGPD admin purge

**Shipped:** 2026-05-05
**Plan:** [plans/2026-05-05-rgpd-admin-purge.md](plans/2026-05-05-rgpd-admin-purge.md)
**Spec:** [specs/2026-05-05-rgpd-admin-purge-design.md](specs/2026-05-05-rgpd-admin-purge-design.md)
**Test suite:** 477 passing total (14 new tests in `members/tests/test_rgpd_purge.py`).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | AuditLog `rgpd.member.purged` action choice + migration | [x] | `14affbc` |
| 2 | `rgpd_purge_member` service function (engine + 10 tests) | [x] | `2fd2735` |
| 3 | `rgpd_purge_member` management command (--dry-run, --yes) | [x] | `85d4e13` |
| 4 | Admin action 'Purger RGPD' with type-to-confirm intermediate page | [x] | `8530021` |
| 5 | Operator runbook | [x] | `7b9f464` |
| 6 | STATUS update | [x] | _this commit_ |

**Notable design decisions:**
- **Admin-only scope.** Master spec §9.4 also describes a member-self-service flow with granular content choices (delete vs anonymize). Deferred — at our scale and stage RGPD requests come in via email and an admin executes. Self-service can ship later as a separate phase calling into this same engine. Spec §A reasoning.
- **Hard-delete personal artifacts; anonymize cross-domain references.** Member's profile photo, gallery uploads, nominations are hard-deleted. AuditLog entries about other things this member did are kept but the actor FK becomes NULL (SET_NULL already configured). AdminApplication rows tied to this email get `.purge()` called on them (existing P3 anonymization machinery).
- **Refusal preconditions, not silent cascades.** If the member has created In Memoriam fiches (`PROTECT` FK to User), the engine refuses with a message telling the operator to reassign `created_by` first. If the actor is the member themselves, refused (would lock the operator out mid-cascade). No schema changes — refusal is rare and easy to fix in 30 seconds via Django admin.
- **External-system calls happen BEFORE the DB transaction.** Cloudinary delete + Tigris bucket delete_version run first. If they fail, the DB is untouched and the operator re-runs safely. DB mutations are wrapped in `transaction.atomic()`. The AuditLog entry is the LAST step — its presence is the unambiguous signal of full success.
- **Audit row carries no PII.** Single `rgpd.member.purged` entry per purge with metadata = `{email_hash: <12-char sha1>, deleted_counts: {...}}`. The hash lets a future investigator confirm "the member with email X was purged on date Y" without storing the email itself.
- **Type-to-confirm UX.** CLI prompts for the literal word `yes`; admin action requires typing the member's exact email per row. Five seconds of friction; eliminates fat-finger purges. Same pattern GitHub uses for repo deletion.
- **No new pip deps.** Reuses `alumni.cloudinary` (P2) + `alumni.storage` (P6a) + existing `AuditLog` (P4b). Zero infrastructure surface added.

---

## P6c — Ops: DMARC monitoring + AuditLog retention

**Shipped:** 2026-05-05
**Spec (combined design + plan):** [specs/2026-05-05-p6c-dmarc-retention-design.md](specs/2026-05-05-p6c-dmarc-retention-design.md)
**Test suite:** 479 passing total (2 new tests in `cooptation/tests/test_process_deadlines.py`).

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | AuditLog 12-month retention purge in daily cron | [x] | `a869043` |
| 2 | DMARC monitoring runbook | [x] | `92e9fd3` |
| 3 | STATUS update — mark P6 complete | [x] | _this commit_ |

**Notable design decisions:**
- **AuditLog retention is wired into the existing daily cron** (`process_cooptation_deadlines`) as one more `_purge_*` step, not a separate command. Keeps the cron-service surface area at one Railway service. Retention window lives in a module-level constant `AUDIT_LOG_RETENTION_DAYS=365` so it can be tuned without re-tagging.
- **Retention applies uniformly across action types**, including `rgpd.member.purged` itself. The spec discusses keeping a subset longer for compliance; that's a follow-up phase that filters by action, not part of P6c. Today's stance: the audit trail is for operational and security review, not indefinite legal record-keeping.
- **DMARC monitoring is operator-driven, not code.** Master spec only requires "p=quarantine minimum + quarterly surveillance" — both achievable with DNS + a free aggregate-report viewer (dmarcian recommended). Building a parser/dashboard would be 2 weeks of work for marginal value at our scale. Runbook covers the verification + ingestion + quarterly review procedure.
- **AdminApplication 6-month auto-purge was already shipped in P3** as part of `_purge_old_rejections` in the same daily cron. Discovered during P6c planning — was tracked as remaining work in earlier STATUS entries by mistake. Now correctly attributed.
- **Tigris-bucket-lifecycle gap acknowledged in STATUS** rather than blocked on. The master spec's "30-day rotation" was a B2-shaped design that doesn't map onto Railway's bucket backend; path-dedup keeps the bucket small enough that the gap is operationally acceptable.

---

## How to update

- When a phase plan is written: link it in the Phase Index and in that phase's section.
- When a task within a phase ships: tick its checkbox and add the short commit SHA.
- When a phase ships: set status to `Complete`, add the date and milestone tag, and confirm test count.
