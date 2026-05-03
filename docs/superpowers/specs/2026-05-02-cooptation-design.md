# P3 — Cooptation: Design Spec

**Date:** 2026-05-02
**Phase:** P3 of P1–P7
**Depends on:** P1 (Foundation), P2 (Membership — `Member`, `NotificationPreference`, `ConsentRecord`)
**Feeds into:** P4 (Public surface), P6 (Ops/RGPD)
**PRD reference:** `docs/archives/PRD_Alumni_CEG1_Birni_v1_2.md` §6.1, §7.2, §9.3, Annexe E
**Project spec:** `docs/superpowers/specs/2026-05-01-alumni-platform-design.md`

---

## 1. Overview

P3 builds the **cooptation flow** — the process by which a non-member becomes a member. A visitor fills a public signup form naming two existing members as parrains; the parrains receive secure-link emails to vouch; J+7 reminder, J+14 expiry with fallback to a knowledge questionnaire or admin direct verification; admin makes the final decision; on approval the candidate receives a one-time password-set link and a `Member` row is created.

End state of P3: P2's `Member` model now has a real input pipeline. The 190 expected alumni can self-onboard with two clicks of vouching from existing members.

---

## 2. Scope

### In scope

- `AdminApplication`, `CooptationRequest`, `KnowledgeQuestion`, `QuestionnaireResponse` models
- Public `/inscription/` signup form (rate-limited, honeypot)
- Public `/cooptation/<token>/` parrain vouch form (login required + identity check, bypasses consent gate)
- Public `/questionnaire/<token>/` knowledge fallback (token-gated, no auth required)
- Admin moderation UI: queue, approve/reject actions, view of cooptation responses + questionnaire answers
- Custom Resend `EmailBackend` (`alumni/email.py`) using the official `resend` SDK
- 10 email templates (Annexe E phase 1) — French only
- Daily `manage.py process_cooptation_deadlines` command (J+7 reminders, J+14 expiry transitions, 6-month retention purge)
- Railway cron service running the daily command
- One-time password-set flow on approval via Allauth's password-reset machinery
- Tests covering models, state machine, public views, email rendering, cron logic, i18n, a11y

### Out of scope (deferred)

- Public landing replacing the placeholder → P4
- `PublicSearchEntry` "we're also looking for…" list → P4
- `AuditLog` model + decorator → P6
- DMARC monitoring dashboards → P6
- CAPTCHA / form-fill timing checks → P7 (only adopt if abuse observed)
- Photo at signup — candidates add via `/profil/` after first login
- Inbound email handling (parsing parrain replies as votes) — out of scope for MVP

---

## 3. Architecture

New Django app `cooptation/`, separate from `members/`. Cooptation creates the `Member` row at admin approval; `members/` does not depend on `cooptation/`. Resend lives at the project level.

```
alumni/
  email.py             # ResendBackend, send_email(to, subject, template_base, context)
  settings/
    base.py            # adds DEFAULT_FROM_EMAIL, RESEND_API_KEY env
    staging.py         # EMAIL_BACKEND="alumni.email.ResendBackend", PASSWORD_RESET_TIMEOUT=7d
    prod.py            # same
cooptation/
  __init__.py
  apps.py
  admin.py             # ApplicationAdmin with custom actions
  models.py            # AdminApplication, CooptationRequest, KnowledgeQuestion, QuestionnaireResponse
  forms.py             # SignupForm (with honeypot), ParrainVouchForm, QuestionnaireForm
  views.py             # signup_view, parrain_vouch_view, questionnaire_view
  services.py          # approve_application(), reject_application(), purge_application()
  emails.py            # one function per template — thin wrappers over send_email
  urls.py
  management/
    commands/
      process_cooptation_deadlines.py
      seed_questions.py     # initial KnowledgeQuestion seed
  templates/cooptation/
    signup.html
    signup_success.html
    parrain_vouch.html
    parrain_vouch_done.html       # already-responded
    parrain_vouch_expired.html    # past expires_at
    questionnaire.html
    questionnaire_done.html
  templates/emails/cooptation/
    application_received.{txt,html}
    cooptation_requests_sent.{txt,html}
    cooptation_accepted.{txt,html}
    cooptation_refused.{txt,html}
    cooptation_expired.{txt,html}
    application_approved.{txt,html}
    application_rejected.{txt,html}
    parrain_invitation.{txt,html}
    parrain_reminder.{txt,html}
    admin_new_application.{txt,html}
  tests/
    conftest.py                       # application_factory, parrain_factory, etc.
    test_models.py
    test_services.py
    test_signup_view.py
    test_parrain_vouch_view.py
    test_questionnaire_view.py
    test_admin_actions.py
    test_emails_render.py
    test_emails_i18n.py
    test_process_deadlines.py
    test_resend_backend.py
    test_a11y.py
```

