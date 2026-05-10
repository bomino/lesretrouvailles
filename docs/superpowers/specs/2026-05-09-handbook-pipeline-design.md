# Internal handbook pipeline (design + plan, combined; backfilled)

**Status:** ✅ Implemented 2026-05-09 → 2026-05-10. This document is a **retroactive backfill** of the spec + plan that should have preceded the work — captured after the pipeline ran end-to-end so the WHY isn't lost. See [STATUS.md](../STATUS.md#post-launch-polish-post-v100-soft-launch) for the corresponding row.
**Branch:** `feat/handbook-pipeline`
**Tag:** none — this is internal tooling, no version bump.

## A. Origin

The platform now has two long French markdown guides — `docs/guides/guide_membre.md` (10 sections, mobile-first) and `docs/guides/guide_admin.md` (12 sections, cross-references runbooks). They cover *what to do*, but they're text-only. For the audience (alumni 55-65, ~80% email-less, mobile-first low-end Android, frequent operator hand-holding via WhatsApp), an illustrated walkthrough — "tap this button, then this one" — has more practical value than prose. And it has to be reproducible: every UI change risks invalidating screenshots, so we want a one-command pipeline that regenerates the handbook against the current code.

The lift: an internal `make handbook` that boots the dev runserver, drives Playwright through three real flows in real browsers (member-mobile login, member-desktop directory search, admin-console magic-link reissue), captures screenshots with French captions, and assembles them with the existing markdown guides + FAQ into a single `handbook.html` + `handbook.pdf`.

## B. Goals

1. One command (`make handbook`) regenerates a printable handbook from the current code — no hand-curated screenshots, no Photoshop, no drift.
2. Three illustrated chapters cover the three audiences that need walkthroughs: members on phones, members on desktop, co-admins on the Gestion console.
3. Output bundles the **existing** narrative (`guide_membre.md`, `guide_admin.md`, `FAQ_ENTRIES`) so we don't duplicate documentation; the handbook is a *view*, not a fork.
4. Demo dataset is deterministic and idempotent — every regen produces the same screenshots given the same code.

## C. Non-goals (explicit)

- **Production deploy.** This is a developer/operator deliverable. The runserver dev settings + cleartext demo passwords stay out of `staging.py` / `prod.py`.
- **CI integration.** Running Chromium in CI would require ~150 MB of binaries and significant runtime. Run locally on demand; commit the spec/plan, not the artifacts.
- **Hand-edited screenshots.** Every screenshot is captured by a flow script. If a UI changes and breaks a flow, the fix is in the flow, not in an image editor.
- **Multi-language handbook.** French only, mirrors `LANGUAGES = [("fr", "Français")]`. Hausa is parked in the Phase 2 backlog.
- **Inbound bot / interactive handbook.** Static HTML + PDF only.
- **Screenshot pixel-diff regression tests.** Out of scope for v1; the harness records screenshots but doesn't assert against goldens.

## D. Audience for the handbook

Two reader profiles:

1. **The operator (Bomino + future co-admins).** The illustrated admin chapter + full `guide_admin.md` is the printable reference they take to a member-onboarding session.
2. **A new co-admin doing first-time training.** The mobile + desktop member chapters show what the member sees, so the co-admin can talk a member through their phone screen on WhatsApp without guessing.

The PDF format matters: the operator may print + ring-bind it, or read it offline on a phone, or share it via WhatsApp document attachment.

## E. Architecture

### Pipeline (one command, four stages)

```
make handbook
  └→ python docs/handbook/assemble.py
       1. _start_runserver        # spawn manage.py runserver --noreload
       2. _wait_for_server        # urlopen(BASE_URL) loop, 30s budget
       3. _run_flows
            a. _storage_states.bootstrap   # log in once per persona,
                                            #  cache cookies to disk
            b. for each flow module:        # 3 flows total
                 import + call run(browser, base_url)
                 → screenshots/curated/<flow-id>-NN-<slug>.png
                 → flows/_output/<flow-id>.json (manifest)
       4. _load_manifests + _render_handbook
            → docs/handbook/handbook.html (Jinja2 + 2 markdown guides + FAQ)
       5. _render_pdf              # second Playwright session, page.pdf()
            → docs/handbook/handbook.pdf
       6. _stop_runserver          # always, finally-clause
```

### Components

