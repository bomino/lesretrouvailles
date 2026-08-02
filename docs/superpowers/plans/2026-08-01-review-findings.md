# Post-review hardening — Implementation Plan (combined spec + plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the top findings from the 2026-08-01 full-codebase review, in the agreed priority order, one TDD'd commit per task.

**Architecture:** Five independent surgical fixes — a state-machine guard in the cooptation vouch view, per-item error isolation in the daily cron, a compose/staging-settings repair for `make docker-run`, an allauth proxy-count setting, and a trio of small robustness fixes (gestion flash banners, `PurgeIncomplete` handling, suspend transaction). No new models, no migrations.

**Tech Stack:** Django 5.2, pytest, existing test conventions (`<app>/tests/test_<topic>.py`, `FakeResendBackend`, source-text settings tests in `alumni/tests/test_infra_hardening.py`).

## Global Constraints

- User-facing copy in **French**; code/comments/commits in **English**.
- Branch: `fix/review-findings` (already created). One commit per task, `<type>(<scope>): <imperative summary>` + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Surgical changes only — no adjacent refactoring.
- Full suite (`make test`) must pass before merge; test count must grow from 954.
- Out of scope (explicitly): H2 (email-only parrainage — product decision for the owner), CSP, dependency lock, everything in the review's "Low" tail.

---

### Task 1: Vouch status guard (review H1)

**Files:**
- Modify: `cooptation/views.py` (`parrain_vouch_view`, after the ownership check at line ~219)
- Modify: `cooptation/templates/cooptation/parrain_vouch_done.html` (decided-application variant copy)
- Test: `cooptation/tests/test_parrain_vouch_view.py`

**Interfaces:** none new — the guard renders the existing done template with `application_decided=True`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.django_db
@pytest.mark.parametrize("decided_status", ["approved", "rejected", "purged"])
def test_vouch_closed_when_application_already_decided(parrain_client, decided_status):
    """H1 (2026-08-01 review): a late vouch on a decided application must not
    flip it back to awaiting_admin — a rejected app escaping status='rejected'
    also escapes the 180-day retention purge."""
    req = parrain_client.request_obj
    app = req.application
    app.status = decided_status
    app.save()

    response = parrain_client.get(f"/cooptation/{req.token}/")
    assert response.status_code == 410

    response = parrain_client.post(
        f"/cooptation/{req.token}/", {"response": "accepted", "comment": ""}
    )
    assert response.status_code == 410

    req.refresh_from_db()
    app.refresh_from_db()
    assert req.response == "pending"  # nothing recorded
    assert app.status == decided_status  # decision not reversed