There is no `signals.py` — approve/reject is admin-driven via `services.py`.

---

## 4. Data Model

### 4.1 `AdminApplication`

State machine — **5 states only**:

| State | Meaning |
|-------|---------|
| `cooptation_pending` | initial — waiting on parrains; cron and vouch view both watch this |
| `awaiting_admin` | parrains resolved/expired or questionnaire submitted; admin must call it |
| `approved` | User+Member created; password-set link sent |
| `rejected` | `rejected_at` set; `retention_until = rejected_at + 180 days` |
| `purged` | retention expired; PII fields cleared |

Auxiliary field `cooptation_outcome` carries detail without bloating the state machine:

| `cooptation_outcome` | Set when |
|---|---|
| `pending` | initial |
| `all_accepted` | both parrains responded `accepted` |
| `mixed` | one accepted, one refused |
| `all_refused` | both parrains responded `refused` |
| `expired` | J+14 passed with at least one parrain still pending |

Whether the questionnaire path was taken is derived from `QuestionnaireResponse.objects.filter(application=...).exists()`.

```python
class AdminApplication(models.Model):
    STATUS_CHOICES = [
        ("cooptation_pending", "Cooptation en cours"),
        ("awaiting_admin", "En attente de l'admin"),
        ("approved", "Approuvé"),
        ("rejected", "Rejeté"),
        ("purged", "Purgé"),
    ]
    OUTCOME_CHOICES = [
        ("pending", "En attente"),
        ("all_accepted", "Deux accords"),
        ("mixed", "Un accord, un refus"),
        ("all_refused", "Deux refus"),
        ("expired", "Expiré (J+14)"),
    ]

    # Candidate identity (PII — purged on retention expiry)
    full_name = models.CharField(max_length=160)
    nickname = models.CharField(max_length=60, blank=True)
    years_attended = ArrayField(models.IntegerField(), size=6)
    classes = ArrayField(models.CharField(max_length=4, choices=GRADE_CHOICES), size=4)
    city = models.CharField(max_length=80)
    country = models.CharField(max_length=80, default="Niger")
    profession = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    whatsapp = models.CharField(max_length=30, blank=True)

    # State
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="cooptation_pending")
    cooptation_outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES, default="pending")

    # Audit
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, related_name="reviewed_applications")
    review_note = models.TextField(blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    retention_until = models.DateTimeField(null=True, blank=True)
    purged_at = models.DateTimeField(null=True, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["email"]),
            models.Index(fields=["retention_until"]),
        ]

    def purge(self):
        """Clear all PII fields. Called when retention_until <= now."""
        for field in ["full_name", "nickname", "email", "whatsapp", "city", "country", "profession", "review_note"]:
            setattr(self, field, "")
        self.source_ip = None
        self.status = "purged"
        self.purged_at = timezone.now()
        self.save()
```

### 4.2 `CooptationRequest`

```python
class CooptationRequest(models.Model):
    RESPONSE_CHOICES = [
        ("pending", "En attente"),
        ("accepted", "Accordée"),
        ("refused", "Refusée"),
    ]

    application = models.ForeignKey(AdminApplication, on_delete=CASCADE, related_name="cooptation_requests")
    parrain = models.ForeignKey("members.Member", on_delete=PROTECT, related_name="cooptation_requests")
    token = models.CharField(max_length=64, unique=True, default=lambda: secrets.token_urlsafe(32))
    expires_at = models.DateTimeField()  # set at creation: now() + 14 days
    reminder_sent_at = models.DateTimeField(null=True, blank=True)  # set at J+7
    response = models.CharField(max_length=16, choices=RESPONSE_CHOICES, default="pending")
    responded_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["application", "response"]),
            models.Index(fields=["expires_at", "response"]),
        ]
```

`parrain` uses `on_delete=PROTECT` so a member cannot be deleted while still owning open cooptation requests. The admin must reassign or wait for resolution.

### 4.3 `KnowledgeQuestion` + `QuestionnaireResponse`

Hybrid Option C: 2 closed-form (admin-defined answer keys) + 1 open-ended (admin-graded).