| Path | Role |
|---|---|
| `members/management/commands/seed_handbook_demo.py` | Builds the deterministic dataset: 12 demo members (one per `demo_member_NN`) spanning all promotion years 1980–1985, 1 co-admin (`demo_coadmin`), 3 published Memory entries, 1 published In Memoriam fiche, 1 cooptation application with 2 pending parrain requests. Idempotent (`update_or_create`); `--reset` wipes only `demo_*` rows. |
| `docs/handbook/flows/_browser.py` | Two `@contextmanager`-style helpers: `member_mobile_context` (360×800 viewport + member storage state) and `member_desktop_context` (1280×800 + member) and admin variants. Encapsulates Playwright context creation + storage_state path conventions. |
| `docs/handbook/flows/_storage_states.py` | One-shot login bootstrap: programmatically POST to `/accounts/login/`, save the resulting cookies to `_storage_states/{member,coadmin}.json`. Called once per pipeline run, before any flow. |
| `docs/handbook/flows/_step.py` | The `step(...)` recorder: takes a Page, an action callable, a slug, a French caption; runs the action, screenshots the page, appends to a manifest dataclass. `flow_recorder(...)` is a contextmanager that writes the manifest JSON on exit. |
| `docs/handbook/flows/flow_*.py` | The three flows. Each is a single `run(browser, base_url)` function. Flows reference `docs/guides/guide_membre.md#anchor` so a future reader can follow back to the prose. |
| `docs/handbook/template.html` | Jinja2 template. Renders chapters (intro + screenshots with captions) followed by the full `guide_membre.md` + `guide_admin.md` (markdown→HTML at render time) + the FAQ accordion (`aide.faq.FAQ_ENTRIES`). Embeds a self-contained `<style>` block — print-friendly, no external CSS. |
| `docs/handbook/assemble.py` | Orchestrator. Top-level `main()` is the entire pipeline. |

### Data flow

```
seed_handbook_demo (one-time setup)
        ↓ writes 12 Member rows + 1 co-admin User + ConsentRecord per member
runserver (spawned by assemble.py)
        ↑                                       ↓
        ┕━━━━━━━━━ Playwright flow scripts ━━━━━━┙
                       ↓ screenshot()
              curated/*.png + _output/*.json
                       ↓ Jinja2 render
              handbook.html + handbook.pdf
```

