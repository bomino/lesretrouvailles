# CLAUDE.md — Project conventions for AI agents

This file is loaded by Claude Code when working in this repository. It captures the load-bearing conventions and gotchas that aren't obvious from reading the code.

If something here contradicts what you'd reach for by default, **trust this file** — it's the result of real incidents on this codebase.

---

## Project context (the 30-second version)

- **What:** Private alumni platform for CEG 1 Birni (Zinder, Niger), promotions 1980-1985. Production at https://villageretrouvailles.com/. Tags: `v1.0.0-soft-launch`, `v1.1.0-gestion-console`, `v1.2.0-self-service-help`.
- **Audience:** ~200 alumni from a WhatsApp group, ages 55-65. **~80% have no email.** Mobile-first (Android 7+ + low-end devices). The launch onboarding imports them en masse from a WhatsApp roster.
- **Tone:** All user-facing copy is **French**. Code, comments, and commit messages are **English**.
- **Owner:** Single bilingual super-admin (Bomino, `bominomla`). Plus 0-3 co-admins via `is_staff=True` (see admin-tiers section below).

---

## Commands

The `Makefile` is the source of truth — these are the wrappers worth knowing:

| Command | What it does |
|---|---|
| `make dev` | `python manage.py runserver` (http://localhost:8000) |
| `make test` | Builds CSS, then runs full pytest suite (~3 min, ~650 tests post-Gestion-v1) |
| `make migrate` | `python manage.py migrate` |
| `make check` | `manage.py check` + `makemigrations --dry-run --check` (pre-push sanity) |
| `make lint` | `ruff check .` + `ruff format --check .` (read-only) |
| `make format` | `ruff check --fix .` + `ruff format .` (writes) |
| `make css` / `make css-watch` | Tailwind one-shot / watch — only when classes changed; CSS is committed in `static/` |
| `make db-up` / `make db-down` | Local Postgres via `docker-compose.yml` (alumni/alumni/alumni on :5432) |
| `make seed` | `loaddata seed_members` |
| `make docker-run` | Builds and runs the **staging-shaped** stack at :8000 (basic-auth `admin / compose-test-pw`); useful for reproducing prod-like middleware behavior |

Single-test invocations:

```bash
pytest members/tests/test_models_member.py -v             # one file
pytest members/tests/test_models_member.py::TestX -v      # one class
pytest members/tests/test_models_member.py::TestX::test_y # one test
pytest -k whatsapp                                        # by keyword
pytest --lf                                               # last failed only
```

`pyproject.toml` sets `DJANGO_SETTINGS_MODULE = "alumni.settings.dev"` for pytest, so tests don't need `--ds=...`. `addopts = "-q"` is the default; pass `-v` to override.

Custom `manage.py` commands worth knowing (see `members/management/commands/` and `cooptation/management/commands/`): `reissue_login_link`, `import_whatsapp_roster`, `rgpd_purge_member`, `audit_launch_readiness`, `process_cooptation_deadlines`, `backup_media`, `seed_questions`, `smoke_test_cooptation`, `create_member`.

---

## Settings modules

`alumni/settings/` splits four ways. Picking the wrong one accidentally is a common mistake:

| Module | Used by | Notes |
|---|---|---|
| `base.py` | (imported by all three below) | Shared INSTALLED_APPS, allauth config, etc. Don't run directly. |
| `dev.py` | Local `runserver`, **pytest** | Loose CSRF, `EMAIL_BACKEND=console`, `DEBUG=True`. This is what `DJANGO_SETTINGS_MODULE` resolves to in `pyproject.toml`. |
| `staging.py` | `docker-compose.yml`, `staging.villageretrouvailles.com` | Prod-shaped middleware (security headers, basic-auth gate). Useful for reproducing prod issues locally with `make docker-run`. |
| `prod.py` | Railway service `lesretrouvailles` | Real Resend, real Cloudinary, real Postgres. |

When a bug only appears in prod, the first thing to try locally is `make docker-run`, not `make dev` — staging settings catch a class of issues `dev.py` masks.

---

## Django app layout

The project is one Django project (`alumni/`) hosting eight apps. Knowing what owns what saves a lot of grepping:

- **`alumni/`** — Django project package. Settings, root URLs, **custom `AdminSite` (`GestionAdminSite`) that gates `/admin/` to superusers**, Cloudinary client (`cloudinary.py`), object-storage client (`storage.py`), `FakeResendBackend` (`email.py`), security/basic-auth middleware.
- **`core/`** — Cross-cutting infrastructure: landing page, `/health` endpoint, sitemap, allauth adapter (`allauth_adapter.py`), `backup_media` weekly cron command.
- **`members/`** — The big one. `Member`, `User` extensions, `PublicSearchEntry`, **`AuditLog`** (cross-domain event log), magic-link reissue, RGPD purge engine (`services.py::rgpd_purge_member`), WhatsApp roster import, member directory views, public ghost list. Search composition extracted into `members/search.py` (multi-token AND + pg_trgm trigram fallback). Also owns `audit_launch_readiness` for go-live checks.
- **`cooptation/`** — Public signup flow (`/inscription/`), `AdminApplication`, `CooptationRequest`, parrainage logic, daily deadlines cron (`process_cooptation_deadlines`).
- **`gestion/`** — Co-admin console at `/gestion/` (Gestion v1, tag `v1.1.0-gestion-console`). **No models** — pure views/forms/decorators composed over the other apps. The `staff_required` decorator in `gestion/decorators.py` is the right gate for any new staff-tier view (redirects to `/accounts/login/`, 403s authenticated non-staff). See admin-tiers section below.
- **`memoires/`** — Mur des souvenirs. `Memory` (curated photo gallery, admin-uploaded).
- **`memoriam/`** — In Memoriam. `InMemoriamEntry` (tribute fiche) + `InMemoriamNomination` (member-submitted proposal).
- **`aide/`** — Public FAQ at `/aide/` (P8, tag `v1.2.0-self-service-help`). **No models** — `aide/faq.py::FAQ_ENTRIES` is a typed Python list rendered through the existing markdown + bleach pipeline, grouped by category with deterministic icons + anchor slugs from `CATEGORY_META`. To edit content, edit `faq.py` and submit a PR; structural tests in `aide/tests/test_faq_content.py` lock `CATEGORIES` and `CATEGORY_META` in sync. **Public-by-default** via `LOGIN_REQUIRED_WHITELIST` because the FAQ has to be reachable to members who don't have a session yet (activation, password reset). No-result `?q=` queries are logged via `AuditLog.aide.query.no_results` for the future-bot-decision data trail.

Models live in `members`, `cooptation`, `memoires`, `memoriam`. URL roots are wired from `alumni/urls.py`. `gestion` and `aide` are model-less "composition layers" — adding a feature there usually means adding a view that calls into another app's services (gestion) or extending a typed Python list (aide), not adding a model.

---

## Auth (load-bearing decision — read this before touching anything auth-adjacent)

- **Username = WhatsApp digits-only**, e.g. `22790000001`. Email is optional.
- `ACCOUNT_LOGIN_METHODS = {"email", "username"}` — both work. `ACCOUNT_SIGNUP_FIELDS = ["username*", "email", "password1*", "password2*"]`.
- These are the **new (non-deprecated) allauth settings keys**; do NOT regress to `ACCOUNT_AUTHENTICATION_METHOD` etc.
- **Magic-link via WhatsApp** is the dominant onboarding flow (~80% of users have no email). Cooptation flow is for *new outside candidates* only.
- For email-less password resets: `python manage.py reissue_login_link <username>`. Operator copy-pastes the printed URL into a WhatsApp DM.

If you're proposing a feature that "just emails the user," ask: how do the email-less ~80% experience this? They probably need an admin-mediated alternative.

---

## Admin tiers — `is_staff` does NOT unlock `/admin/`

Since Gestion v1 (tag `v1.1.0-gestion-console`), there are two admin tiers:

- **Super Admin** = `is_superuser=True`. Sees `/admin/` AND `/gestion/`. Only `bominomla` in prod.
- **Co-admin** = `is_staff=True, is_superuser=False`. Sees `/gestion/` only. `/admin/` redirects them to the admin login form even though they "could" log in to it under default Django.

**Why this matters for you:**
- `admin.site` in this project is **NOT** the default `django.contrib.admin.site`. It's `alumni.admin.GestionAdminSite`, wired via `INSTALLED_APPS = ["alumni.admin.GestionAdminConfig", ...]`. Its `has_permission` requires `is_superuser`.
- If you read code that calls `admin.site.register(...)` and assume any staff can use those admin views, you'll be wrong. Only superusers can.
- `MemberAdmin.get_actions()` further gates `rgpd_purge_action` to `is_superuser` even within `/admin/` (defense-in-depth).
- The custom `staff_required` decorator is in `gestion/decorators.py` — it redirects to `/accounts/login/` (NOT `/admin/login/`) for unauthenticated users, and 403s for authenticated-but-not-staff. Don't substitute `django.contrib.admin.views.decorators.staff_member_required` — that one redirects to admin login, which we want hidden from co-admins.

If you're adding a new admin-y view: gate it with `gestion.decorators.staff_required` (works for any staff) OR by manually checking `request.user.is_superuser` (Bomino-only).

---

## WhatsApp number ≠ `User.username`

Since `feat/member-whatsapp-field` (post-Gestion-v1), `Member.whatsapp` is the canonical messaging-channel identifier. **`User.username` is the LOGIN identity** and only happens to equal the WhatsApp number for members imported from the roster — for coopted members it's the email, and for the super-admin it's `bominomla`.

**For wa.me URLs and any "send a WhatsApp message to this person" feature:**
- Use `member.whatsapp` (CharField, digits-only, 8-15 chars, may be blank). Validate with `VALID_WHATSAPP_PATTERN` from `members/models.py`.
- DO NOT use `member.user.username`. That generates broken URLs for half the members.
- Hide the button / disable the feature when `member.whatsapp` is empty rather than failing silently. See `gestion.views.member_login_link_view` for the gating pattern.

**For login-related code:** use `User.username` as before. Login identity and messaging identity are decoupled on purpose.

**Form input convention:** the `clean_whatsapp()` / `clean_new_username()` methods on gestion forms strip every non-digit character before validating length, so operators can paste `+227 90 00 01 23` or `+1 555-987-6543` from WhatsApp's contact card. The 8-15 digit length check still fires; country-code requirement is on the operator, not the form.

---

## AuditLog conventions

`members.models.AuditLog` is the cross-domain event log. Two conventions worth following when you write to it:

- **Action string namespace:** `<domain>.<entity>.<verb>`. Currently in use: `ghost.*`, `memoriam.*`, `rgpd.*`, `gestion.*`. Always extend `AuditLog.ACTION_CHOICES` when you add a new action — the field has `choices=` so a Form-level write would otherwise reject. ORM `objects.create()` ignores choices but the `/admin/auditlog/` list filter relies on it.
- **Metadata always includes a human-readable name** (e.g. `member_full_name`, `candidate_full_name`) so the audit log stays readable after a member is purged or renamed. Don't store raw IDs only.

---

## Vendor architecture (don't agree to "all on Railway")

The platform spans **two cloud vendors**:

- **Railway** — app, Postgres, cron services, S3-compatible bucket (Tigris-backed)
- **Cloudinary** — primary media storage + on-the-fly transforms

If a user says "we have everything on Railway, why add X?" or proposes "single-vendor simplicity," **verify against the code first**. Cloudinary is load-bearing for `Member.photo_public_id`, `Memory.photo_public_id`, `InMemoriamEntry.photo_public_id`, and the upload widgets in `members/admin.py`, `memoires/admin.py`, `memoriam/admin.py`.

Replacing Cloudinary would mean reimplementing `f_auto, q_auto:eco, c_fill, g_face` etc. via Pillow or pre-generated variants. Don't agree it's "easy."

---

## Tigris (Railway's bucket backend) quirks

The bucket is on Tigris (`storageapi.dev`), discovered during P6a:

- **`PutBucketVersioning` is NOT supported.** Returns the misleading `BucketAlreadyExists` error.
- **`PutBucketLifecycleConfiguration` only accepts `Expiration` with explicit `Days`/`Date`.** Rejects `NoncurrentVersionExpiration` and `ExpiredObjectDeleteMarker`. The only rule shape Tigris accepts would auto-delete the backups themselves — useless for us.
- **The bucket has no rotation today.** Path-dedup in `backup_media` keeps it small (~500 MB peak at our scale).

If the user proposes anything around bucket retention/versioning, **don't volunteer to apply S3 lifecycle rules**. Read `docs/runbooks/restore.md` §1.2 first.

The script `scripts/apply_bucket_lifecycle.py` exists and gracefully detects + reports both Tigris failures (no longer raises a stack trace).

---

## Cloudinary submodule trap (we hit this twice — don't be the third)

`import cloudinary` does NOT transitively pull in `cloudinary.api` or `cloudinary.uploader`. Attribute access (`cloudinary.uploader.upload(...)`) raises `AttributeError: module 'cloudinary' has no attribute 'uploader'` at first real use.

**Fix and contract:**

- `RealCloudinary.__init__` in `alumni/cloudinary.py` imports `cloudinary`, `cloudinary.api`, AND `cloudinary.uploader` explicitly.
- A regression test (`alumni/tests/test_cloudinary_extensions.py::test_real_cloudinary_init_loads_required_submodules`) instantiates `RealCloudinary` and asserts all three submodules are accessible.
- **Do NOT remove** those imports thinking they're unused. They're load-bearing for production.
- `FakeCloudinary` (used in tests) doesn't go through the real SDK; you'll never catch this in unit tests. The bug only surfaces in production at first real call.

---

## DB constraints: prefer Python-level `clean()` validation

Hard CHECK constraints at the DB level become footguns when the format evolves. We hit this with `members_member_classes_in_set` (P7.1, dropped in migration 0013).

**Pattern:**

- Validate via `Model.clean()` with a regex constant (e.g. `VALID_CLASS_PATTERN`).
- Surface a friendly user-facing message (in French) at the form layer.
- DB-level CHECK is acceptable as defense-in-depth, but only when the format is genuinely fixed forever (e.g. `status IN ('active', 'suspended', 'deleted')`).

For `last_name_initial` on `PublicSearchEntry`: we have `max_length=2` (browser maxlength cap) + `Model.clean()` (friendly message) + DB CHECK regex (defense). Three layers; the user never sees the raw constraint name.

---

## Workflow

The project has used a tight **spec → plan → TDD → ship** loop throughout.

1. **Spec** (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`) — what we're building, why, what's in/out of scope. Includes a §J risks section.
2. **Plan** (`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`) — task breakdown with TDD steps. For small fixes, you can fold spec + plan into one combined doc (see P6c, P7).
3. **Branch** — `feat/<phase-or-topic>` for features, `fix/<topic>` for bugfixes, `docs/<topic>` for doc-only.
4. **TDD** per task: write failing tests → run red → implement → run green → run full suite → commit.
5. **Merge** — always `git merge --no-ff` with a descriptive merge commit message.
6. **Tag** — only for milestone phases (`v1.0.0-soft-launch`). Sub-phases since P5+ haven't been individually tagged.

Commit message convention:
```
<type>(<scope>): <imperative summary>

<body — what changed and why; reference incident if applicable>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

`<type>` ∈ {feat, fix, docs, chore, refactor}; `<scope>` is the affected app or area.

---

## Pre-commit hooks

Configured in `.pre-commit-config.yaml`:

- **ruff** + **ruff-format** — Python linting + formatting
- **djLint** — Django template formatting (HTML)
- **trim trailing whitespace**, **fix end of files**

The hooks **auto-fix** on commit. If they reformat a file, the commit fails and you have to re-stage + re-commit:

```bash
git add <files>
git commit -m "..."
# → ruff-format reformatted; commit aborted
git add <files>           # re-stage the reformatted files
git commit -m "..."       # this one passes
```

This is normal. Don't fight it.

---

## Production secrets — DO NOT pull locally

Earlier in the project I (Claude) was rate-limited for piping production Cloudinary credentials into a local Python process. **Don't do that.**

If you need to interact with prod:

- **Read-only inspection:** `railway ssh --service lesretrouvailles -- python manage.py shell` (then pipe a Python script via stdin).
- **Run a Django command in prod context:** `railway run --service lesretrouvailles python manage.py <command>` (note: this runs **locally** with prod env vars; only works for things that don't need internal-network DNS).
- **Run something that needs prod DB access:** SSH into the running container — `DATABASE_URL` only resolves inside Railway's network.

Never paste a production secret into a tool call's stdout/argv.

---

## Windows-specific gotchas

The owner develops on Windows. The repo is cross-platform but:

- The `railway` CLI is `railway.cmd` on Windows. From Python `subprocess`, you need `shell=True` for Windows (see `scripts/apply_bucket_lifecycle.py` for the pattern). Without it, you get `FileNotFoundError`.
- The `Bash` tool in this Claude Code env is Git Bash, not WSL. Most things work; Postgres connections to localhost work via the Docker port mapping.
- Line endings: `.gitattributes` is set to LF; on commit, Git warns "LF will be replaced by CRLF" — that's working-tree-only, harmless.
- pytest with multiple sequential runs sometimes hits transient Postgres test-DB issues. If a full-suite run shows ERRORS in cooptation tests but passes in isolation, just re-run.

---

## Test conventions

- Tests live next to the app: `<app>/tests/test_<topic>.py`.
- Fixtures in `<app>/tests/conftest.py`. Common fixtures: `make_user`, `make_member`, `make_admin`, `make_application`, `make_cooptation_request`.
- Use `@pytest.mark.django_db` for DB tests.
- Use `settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"` to avoid real sends in email-related tests.
- Use `settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"` and `settings.STORAGE_CLIENT_PATH = "alumni.storage.FakeStorage"` (call `reset_fake_client()` between tests for clean call lists).
- Target full-suite count: `~520` at v1.0.0-soft-launch, `~622` at v1.1.0-gestion-console, `~650` at the post-Gestion polish round, `~683` at v1.2.0-self-service-help. New work should add tests; the count should grow, not shrink.

---

## Mobile UX

- Tap targets: `min-h-tap` and `min-w-tap` Tailwind utilities (= 44px). Use them on every interactive element.
- Mobile breakpoint: `md:` (768px+) is "desktop". Below = mobile, including iPads in portrait.
- The navbar uses a hamburger pattern on `<md` for authenticated users (P7.2 fix). Anon mobile gets a simpler inline layout (logo + WhatsApp icon + Connexion).
- Test responsive in browser DevTools at 360px width minimum (low-end Android baseline for this audience).

---

## Quick references

| What | Where |
|---|---|
| Current state, phase index | `docs/superpowers/STATUS.md` |
| Master spec (PRD + design) | `docs/superpowers/specs/2026-05-01-alumni-platform-design.md` |
| Operator launch procedure | `docs/runbooks/launch.md` |
| User-facing French guide | `docs/guides/guide_membre.md` (member) + `guide_admin.md` (admin) |
| Frontend admin console (gestion) | `gestion/` — views, forms, decorators, templates, tests |
| Public FAQ (`/aide/`) | `aide/` — `faq.py` (typed entries), `views.py`, single accordion template |
| Member directory search composition | `members/search.py` — multi-token AND + pg_trgm trigram fallback |
| Custom AdminSite (locks /admin/ to superuser) | `alumni/admin.py` |
| Cooptation services (approve/reject/purge) | `cooptation/services.py` |
| Member purge (RGPD) engine | `members/services.py::rgpd_purge_member` |
| Bulk import command | `members/management/commands/import_whatsapp_roster.py` |
| Magic-link reissue CLI | `members/management/commands/reissue_login_link.py` |
| Daily cron handler | `cooptation/management/commands/process_cooptation_deadlines.py` |
| Cloudinary client (real + fake) | `alumni/cloudinary.py` |
| Object storage client (real + fake) | `alumni/storage.py` |
| AuditLog model + action choices | `members/models.py::AuditLog` |

---

## Phase patterns to repeat

When the user asks for a new feature:

1. **Brainstorm** if scope is unclear (use `superpowers:brainstorming` skill if it appears applicable).
2. **Spec** the design, including non-goals + risks.
3. **Plan** the tasks with TDD steps.
4. Show user the spec/plan, get confirmation, then execute.
5. After each task: tests green → commit → next task. After all tasks: full suite → STATUS update → propose merge + tag if milestone.

When the user reports a bug:

1. **Understand** the symptom — read logs, reproduce if possible.
2. **Diagnose** the root cause before proposing a fix. Don't paper over symptoms.
3. **Fix** with the smallest change that addresses the cause.
4. **Add a regression test** that would have caught the bug.
5. **Ship** via the same workflow (branch → commit → merge → push). Watch the deploy.

---

## What NOT to do

- **Don't** change auth settings without thinking through how the email-less ~80% are affected.
- **Don't** assume `is_staff=True` unlocks `/admin/`. It doesn't anymore — `/admin/` requires `is_superuser`. See the admin-tiers section above.
- **Don't** use `User.username` as the WhatsApp number for messaging features. Use `Member.whatsapp` (validated digits-only). The two are decoupled on purpose.
- **Don't** generate `wa.me/<id>` URLs without first validating that `<id>` matches `^\d{8,15}$`. Otherwise you'll send operators to api.whatsapp.com's "phone number invalid" page.
- **Don't** propose Cloudinary removal without acknowledging the transform pipeline.
- **Don't** apply S3 lifecycle rules to the Railway bucket — Tigris rejects the rule shapes we'd want.
- **Don't** remove the explicit `import cloudinary.api` / `import cloudinary.uploader` in `RealCloudinary.__init__` — there's a regression test, but more importantly there's a real production failure waiting if you do.
- **Don't** add DB CHECK constraints for fields whose format might evolve. Use Python `clean()` instead.
- **Don't** add a new `AuditLog.action` value without also adding it to `ACTION_CHOICES`. Forms validate against choices; ORM `create()` doesn't, but list filters in `/admin/auditlog/` rely on the enum.
- **Don't** pull production secrets into the local environment.
- **Don't** delete records on production without explicit user confirmation. The P6b RGPD purge engine is the right tool for member deletions; for other test artifacts, surface what you'd delete and ask.
- **Don't** add a new Django app without updating ALL THREE config files that enumerate apps explicitly. The platform doesn't use wildcards anywhere — each new app means an explicit edit in three places, and missing any of them produces a different, silent failure mode:
  1. **`Dockerfile`** — both stages need `COPY <app>/ ./<app>/`. Runtime stage for `django.setup()` to discover the `AppConfig` at `compilemessages` / `collectstatic` time; css-builder stage so Tailwind can scan templates. Symptom if missed: `ModuleNotFoundError: No module named '<app>'` during the prod build (caught loudly at first deploy of `aide/` during P8).
  2. **`.dockerignore`** — if your app or its content sits under a directory excluded by a top-level pattern (e.g., `docs/` or `*.md`), add a negation `!` rule AFTER the exclusion (later patterns win for the same path). Symptom if missed: build fails at the COPY step because the directory isn't in the build context (caught at first deploy of `/guide/` during P8.1, where the runtime COPY of `docs/guides/` failed because `docs/` was wholesale excluded).
  3. **`tailwind.config.js`** — add `"./<app>/**/*.{html,py}"` to the `content` array. Symptom if missed: HTML renders with the raw class names but the corresponding CSS rules are absent from `output.css`, so styling silently fails — elements appear unstyled (zero-height accent bars, plain numbers instead of tabular-nums, missing gradients, etc.). Hardest to catch because the page still loads 200 and most "common" classes already exist in the bundle from other apps; only NEW classes (custom gradients, arbitrary values like `h-[2px]`) reveal the gap. Caught at the visual-elevation pass of `/aide/` and `/guide/` after P8.1 — the user noticed elements weren't rendering as described.
  Pattern: search for an existing `core/` reference in each file, add your app next to it in all three.
- **Don't** assume what the user wants. If a request has multiple interpretations or non-obvious tradeoffs, surface them in 2-3 sentences and ask before executing.

---

## When you're stuck

- Check `docs/superpowers/STATUS.md` for the current state.
- Check `git log --oneline -20` to see what shipped recently.
- Check `docs/runbooks/<topic>.md` for the operator procedure on $topic.
- Check existing `<app>/tests/` for the test pattern in that area.
- Ask the user.