```python
class KnowledgeQuestion(models.Model):
    KIND_CHOICES = [("closed", "Réponse courte"), ("open", "Réponse libre")]
    position = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    text = models.CharField(max_length=500)
    answer_keys = ArrayField(models.CharField(max_length=80), default=list, blank=True)  # accent-insensitive substrings
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]

class QuestionnaireResponse(models.Model):
    application = models.ForeignKey(AdminApplication, on_delete=CASCADE, related_name="questionnaire_responses")
    question = models.ForeignKey(KnowledgeQuestion, on_delete=PROTECT)
    candidate_answer = models.TextField()
    auto_grade = models.BooleanField(null=True, blank=True)  # True/False for closed; None for open
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("application", "question")]
```

Auto-grade logic (closed only):
```python
def grade_closed_response(question, answer):
    needle = unaccent_lower(answer)
    return any(unaccent_lower(key) in needle for key in question.answer_keys)
```

Default seed (loaded by `seed_questions` management command, admins edit via Django admin):
- `position=1, kind=closed, text="Cite un professeur du CEG 1 entre 1980 et 1985.", answer_keys=[<admin fills>]`
- `position=2, kind=closed, text="Comment s'appelait la principale autorité du CEG 1 dans ces années ?", answer_keys=[<admin fills>]`
- `position=3, kind=open, text="Décris en quelques phrases un souvenir précis de ta scolarité au CEG 1.", answer_keys=[]`

---

## 5. URL Surface

| Path | View | Auth | Notes |
|------|------|------|-------|
| `/inscription/` | `signup_view` | none, rate-limit 5/h/IP, honeypot field | Public form |
| `/cooptation/<token>/` | `parrain_vouch_view` | login required + parrain identity check | Bypasses consent gate; renders 410 page if expired or already-responded |
| `/questionnaire/<token>/` | `questionnaire_view` | none, token only | One-time submission; 410 page after submit |

**Settings updates:**
- `LOGIN_REQUIRED_WHITELIST` adds `/inscription/`, `/questionnaire/`
- `ConsentRequiredMiddleware.SKIP_PREFIXES` adds `/cooptation/`

**Parrain identity check** in `parrain_vouch_view`:
```python
member = getattr(request.user, "member", None)
if member is None or member.pk != cooptation_request.parrain_id:
    raise PermissionDenied("Cette invitation ne vous est pas adressée.")
```

---

## 6. Email — Resend integration

### 6.1 `alumni/email.py` — custom backend

```python
from django.core.mail.backends.base import BaseEmailBackend
import resend
from django.conf import settings

class ResendBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        resend.api_key = settings.RESEND_API_KEY
        sent = 0
        for msg in email_messages:
            payload = {
                "from": msg.from_email or settings.DEFAULT_FROM_EMAIL,
                "to": list(msg.to),
                "subject": msg.subject,
                "text": msg.body,
                "html": next(
                    (alt[0] for alt in (msg.alternatives or []) if alt[1] == "text/html"),
                    None,
                ),
            }
            payload = {k: v for k, v in payload.items() if v is not None}
            try:
                resend.Emails.send(payload)
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
```

A `FakeResendBackend` for tests records `sent_messages` as a list, no network call.

### 6.2 `send_email(to, template_base, context)`

```python
def send_email(to, template_base, context):
    """template_base='cooptation/parrain_invitation' loads .txt for body and .html for alternative."""
    body = render_to_string(f"emails/{template_base}.txt", context)
    html = render_to_string(f"emails/{template_base}.html", context)
    subject = render_to_string(f"emails/{template_base}.subject.txt", context).strip()
    msg = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [to])
    msg.attach_alternative(html, "text/html")
    msg.send()
```

Three files per template: `.txt` body, `.html` body, `.subject.txt` (single-line subject).

### 6.3 Templates (10)

All under `cooptation/templates/emails/cooptation/`:

| # | Trigger | To | Template base |
|---|---------|----|----|
| 1 | Application submitted | candidate | `application_received` |
| 2 | After parrain emails sent | candidate | `cooptation_requests_sent` |
| 3 | Parrain accepts | candidate | `cooptation_accepted` |
| 4 | Parrain refuses | candidate | `cooptation_refused` |
| 5 | J+14 expiry | candidate | `cooptation_expired` (with questionnaire link) |
| 6 | Admin approves | candidate | `application_approved` (with password-set link) |
| 7 | Admin rejects | candidate | `application_rejected` (with reason) |
| 8 | Application submitted | parrain | `parrain_invitation` (with token link) |
| 9 | J+7 reminder | parrain | `parrain_reminder` |
| 10 | Application submitted | all `is_staff=True` | `admin_new_application` |

### 6.4 Settings