@pytest.mark.django_db
def test_vouch_on_decided_application_sends_no_candidate_email(parrain_client, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    req = parrain_client.request_obj
    app = req.application
    app.status = "rejected"
    app.save()
    parrain_client.post(f"/cooptation/{req.token}/", {"response": "accepted", "comment": ""})
    assert FakeResendBackend.sent_messages == []
```

- [ ] **Step 2: Run, expect FAIL** — `pytest cooptation/tests/test_parrain_vouch_view.py -v -k decided` → the POST currently records the response / flips status.

- [ ] **Step 3: Implement** — in `parrain_vouch_view`, after the `PermissionDenied` ownership check, add (mirroring the questionnaire gate's comment style):

```python
    # A vouch link must go dead the moment the application is decided.
    # DECIDABLE_STATUSES deliberately lets the admin approve/reject while the
    # cooptation is still running; without this gate a late second vouch would
    # flip an approved app back to awaiting_admin (re-decidable, stranding the
    # already-created account) or pull a rejected one out of status='rejected'
    # — where the 180-day retention purge would no longer find it.
    if cooptation_request.application.status not in ("cooptation_pending", "awaiting_admin"):
        return render(
            request,
            "cooptation/parrain_vouch_done.html",
            {"request_obj": cooptation_request, "application_decided": True},
            status=410,
        )
```

In `parrain_vouch_done.html`, branch the heading/body on `application_decided` ("Cette candidature a déjà été traitée." / "La décision a été prise par l'équipe ; votre réponse n'est plus nécessaire." — no `responded_at` line in that branch).

- [ ] **Step 4: Run, expect PASS**, then the whole file: `pytest cooptation/tests/test_parrain_vouch_view.py -v`
- [ ] **Step 5: Commit** — `fix(cooptation): dead-end vouch links once the application is decided`

---

### Task 2: J+7 reminder failure must not abort the daily cron (review M2-cron)

**Files:**
- Modify: `cooptation/management/commands/process_cooptation_deadlines.py` (`_send_j7_reminders`, lines 93-100)
- Test: `cooptation/tests/test_process_deadlines.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_one_failed_reminder_does_not_abort_the_run(
    make_cooptation_request, monkeypatch, settings
):
    """M2 (2026-08-01 review): a single Resend failure in the J+7 loop raised
    out of handle(), cancelling that day's expiries and retention purges."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from django.core.management import call_command
    from django.utils import timezone
    from cooptation import emails

    soon = timezone.now() + timedelta(days=3)
    req_fail = make_cooptation_request(expires_at=soon)
    req_ok = make_cooptation_request(expires_at=soon)

    real_send = emails.send_parrain_reminder

    def flaky(req):
        if req.pk == req_fail.pk:
            raise RuntimeError("resend 500")
        real_send(req)

    monkeypatch.setattr(emails, "send_parrain_reminder", flaky)
    monkeypatch.setattr("cooptation.management.commands.process_cooptation_deadlines.time.sleep", lambda s: None)

    out = StringIO()
    call_command("process_cooptation_deadlines", stdout=out)  # must not raise

    req_fail.refresh_from_db()
    req_ok.refresh_from_db()
    assert req_fail.reminder_sent_at is None  # retried tomorrow
    assert req_ok.reminder_sent_at is not None
    assert "Done." in out.getvalue()  # later stages ran
```

- [ ] **Step 2: Run, expect FAIL** with `RuntimeError: resend 500` propagating.
- [ ] **Step 3: Implement** — wrap the send in the same per-item isolation `_expire_j14` uses:

```python
        for req in qs:
            # Same per-item isolation as _expire_j14: one Resend failure must
            # not abort the run — everything after this stage (J+14 expiry,
            # retention purges) would silently be skipped for the day. The
            # send happens BEFORE the stamp on purpose: a failed send leaves
            # reminder_sent_at NULL, so the reminder is retried tomorrow.
            try:
                emails.send_parrain_reminder(req)
            except Exception as e:  # noqa: BLE001
                self.stderr.write(f"  ERROR reminder req={req.pk}: {e}")
                continue
            req.reminder_sent_at = now
            req.save()
            count += 1
            time.sleep(PACING_SECONDS)
```

- [ ] **Step 4: Run, expect PASS**, then `pytest cooptation/tests/test_process_deadlines.py -v`
- [ ] **Step 5: Commit** — `fix(cooptation): isolate J+7 reminder failures so one outage cannot cancel the daily run`

---

### Task 3: `make docker-run` boots again (review H3)

**Files:**
- Modify: `alumni/settings/staging.py` (SITE_URL guard, lines 110-117)
- Modify: `docker-compose.yml` (app environment)
- Test: `alumni/tests/test_infra_hardening.py`

**Design:** the guard exists to stop a *deployed* service from serving localhost links; `make docker-run` is a local prod-repro where a localhost SITE_URL is correct. So: (a) tighten the guard to also catch `http://127.0.0.1` (reviewer-noted gap), (b) add an explicit opt-out env var `SITE_URL_ALLOW_LOCAL` (default false) that only docker-compose.yml sets, (c) compose also sets the console `EMAIL_BACKEND` so the Resend-key guard (correctly) doesn't apply. Dockerfile build steps already use `SITE_URL=https://build-time-only.invalid`, so they are unaffected (CLAUDE.md Docker-build rule respected).

- [ ] **Step 1: Write the failing tests** (source-text style + subprocess boot, both in `test_infra_hardening.py`):

```python
def test_compose_prod_repro_can_boot_staging_settings(tmp_path):
    """H3 (2026-08-01 review): the b4d86d8 fail-fast guards were never
    reflected in docker-compose.yml, so `make docker-run` — the documented
    prod-repro workflow — crash-looped at settings import. The compose file
    must opt out of the localhost-SITE_URL guard explicitly and use the
    console email backend; the guard must also catch 127.0.0.1."""
    import subprocess, sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    # Compose declares its intent explicitly...
    assert 'SITE_URL_ALLOW_LOCAL: "true"' in compose
    assert "EMAIL_BACKEND: django.core.mail.backends.console.EmailBackend" in compose
    # ...and the guard closes the 127.0.0.1 gap.
    src = (root / "alumni" / "settings" / "staging.py").read_text(encoding="utf-8")
    assert "http://127.0.0.1" in src and "SITE_URL_ALLOW_LOCAL" in src

    # Boot staging settings in a subprocess with the same env the compose
    # file gives the app service (minus DB, which django.setup() never touches).
    compose_env = {
        "DJANGO_SETTINGS_MODULE": "alumni.settings.staging",
        "SECRET_KEY": "test-not-a-secret",
        "DATABASE_URL": "postgres://x:x@localhost:5432/x",
        "ALLOWED_HOSTS": "localhost",
        "SITE_URL": "http://localhost:8000",
        "SECURE_SSL_REDIRECT": "false",
        "CLOUDINARY_CLIENT_PATH": "alumni.cloudinary.FakeCloudinary",
        "CLOUDINARY_CLOUD_NAME": "fake-cloud",
        "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
        "SITE_URL_ALLOW_LOCAL": "true",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Windows needs this
    }
    boot = 'import django; django.setup(); print("BOOTED")'
    result = subprocess.run(
        [sys.executable, "-c", boot], capture_output=True, text=True,
        cwd=root, env=compose_env,
    )
    assert "BOOTED" in result.stdout, result.stderr

    # Without the explicit opt-out the guard still fires — for BOTH spellings.
    for local_url in ("http://localhost:8000", "http://127.0.0.1:8000"):
        env = {**compose_env, "SITE_URL": local_url}
        env.pop("SITE_URL_ALLOW_LOCAL")
        result = subprocess.run(
            [sys.executable, "-c", boot], capture_output=True, text=True,
            cwd=root, env=env,
        )
        assert "BOOTED" not in result.stdout
        assert "ImproperlyConfigured" in result.stderr
```

- [ ] **Step 2: Run, expect FAIL** (compose lacks the vars; guard misses 127.0.0.1).
- [ ] **Step 3: Implement** — staging.py guard becomes:

```python
# SITE_URL feeds every magic link. Left at base.py's http://localhost:8000
# default, the roster import would DM ~200 members a link to their own machine
# — and the operator would find out from the members. 127.0.0.1 is the same
# footgun spelled differently. docker-compose.yml (local prod-repro, where a
# localhost SITE_URL is the *correct* value) opts out explicitly via
# SITE_URL_ALLOW_LOCAL — a deployed service never sets it.
_local_site_url = SITE_URL.startswith(("http://localhost", "http://127.0.0.1"))  # noqa: F405
if _local_site_url and not env.bool("SITE_URL_ALLOW_LOCAL", default=False):
    raise ImproperlyConfigured(
        "SITE_URL is still a localhost value. Every magic link and email "
        "URL would point at localhost. Set SITE_URL on the service (or, for "
        "the local docker-compose stack only, SITE_URL_ALLOW_LOCAL=true)."
    )
```

docker-compose.yml app environment gains:

```yaml
      SITE_URL_ALLOW_LOCAL: "true"
      EMAIL_BACKEND: django.core.mail.backends.console.EmailBackend
```

- [ ] **Step 4: Run, expect PASS**: `pytest alumni/tests/test_infra_hardening.py -v`
- [ ] **Step 5: Commit** — `fix(docker): let the compose prod-repro stack boot under the staging fail-fast guards`

---

### Task 4: Allauth rate limits get the real client IP (review, security M1)

**Files:**
- Modify: `alumni/settings/staging.py` (prod inherits via `from .staging import *`)
- Test: `alumni/tests/test_infra_hardening.py`

**Design:** allauth ≥65 resolves the throttle-bucket IP via `ALLAUTH_TRUSTED_PROXY_COUNT` (takes the Nth-from-right XFF token; `1` = rightmost = the hop Railway observed — exactly what `alumni/ratelimit.py` already does for django-ratelimit). Set it in staging.py next to the cache block so both prod-shaped modules get it. Dev/test (no XFF) fall back to `REMOTE_ADDR`, unchanged.

- [ ] **Step 1: Write the failing test**

```python
def test_allauth_throttles_see_the_real_client_ip():
    """2026-08-01 review: RATELIMIT_IP_META_KEY fixed django-ratelimit's view
    of the client IP behind Railway, but allauth has its own resolver that was
    left on REMOTE_ADDR (the proxy) — every visitor shared one login/reset
    bucket, so one attacker could lock all members out. TRUSTED_PROXY_COUNT=1
    makes allauth take the rightmost XFF token, mirroring alumni/ratelimit.py."""
    src = _settings_source("staging")
    assert "ALLAUTH_TRUSTED_PROXY_COUNT = 1" in src

    # Behavioral check of the exact allauth mechanism the setting drives.
    from django.test import RequestFactory, override_settings
    from allauth.core.internal.httpkit import get_client_ip

    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.5", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
    )
    with override_settings(ALLAUTH_TRUSTED_PROXY_COUNT=1):
        assert get_client_ip(request) == "5.6.7.8"  # rightmost = Railway-observed hop
```

- [ ] **Step 2: Run, expect FAIL** on the source assert.
- [ ] **Step 3: Implement** — in staging.py, after the EMAIL_BACKEND block:

```python
# Allauth's login/reset/signup throttles key on ITS OWN client-IP resolver,
# not on RATELIMIT_IP_META_KEY. Left at the default (REMOTE_ADDR = Railway's
# proxy), every visitor shares one bucket: a single attacker can exhaust
# login/reset limits platform-wide. 1 = take the rightmost X-Forwarded-For
# token — the hop Railway actually observed, same choice as alumni/ratelimit.py.
ALLAUTH_TRUSTED_PROXY_COUNT = 1
```

- [ ] **Step 4: Run, expect PASS**.
- [ ] **Step 5: Commit** — `sec(settings): give allauth throttles the real client IP behind Railway's proxy`

---

### Task 5: Gestion console robustness trio

Three sub-fixes, one commit each.

#### 5a. Flash banners: right copy, once, no reflection (review M1-gestion + L2)

**Files:**
- Modify: `gestion/templates/gestion/base.html` (delete the flash block, lines 38-60)
- Modify: `gestion/templates/gestion/memory_list.html` (add the memory-flash block at top of content)
- Modify: `gestion/templates/gestion/member_detail.html` (add `noop` / `bad_status` branches)
- Test: `gestion/tests/test_flash_banners.py` (new)

**Design:** every memory flash redirect lands on `gestion:memory_list`, so the memory-specific copy moves there. `member_status_view` redirects `noop`/`bad_status` to member_detail, which the base block used to cover — member_detail gains those two branches ("Aucune modification." / "Statut invalide."). The raw `{{ flash }}` fallback is dropped everywhere (fixes the reflected-content spoofing).

- [ ] **Step 1: Write the failing tests**

```python
# gestion/tests/test_flash_banners.py
"""M1 + L2 (2026-08-01 review): gestion/base.html rendered a second,
memory-worded banner on every member/cooptation flash, and reflected
arbitrary ?flash= text into a trusted-looking status banner."""

@pytest.mark.django_db
def test_member_suspend_flash_shows_one_correct_banner(admin_client, make_member):
    member = make_member()
    response = admin_client.get(f"/gestion/membres/{member.slug}/?flash=status_suspended")
    content = response.content.decode()
    assert content.count("Compte suspendu.") == 1
    assert "status_suspended" not in content  # raw token no longer leaks

@pytest.mark.django_db
def test_member_noop_flash_still_has_copy(admin_client, make_member):
    member = make_member()
    response = admin_client.get(f"/gestion/membres/{member.slug}/?flash=noop")
    assert "Aucune modification." in response.content.decode()

@pytest.mark.django_db
def test_arbitrary_flash_text_is_not_reflected(admin_client, make_member):
    member = make_member()
    response = admin_client.get(
        f"/gestion/membres/{member.slug}/?flash=Compte+supprim%C3%A9"
    )
    assert "Compte supprimé" not in response.content.decode()

@pytest.mark.django_db
def test_memory_list_keeps_memory_flash_copy(admin_client):
    response = admin_client.get("/gestion/souvenirs/?flash=updated")
    assert "Photo mise à jour." in response.content.decode()
```

(Use the existing gestion tests' staff-client fixture — check `gestion/tests/conftest.py` for its actual name and reuse it; `admin_client` above is a placeholder for that fixture.)

- [ ] **Step 2: Run, expect FAIL** (duplicate banner / reflected text present today).
- [ ] **Step 3: Implement** per the design above.
- [ ] **Step 4: Run new file + full gestion suite: `pytest gestion/ -v`** (existing memory-flash tests must stay green).
- [ ] **Step 5: Commit** — `fix(gestion): scope flash banners to their pages and stop reflecting raw tokens`

#### 5b. `PurgeIncomplete` reaches the operator (review M1-members)

**Files:**
- Modify: `members/admin.py` (rgpd purge execute loop, lines 193-204)
- Modify: `members/management/commands/rgpd_purge_member.py` (execute path, lines 156-161)
- Test: `members/tests/test_rgpd_purge.py` (extend)

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.django_db
def test_cli_purge_reports_incomplete_instead_of_traceback(make_member, monkeypatch):
    """M1 (2026-08-01 review): PurgeIncomplete — the engine's designed
    'external delete failed, safe to retry' signal — propagated as a raw
    traceback through both purge front-ends."""
    from alumni import cloudinary as cloud_mod
    from django.core.management import call_command

    cloud_mod.reset_fake_client()
    member = make_member(photo_public_id="members/x/photo")
    monkeypatch.setattr(
        cloud_mod.get_client(), "delete", lambda pid: (_ for _ in ()).throw(RuntimeError("down"))
    )
    err = StringIO()
    with pytest.raises(SystemExit) as exc:
        call_command("rgpd_purge_member", member.user.username, "--yes", stderr=err)
    assert exc.value.code == 1
    assert "INCOMPLETE" in err.getvalue()
    assert "idempotent" in err.getvalue()  # the retry guidance reaches the operator
```

Plus an admin-action test mirroring the existing admin purge-action tests in `test_rgpd_purge.py` (same fixtures/POST shape): monkeypatch the fake client's `delete` to raise, POST the confirmed action, assert `response.status_code == 302` (no 500) and the member still exists.

- [ ] **Step 2: Run, expect FAIL** (RuntimeError→PurgeIncomplete traceback today).
- [ ] **Step 3: Implement** —
  - `members/admin.py`: import `PurgeIncomplete` alongside `PurgeRefused`; in the execute loop `except (PurgeRefused, PurgeIncomplete) as e: messages.error(...)`.
  - CLI execute path: `except PurgeIncomplete as e: self.stderr.write(f"INCOMPLETE: {e}"); sys.exit(1)` (keep `REFUSED:` separate; dry-run/prompt paths can't raise it — external deletes are skipped on dry-run).
- [ ] **Step 4: Run, expect PASS**: `pytest members/tests/test_rgpd_purge.py -v`
- [ ] **Step 5: Commit** — `fix(members): surface PurgeIncomplete cleanly in both purge front-ends`

#### 5c. Suspension is atomic (review M2-gestion)

**Files:**
- Modify: `gestion/views.py` (`member_status_view`, lines 155-189)
- Modify: `gestion/forms.py` (`save_with_audit` x2 — wrap in `transaction.atomic()`)
- Test: `gestion/tests/test_member_status.py` (or wherever the existing suspend tests live — extend that file)

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_suspend_rolls_back_completely_if_audit_write_fails(
    admin_client, make_member, monkeypatch
):
    """M2 (2026-08-01 review): Member.status and User.is_active were saved in
    separate non-atomic writes — a failure between them left a 'suspended'
    member whose account could still log in."""
    from members.models import AuditLog

    member = make_member()
    def boom(*a, **k):
        raise RuntimeError("db hiccup")
    monkeypatch.setattr(AuditLog.objects, "create", boom)

    with pytest.raises(RuntimeError):
        admin_client.post(
            f"/gestion/membres/{member.slug}/statut/", {"target_status": "suspended"}
        )

    member.refresh_from_db()
    member.user.refresh_from_db()
    assert member.status == "active"        # rolled back together...
    assert member.user.is_active is True    # ...not half-applied
```

(If the test client swallows the exception into a 500 response instead of raising, assert on `response.status_code == 500` — the two `refresh_from_db` asserts are the point.)

- [ ] **Step 2: Run, expect FAIL** — today `member.status` comes back `"suspended"`.
- [ ] **Step 3: Implement** — mirror `memory_status_view`: wrap the body in `transaction.atomic()` with `select_for_update()` on the member row; keep `_flush_user_sessions` inside the transaction (DB-backed sessions, same connection — all-or-nothing). Wrap both `save_with_audit` bodies in `with transaction.atomic():`.
- [ ] **Step 4: Run, expect PASS**, then `pytest gestion/ -v`.
- [ ] **Step 5: Commit** — `fix(gestion): make suspend/reactivate and audited form saves atomic`

---

### Task 6: Wrap-up

- [ ] Run the full suite: `make test` (expect >954 passing; transient cooptation ERRORS on full runs are a known Windows/Postgres quirk — re-run once before investigating).
- [ ] `make lint` clean.
- [ ] Update `docs/superpowers/STATUS.md` with a short entry for this sweep.
- [ ] Merge: `git checkout main && git merge --no-ff fix/review-findings` with a descriptive message; push. No tag (not a milestone).
- [ ] Surface to the owner (not code): H2 — parrainage is email-only; ~80% of members can't be parrains. Product decision needed.

## Self-review notes

- Spec coverage: fix-order items 1-5 → Tasks 1-5; item 6 (H2) deliberately non-code, in Task 6.
- Fixture names in Tasks 5a/5c (`admin_client`) must be replaced with the real gestion conftest fixture at implementation time — flagged in-plan.
- Types/signatures: no new interfaces; all changes are internal to existing views/commands/settings.