## F. Locked decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Browser engine | **Chromium via Playwright** | Single-engine PDF rendering; Playwright is already in dev extras; ~150 MB one-time install. |
| 2 | Demo data isolation | **`demo_*` username prefix + `--reset` only nukes that prefix** | `seed_handbook_demo --reset` is safe to run against a dev DB that also has `bominomla` or real `seed_members` fixtures; only demo rows die. |
| 3 | Demo password reset on every run | **Yes (idempotent + deterministic)** | Storage-state bootstrap relies on a known password; the seed always re-sets `demo-handbook-pw`. Safe — only `demo_*` users affected. |
| 4 | Charter consent for demo members | **Pre-create `ConsentRecord` at `CHARTER_CURRENT_VERSION`** | `ConsentRequiredMiddleware` redirects every URL to `/charte/` until consent exists. Without this, every flow lands on the charter page (silent on mobile-login screenshot, loud on directory flow's missing-search-input assertion). |
| 5 | Storage-state file location | **`docs/handbook/flows/_storage_states/`** (gitignored) | Cookies are dev-only and short-lived; gitignoring keeps them out of code review and prevents stale-cookie bugs. |
| 6 | Flow output manifest format | **JSON with `ensure_ascii=False`, written `encoding="utf-8"`** | Captions are French; ASCII-escaping makes the manifests unreadable. UTF-8 explicit on the write side because Python's `Path.write_text` defaults to the system locale (cp1252 on Windows) — a real bug we hit at first end-to-end run. |
| 7 | Screenshot directory | **`screenshots/curated/`** (gitignored) | Flow scripts write directly here; the original "curated" name was meant for hand-picked images, but in practice the flow IS the curation. Treat as build output, not source. |
| 8 | HTML + PDF output | **Gitignored** | Regenerable from code; checking them in would balloon the repo on every UI tweak. Operators run `make handbook` when they need a fresh copy. |
| 9 | Bundle existing markdown vs duplicate | **Bundle (markdown→HTML at assembly time)** | Single source of truth for `guide_membre.md` etc. The handbook is a *view*; editing prose still happens in `docs/guides/`. |
| 10 | runserver via subprocess vs LiveServerTestCase | **subprocess** | Three independent flows + a separate PDF-render pass means we want a stable HTTP server across the whole orchestrator run, not a per-test fixture. `--noreload` to avoid double-spawning on Windows. |
| 11 | flow harness vs pytest-playwright | **Standalone harness** | These aren't tests — they're documentation generators. They shouldn't run in `make test`, shouldn't fail CI, and produce artifacts (screenshots) by design rather than as a side effect. |

## G. Plan (what was implemented, in build order)

| # | Task | Done | Commit |
|---|------|------|--------|
| 1 | Playwright + markdown + jinja2 dev extras + `make handbook` / `seed-handbook` / `playwright-install` targets | [x] | `4b84837` |
| 2 | `seed_handbook_demo` management command (12 members + co-admin + memory + memoriam + cooptation; idempotent + `--reset`) | [x] | `e24e5d2` |
| 3 | Flow harness — `_browser.py` viewport contexts + `_step.py` recorder + `_storage_states.py` cookie bootstrap | [x] | `423349d` |
| 4 | Three proof flows — `flow_member_mobile_login`, `flow_member_desktop_directory`, `flow_admin_magic_link_reissue` | [x] | `7e937a7` |
| 5 | Assembly orchestrator `assemble.py` + Jinja2 `template.html` (chapters + markdown guides + FAQ + self-contained CSS) | [x] | `2595366` |
| 6 | Fix: `ConsentRecord` per demo member (else middleware redirects every URL to `/charte/`) — found at first end-to-end run | [x] | `8e1338b` |
| 7 | Fix: write manifests `encoding="utf-8"` (cp1252 default on Windows) — found at first end-to-end run | [x] | `aa7ed0b` |
| 8 | Backfilled spec/plan + STATUS row + gitignore handbook artifacts | [x] | _this commit_ |

## H. Notable design decisions captured during execution

- **The two bugs we hit at first end-to-end run are pinned in `F.4` and `F.6` above** because they're the kind of cross-cutting failures that are easy to forget. Both have regression tests (`test_demo_members_have_charter_consent`; the UTF-8 fix is exercised by every regen).
- **Flow ordering is intentional in `assemble.py::FLOW_MODULES`.** Mobile login first (sets up the visual narrative — "this is what the member sees on their phone"), then desktop directory (same audience, richer screen real estate, exercises search), then admin magic-link reissue (operator-side, builds on the directory flow's mental model). The PDF reads top-to-bottom in this order.
- **The mobile-login flow's "after-login" screenshot lands on the public landing page (`/`), not the member's profile.** That's because Allauth's `LOGIN_REDIRECT_URL` is `/` and the public landing page renders the same hero for authenticated users (with a hamburger nav, see post-Gestion-v1 polish row 4). The screenshot's caption acknowledges this — the page shown IS the post-login state for a member.
- **No pixel-diff goldens.** Adding screenshot regressions would be high-maintenance for low value at our scale; the value of this pipeline is *catching that a flow no longer completes*, not catching that a button moved by 3px. If a UI change breaks a flow, the flow assertion fails and the fix is obvious.
- **`runserver --noreload` is mandatory on Windows.** The default reload watcher double-spawns on Windows and the orchestrator's `Popen.terminate()` only kills the parent, leaving an orphan that holds port 5432. `--noreload` keeps it to a single process.

## I. Risks + ongoing concerns

| # | Risk | Mitigation |
|---|---|---|
| 1 | UI changes silently break a flow assertion | Flow failure exits with a stack trace pointing at the locator. Re-run after the UI change to catch + update. Same shape as a broken integration test. |
| 2 | Demo passwords leak to a wrong environment | `seed_handbook_demo` is a dev-only command — no `prod.py` import path uses it. The `demo_*` prefix + `--reset` semantics make it safe even on a populated dev DB. |
| 3 | Chromium binary drift (Playwright version mismatch) | `pip install -e ".[handbook]" && playwright install chromium` is the documented one-time setup; pin Playwright in `pyproject.toml` `[handbook]` extras. |
| 4 | Charter version bumps invalidate the seeded ConsentRecord | The seed reads `CHARTER_CURRENT_VERSION` at runtime, so bumping the charter just means re-seeding. Acceptable. |
| 5 | New flow added but assembly chapter mapping missed | `_render_handbook` groups flows by `manifest["audience"]` (`member-mobile` / `member-desktop` / `admin`); a new audience key would silently appear in no chapter. Minor — visible at first regen. |
| 6 | Storage state cookies expire mid-run | Bootstrap runs every pipeline invocation; cookies are seconds old by the time flows execute. Not an issue in practice. |
| 7 | PDF page-break mid-screenshot looks bad | Screenshots are wrapped in a `figure` with `break-inside: avoid` in the embedded CSS. Verified visually on the first end-to-end pass. |

## J. How to run

One-time:
```bash
make playwright-install   # ~150 MB of Chromium binaries into the venv
```

Every regen:
```bash
make db-up                # if not already running
make migrate              # only if migrations have moved
make seed-handbook        # idempotent; --reset is safe
make handbook             # ~30s end-to-end on a warm cache
open docs/handbook/handbook.pdf
```

## K. Future enhancements (not promised)

- **Add flow: cooptation parrain vouch** — covers the parrain-onboards-coopté narrative.
- **Add flow: Mur des souvenirs upload (admin)** — currently only the directory + magic-link admin flows are illustrated.
- **Side-by-side language version** — when Hausa translations land, render two PDFs from the same flow set.
- **Pixel-diff regression** — only if we ever decide the cost is worth catching cosmetic drift. Keep parked.