`alumni/settings/base.py`:
```python
RESEND_API_KEY = env("RESEND_API_KEY", default="")
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="Les Retrouvailles <noreply@villageretrouvailles.com>",
)
```

`alumni/settings/staging.py` and `prod.py`:
```python
EMAIL_BACKEND = "alumni.email.ResendBackend"
PASSWORD_RESET_TIMEOUT = 7 * 24 * 60 * 60  # 7 days for the post-approval password-set link
```

Dev keeps Django's console backend (already set in `dev.py`).

---

## 7. Cron — daily deadline processor

### 7.1 `manage.py process_cooptation_deadlines`

Runs once daily. Idempotent (re-running on the same day is a no-op).

**Step 1 — J+7 reminders.** For each `CooptationRequest`:
- `response='pending'`
- `reminder_sent_at IS NULL`
- `now >= expires_at - 7 days` AND `now < expires_at`

→ Send `parrain_reminder` to `parrain.user.email`, set `reminder_sent_at = now`.

**Step 2 — J+14 expiry.** For each `AdminApplication` in `cooptation_pending` whose **all** CooptationRequests have either `response != 'pending'` OR `expires_at < now`:

If at least one request expired without a response:
- `application.cooptation_outcome = 'expired'`
- Send `cooptation_expired` email to candidate (containing the questionnaire URL `/questionnaire/<questionnaire_token>/`)
- Application stays in `cooptation_pending` until questionnaire submitted, then transitions to `awaiting_admin`

If all requests have `response != 'pending'`:
- Compute `cooptation_outcome` from response distribution
- `application.status = 'awaiting_admin'`
- Send `admin_new_application` to staff (re-using the same template) for queue visibility

**Step 3 — 6-month retention purge.** For each `AdminApplication` in `rejected` where `retention_until <= now`:
- Call `application.purge()`

### 7.2 Email pacing

Between each `send_email` call: `time.sleep(0.5)`. Resend free tier is 100/day; the sleep gives 200/min headroom. Documented in runbook: "do not batch more than 50 candidates in one onboarding session — cooptation sends ~5 emails per candidate."

### 7.3 Cron mechanism: Railway cron service

Create a second Railway service in the same project, named `cooptation-cron`:
- Build mode: same `Dockerfile` (shares the image)
- Start command override: `python manage.py process_cooptation_deadlines`
- Schedule: `0 6 * * *` (daily at 06:00 UTC) via Railway's built-in cron config
- Env vars: shares the app's `DATABASE_URL`, `RESEND_API_KEY`, `SECRET_KEY`, `DJANGO_SETTINGS_MODULE`

No GitHub Actions glue, no CLI tokens, no second auth surface. Documented in `docs/runbooks/staging-deploy.md`.

---

## 8. Account creation on admin approve

Admin clicks **Approuver** in `/admin/cooptation/adminapplication/<id>/change/`:

`cooptation/services.py::approve_application(application, *, reviewed_by)`:

```python
@transaction.atomic
def approve_application(application, *, reviewed_by):
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        email=application.email,
        defaults={"username": application.email},
    )
    user.set_unusable_password()
    user.save()
    member, _ = Member.objects.update_or_create(
        user=user,
        defaults={
            "first_name": application.full_name.split()[0],
            "last_name": " ".join(application.full_name.split()[1:]),
            "nickname": application.nickname,
            "years_attended": application.years_attended,
            "classes": application.classes,
            "city": application.city,
            "country": application.country,
            "profession": application.profession,
            "status": "active",
        },
    )
    application.status = "approved"
    application.reviewed_by = reviewed_by
    application.save()
    # Generate Allauth-managed password-set link, valid PASSWORD_RESET_TIMEOUT (7 days).
    send_application_approved_email(application, user)
    return user, member
```

The email contains an Allauth password-reset URL (same machinery used for forgot-password). Candidate clicks → sets password → auto-logged in → lands on `/charte/`.

If candidate misses the 7-day window: admin clicks **Renvoyer le lien** custom action which calls `send_application_approved_email` again with a freshly-generated token.

---

## 9. Spam / abuse protection

