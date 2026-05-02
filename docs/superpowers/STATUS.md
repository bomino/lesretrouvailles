# Project Status

**Project:** Les Retrouvailles — CEG1 Birni alumni platform
**Spec:** [specs/2026-05-01-alumni-platform-design.md](specs/2026-05-01-alumni-platform-design.md)

Single dashboard for tracking phase and task completion across all plans. Update when a plan is written, when a task ships, and when a phase ships.

## Phase Index

| Phase | Title | Status | Plan |
|-------|-------|--------|------|
| P1 | Foundation | Complete (tag `v0.1.0-foundation`, 2026-05-02) | [plan](plans/2026-05-01-foundation.md) |
| P2 | Membership | Not started | — |
| P3 | Cooptation | Not started | — |
| P4 | Public surface | Not started | — |
| P5 | Mémoire seed | Not started | — |
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

**Status:** Not started.
**Scope:** `Member` model, profile pages, directory with search/filters/pagination, Cloudinary upload integration, `NotificationPreference`, `ConsentRecord`.
**Plan:** not yet written.

---

## P3 — Cooptation

**Status:** Not started.
**Scope:** `AdminApplication`, `CooptationRequest`, J+7/J+14 deadline machinery (Django management command + cron), knowledge questionnaire, admin moderation UI, email templates, Resend integration, `AdminApplication` 6-month retention purge.
**Plan:** not yet written.

---

## P4 — Public surface

**Status:** Not started.
**Scope:** Public landing page (replaces the placeholder), `PublicSearchEntry` model with collegial validation, public removal flow without auth, `noindex` differentiation between public and private pages.
**Plan:** not yet written.

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
