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
| P5 | Mémoire seed | (split into P5a + P5b) | — |
| P6 | Ops & RGPD | Not started | — |
| P7 | Soft launch | Not started | — |

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

## P5 — Mémoire seed

**Status:** Not started.
**Scope:** `Memory` model, Mur des souvenirs admin-only gallery, `InMemoriamEntry`, In Memoriam seed page.
**Plan:** not yet written.

---

## P6 — Ops & RGPD

**Status:** Not started.
**Scope:** GitHub Actions backup workflow Cloudinary→B2, `purge_user_from_backups.py`, RGPD deletion flow, DMARC monitoring, `AuditLog` model + decorator.
**Plan:** not yet written.

---

## P7 — Soft launch

**Status:** Not started.
**Scope:** Seed content prep, pilot rollout, production launch checklist.
**Plan:** not yet written.

---

## How to update

- When a phase plan is written: link it in the Phase Index and in that phase's section.
- When a task within a phase ships: tick its checkbox and add the short commit SHA.
- When a phase ships: set status to `Complete`, add the date and milestone tag, and confirm test count.