- **Rate limit on `/inscription/` POST:** 5/h per IP via `django-ratelimit` (already in deps)
- **Honeypot:** hidden form field `website_url` in SignupForm. Bots fill it. Server-side: if non-empty → render success page (don't tell the bot); no DB write.
- **IP audit:** `source_ip` stored on every application. After 3 submissions from same IP in 24h → application gets `🚩` badge in admin changelist (custom `list_display` callable).

Form-fill timing checks and CAPTCHA → P7 if abuse appears.

---

## 10. Tests

| File | Coverage |
|------|----------|
| `test_models.py` | Field constraints, state defaults, `purge()` clears every PII field, `cooptation_outcome` derivation |
| `test_services.py` | `approve_application` creates User+Member in single txn, idempotent on email; `reject_application` sets retention_until correctly; `purge_application` |
| `test_signup_view.py` | Form validates parrain emails against active members, rejects self-cooptation, rejects duplicate parrains, honeypot caught, rate limit at 6th, source_ip stored |
| `test_parrain_vouch_view.py` | 410 on expired token, 410 on already-responded, 403 for wrong-user, accept transitions outcome, both-accept transitions application to `awaiting_admin` immediately (not waiting for cron), email sent |
| `test_questionnaire_view.py` | Closed answer auto-graded, accent-insensitive, open answer never auto-graded, one-time submission, transitions application to `awaiting_admin` |
| `test_admin_actions.py` | Approve action calls `approve_application`, reject action sets retention_until, resend-link action regenerates token |
| `test_emails_render.py` | Each of 10 templates renders without TemplateError given representative context |
| `test_emails_i18n.py` | Each template includes a key French phrase (covers regression if msgstr lookup breaks) |
| `test_process_deadlines.py` | J+7 reminder fires once (re-run is no-op), J+14 expiry transitions correctly, retention purge clears expected fields, email pacing called |
| `test_resend_backend.py` | FakeResendBackend records calls; payload shape correct; html alternative attached |
| `test_a11y.py` | `/inscription/`, `/questionnaire/`, `/cooptation/<token>/` all have proper label associations |

Estimated 50+ new tests.

---

## 11. Error handling and edge cases

| Case | Behavior |
|------|----------|
| Parrain clicks expired token | 410 Gone with styled "Cette demande a expiré le X" page |
| Parrain clicks already-responded token | 410 Gone with styled "Vous avez déjà répondu le X" page |
| Wrong logged-in user clicks token | 403 with French message |
| Candidate signs up with email matching existing Member | 400 — "Cet email correspond déjà à un membre" |
| Parrain email matches candidate email | 400 — "Vous ne pouvez pas vous parrainer" |
| Both parrain emails match | 400 — "Veuillez nommer deux parrains différents" |
| Parrain email matches a non-active Member | 400 — "Email parrain inconnu ou inactif" |
| Application submitted but parrain emails are valid Members → email sending fails (network) | Application saved, retry in cron's daily run; admin sees "0 emails sent" badge |
| Cron fails for 3 days | Resumes; backlog processed in one run; idempotent design prevents double-sends |
| Candidate submits questionnaire twice (bot) | unique_together prevents duplicate row; second POST returns 410 |
| Candidate signs up with the same email twice (already an open application) | 400 — "Une demande avec cet email est en cours" |

---

## 12. Acceptance criteria

P3 ships when:

- All 50+ new tests pass; full suite green
- A visitor can submit `/inscription/` → both parrains receive an email → both click and accept → admin sees the application in `awaiting_admin` → admin approves → candidate receives password-set link → clicks → sets password → logs in → lands on `/charte/` → accepts charter → reaches `/annuaire/` and sees themselves in the directory
- The questionnaire fallback path works end-to-end: J+14 cron fires → candidate receives questionnaire email → completes it → admin reviews and approves
- The retention purge works: rejected application's PII is cleared after 6 months simulated via `freeze_time` test
- Resend integration delivers a real test email to a developer mailbox via the staging environment
- `STATUS.md` updated with P3 row and task-to-commit mapping
- `git tag v0.3.0-cooptation` after merge to `main`

## 13. Open questions / risks

1. **Resend free tier 100/day cap.** With 190 candidates × ~5 emails ≈ 950 emails over launch period. Spread over 2-3 weeks is fine. If batching breaks the cap, upgrade to Pro ($20/mo for 50k/mo) — flag in runbook.
2. **Allauth password-reset token UX.** The post-approval email reuses the password-reset machinery. Email copy must NOT say "réinitialiser" (which implies they had a password) but rather "définir votre mot de passe".
3. **Parrain emails in PRD say "name and email of 2 parrains".** We treat 2 as the required count. If a candidate only has 1 known parrain, they can't apply via the standard flow — admin direct verification (skip-cooptation custom action) is the escape hatch. Implemented as an admin button: "Approuver sans cooptation" for cases where the admin personally vouches.
4. **Knowledge question seed values.** The 2 closed questions need admin-defined answer keys before launch. P3 ships with placeholder questions; admin must populate keys via Django admin before going live.
