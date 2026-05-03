# P4b — Public Surface Governance · Design

**Phase:** P4b (second slice of P4 "Public surface" per `docs/superpowers/STATUS.md`).
**Master spec reference:** § 6.5 "Gouvernance de la liste publique" of `2026-05-01-alumni-platform-design.md`.
**P4a reference:** `docs/superpowers/specs/2026-05-03-public-surface-design.md`.
**Date:** 2026-05-03.
**Authors:** BMLa + Claude.

---

## 1. Goal & scope

### Goal

Unblock the `PUBLIC_GHOST_LIST_ENABLED=True` flag flip by shipping a public, friction-free removal flow ("Retirer mon nom") with email confirmation, and add an `AuditLog` model that records every governance action on the ghost list (entry creation, admin sign-off, removal request, removal execution, admin cancellation).

### In scope (P4b)

| Component | Notes |
|----------|-------|
| `RemovalRequest` model | Per-request ephemeral record with confirmation token, 30-day expiry, IP capture |
| `AuditLog` model | Append-only generic event log (actor, action, target, metadata, timestamp) |
| Public removal entry point | "Retirer mon nom" link next to each ghost card → `/retrait/<entry-token>/` (full-page form) |
| Removal form view | Email + optional reason → creates `RemovalRequest` + sends confirmation email |
| Email confirmation handler | `/retrait/confirme/<confirm-token>/` → idempotent auto-execute, sets `entry.removed_at`, writes AuditLog, notifies admin |
| Admin notification email | FYI-style, sent on each successful removal so admins notice patterns |
| Rate limiting | 5/h per IP on **POST** `/retrait/<entry-token>/` (form submit only — confirm-link click is idempotent and not rate-limited) |
| AuditLog signal handlers | `m2m_changed` on `added_by_admins` + `post_save` on entry create + `pre_delete` on RemovalRequest |
| Admin registrations | `RemovalRequestAdmin` (read-only-ish) + `AuditLogAdmin` (append-only — no add/change/delete) |
| Operational unblock | After P4b ships, operators flip `PUBLIC_GHOST_LIST_ENABLED=True` |

### Out of scope (deferred to P4c)

| Item | Rationale |
|------|-----------|
| Custom admin governance UI (approval queue, signoff status indicators) | Django admin's built-in is fine at launch with 0-30 entries; revisit when admins give feedback |
| Quarterly review automation (12-month auto-removal cron) | Master spec mandate but mostly hygiene; the list will be small and admins can sweep manually until the volume warrants automation |
| Retrofitting P3 cooptation actions into AuditLog | P3 keeps its domain-specific audit fields (`reviewed_by`, `rejected_at`, `review_note`); AuditLog is purely additive |
| Hausa translation of the removal flow | Same rationale as P4a — defer to when a Hausa-fluent reviewer is on the admin team |

### Spec interpretation: "sans débat" → auto-execute

Master spec § 6.5 says: *"Formulaire avec confirmation par email à l'adresse fournie. Retrait admin sous 48h, sans débat."*

**Reading:** "sans débat" = no human gatekeeping. Email confirmation IS the gate, not admin review. Removal happens within minutes of the requester clicking the email link. Admin gets a notification email so they can re-add (with 2 signoffs) if it was a clear mistake. The 48h SLA in the spec was operational expectation — the system itself has no 48h delay.

**Tradeoff accepted:** A griefer who controls their own email could remove a stranger's entry. Mitigation: re-adding is possible (via the 2-admin gate); the AuditLog shows who-removed-when; the minimal data exposed (first name + last initial only) means there's not much to grief over.

---

## 2. Data model

### New: `members.models.AuditLog`

Generic governance event log. One row per action, never mutated.

```python
class AuditLog(models.Model):
    """Append-only governance event log. Domain audit fields (e.g.
    AdminApplication.reviewed_by) stay on their respective models — this
    table records cross-domain events that would otherwise be invisible
    to a future "who did what when" query.

    Never mutated after insert. Retention: indefinite (legal-defense
    horizon), revisit when storage becomes a concern.
    """

    ACTION_CHOICES = [
        ("ghost.entry.created",          "Fiche fantôme créée"),
        ("ghost.entry.signed_off",       "Cosignature ajoutée"),
        ("ghost.entry.signoff_removed",  "Cosignature retirée"),
        ("ghost.removal.requested",      "Demande de retrait soumise"),
        ("ghost.removal.confirmed",      "Demande de retrait confirmée"),
        ("ghost.removal.executed",       "Retrait exécuté"),
        ("ghost.removal.cancelled",      "Demande de retrait annulée par admin"),
        ("ghost.entry.purged",           "Fiche purgée"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="audit_log_entries",
        help_text="Null for anonymous actions (e.g., a public removal request).",
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=64)  # e.g. "members.PublicSearchEntry"
    target_id = models.CharField(max_length=64)    # PK of the target as a string
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} on {self.target_type}:{self.target_id} @ {self.created_at:%Y-%m-%d %H:%M}"
```

`metadata` JSON examples per action:
- `ghost.removal.requested` → `{"requester_email": "x@y.test", "reason": "Je veux disparaître"}`
- `ghost.entry.signed_off` → `{"signer_pk": 12, "signer_email": "admin@...", "signoff_count_after": 2}`
- `ghost.removal.executed` → `{"removal_request_id": 5, "reason_at_request": "..."}`

**Accepted limitation (I1):** GDPR Art. 15 access requests ("show me everything you have on me") for non-staff requesters require a Postgres JSON query against `metadata->>'requester_email'`. Workable at our scale (~few hundred rows). Note for future P5+ work that wants a self-service GDPR portal.

**Accepted design (I4):** `target_id` is a `CharField` rather than a polymorphic FK. If an admin hard-deletes a `PublicSearchEntry` (Django admin's default delete button), AuditLog rows still reference the now-dead PK. This is **intentional** — audit logs are historical records, not live state. Hard-delete is discouraged via admin `has_delete_permission=False` on `PublicSearchEntryAdmin` for cosigned entries; soft-removal via `removed_at` is the supported path.

### New: `members.models.RemovalRequest`

Per-request ephemeral record. Stores enough to authorize the email-confirmation flow and to write AuditLog entries on completion.

```python
def _make_token() -> str:
    """Mirrors cooptation.models._make_token — opaque random token."""
    import secrets
    return secrets.token_urlsafe(32)


class RemovalRequest(models.Model):
    """A public 'Retirer mon nom' request awaiting email confirmation.

    Created when the visitor submits the removal form; rendered
    redundant once the entry is removed (via on_delete=CASCADE) but
    the AuditLog entries about the request remain.
    """

    STATUS_CHOICES = [
        ("pending_confirmation", "En attente de confirmation"),
        ("confirmed",             "Confirmée — retrait exécuté"),
        ("expired",               "Expirée — non confirmée"),
    ]

    entry = models.ForeignKey(
        "members.PublicSearchEntry",
        on_delete=models.CASCADE,
        related_name="removal_requests",
    )
    requester_email = models.EmailField()
    reason = models.CharField(max_length=200, blank=True)
    confirm_token = models.CharField(max_length=64, unique=True, db_index=True, default=_make_token)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="pending_confirmation")
    requester_ip = models.GenericIPAddressField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()  # filled in by save() below

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = (self.requested_at or timezone.now()) + timedelta(days=30)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [models.Index(fields=["status", "expires_at"])]
```

**`expires_at = requested_at + 30 days`** (C2): aligns with GDPR Art. 12's one-month response window for data-subject requests. A vacationing requester who needed 7 days to notice the email won't lose the request.

### Modified: `members.models.PublicSearchEntry`

P4a's `removal_token = CharField(..., null=True, blank=True)` becomes:

```python
removal_token = models.CharField(
    max_length=64,
    unique=True,
    default=_make_token,
)
```

A data migration (`0008_*`) populates `removal_token` for any existing entries (likely zero at the time of P4b deploy, since the public list section was hidden in P4a) and removes `null=True/blank=True`.

**Justification for the token vs PK in URL:** opaque tokens prevent casual enumeration of entry count. At our scale (0-30 entries) the privacy gain is small but the cost is trivial — the field already existed.

### Migration impact

- `members/0008_auditlog_removalrequest_and_more.py` — creates two models + populates / tightens `removal_token`. Backward-compatible.
- No schema-breaking changes.
- No data loss possible on rollback (additive).

---

## 3. URLs, views, page composition

### New URL routes (in `members/urls.py`)

| Route | Method | Handler | Notes |
|-------|--------|---------|-------|
| `/retrait/<entry_token>/` | GET | `removal_request_form_view` | Full page, form with entry context |
| `/retrait/<entry_token>/` | POST | same | Form submit; rate-limited 5/h per IP |
| `/retrait/merci/` | GET | `removal_request_done_view` | "Check your email" success page |
| `/retrait/confirme/<confirm_token>/` | GET | `removal_confirm_view` | Idempotent — clicking twice is fine |
| `/retrait/expire/` | GET | `removal_expired_view` | Static page for expired/invalid tokens |

`/retrait/*` is added to:
- `LOGIN_REQUIRED_WHITELIST` in `alumni/settings/base.py`
- `BASIC_AUTH_PUBLIC_PREFIXES` in `core/middleware.py` (so SEO crawlers and anonymous visitors can reach the flow on staging)

### View behavior

**`removal_request_form_view`**
- `GET`: render form (CharField for email, optional CharField for reason, hidden CSRF). Show entry preview ("Vous demandez le retrait de **Idrissa S.** · années 1980-1983"). 404 if `entry_token` doesn't match any `PublicSearchEntry`.
- `POST`: validate, create `RemovalRequest` with `status=pending_confirmation`, fresh `confirm_token`, capture `requester_ip`. Send `removal_confirmation_pending` email. Write `ghost.removal.requested` AuditLog. Redirect to `/retrait/merci/`.
- **Works regardless of `PUBLIC_GHOST_LIST_ENABLED` flag** (I3) — removal respects consent independent of public visibility.
- **Rate limit: only on POST** (C3) — `@ratelimit(key="ip", rate="5/h", method="POST", block=True)`.

**`removal_confirm_view`** — idempotent state machine:
- `RemovalRequest` not found → render `removal_expired_or_invalid.html`
- `status=pending_confirmation` AND `expires_at > now`:
  - Set `entry.removed_at=now`, `entry.removed_reason = request.reason or "Retrait demandé par la personne concernée"`
  - Set `request.status=confirmed`, `request.confirmed_at=now`
  - Write `ghost.removal.confirmed` + `ghost.removal.executed` AuditLog entries
  - Send `removal_completed` to requester + `admin_removal_notification` to staff
  - Render `removal_confirmed.html`
- `status=pending_confirmation` AND `expires_at <= now` → mark `status=expired`, render expired page
- `status=confirmed` → render success page anyway (idempotent)
- `status=expired` → render expired page

**`removal_request_done_view`** — static template, French copy: "Vérifiez votre boîte mail, le lien de confirmation expire dans 30 jours."

**`removal_expired_view`** — static template, French copy: "Lien expiré ou invalide. Vous pouvez recommencer la procédure depuis la page d'accueil."

### Template files

- `members/templates/members/removal_request_form.html`
- `members/templates/members/removal_request_done.html`
- `members/templates/members/removal_confirmed.html`
- `members/templates/members/removal_expired_or_invalid.html`

All extend `base.html` and inherit `{% block robots %}` default (`noindex` — these pages should not be indexed; the entry tokens are not secrets but the URLs are not for crawler consumption).

### Public landing template change (`templates/core/landing.html`)

Add a "Retirer mon nom" link in each ghost card — discreet styling so it doesn't dominate but is always findable for the person who matters:

```django
<p class="mt-2 text-xs text-secondary">
    <a href="{% url 'members:removal_request_form' entry.removal_token %}"
       class="underline hover:text-tertiary">
        {% trans "Retirer mon nom" %}
    </a>
</p>
```

---

## 4. Emails, signal handlers, operational

### Email senders (`members/emails.py` — new file, mirrors `cooptation/emails.py`)

Three thin wrapper functions over `alumni.email.send_email`:

```python
def send_removal_confirmation_pending(removal_request) -> None:
    """To the requester after they submit the form. Contains the
    confirmation link and the entry preview so they can verify they're
    removing the right person."""
    send_email(
        removal_request.requester_email,
        "members/removal_confirmation_pending",
        {"request": removal_request, "entry": removal_request.entry},
    )


def send_removal_completed(removal_request) -> None:
    """To the requester after auto-execution. Acknowledgment, no action
    required. Includes a 'this was a mistake' note pointing at the admin
    contact email."""
    send_email(
        removal_request.requester_email,
        "members/removal_completed",
        {"request": removal_request, "entry": removal_request.entry},
    )


def send_admin_removal_notification(removal_request) -> None:
    """FYI to all active staff after auto-execution. Transparency, not
    action-required. Lets admins notice patterns (e.g., 5 removals in
    1 minute = bot attack)."""
    User = get_user_model()
    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True).values_list("email", flat=True)
    )
    if not staff_emails:
        return
    send_email(
        staff_emails,
        "members/admin_removal_notification",
        {"request": removal_request, "entry": removal_request.entry},
    )
```

### Email templates (new directory `members/templates/emails/members/`)

Three template families, each with `.subject.txt`, `.txt`, `.html`:

| Family | Subject (FR) | Body summary |
|--------|--------------|---------------|
| `removal_confirmation_pending` | "Confirmez le retrait de votre nom" | Greeting + entry preview + confirmation button (link to `/retrait/confirme/<token>/`) + "Si vous n'avez pas fait cette demande, ignorez ce message" + 30-day expiry note |
| `removal_completed` | "Votre nom a été retiré" | "Le nom suivant a été retiré de la liste publique : [...]. Cette action est définitive. Si c'était une erreur, contactez l'équipe à [admin email]." |
| `admin_removal_notification` | "[admin] Retrait exécuté : [Idrissa S.]" | "Un retrait public a été exécuté à [datetime]. Détails : entry pk, requester email, reason. Lien admin pour réviser/annuler." |

All bodies use `{{ site_url }}` for absolute links (already injected by `alumni.email.send_email`'s context — already shipped in P4a).

### Signal handlers (`members/signals.py` — new file, wired in `members/apps.py:MembersConfig.ready()`)

```python
"""Signals that translate ORM events into AuditLog entries.

These hooks intentionally use signals (not explicit calls in admin /
service code) so the audit trail is automatic — adding a new way to
sign off or remove an entry doesn't require remembering to write to
AuditLog. The cost: signal handlers are easy to miss when grepping;
each handler has an explicit comment naming the audit hook.
"""

@receiver(post_save, sender=PublicSearchEntry)
def _audit_entry_created(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            actor=None,
            action="ghost.entry.created",
            target_type="members.PublicSearchEntry",
            target_id=str(instance.pk),
            metadata={"first_name": instance.first_name, "last_name_initial": instance.last_name_initial},
        )


@receiver(m2m_changed, sender=PublicSearchEntry.added_by_admins.through)
def _audit_signoff_change(sender, instance, action, pk_set, **kwargs):
    """Audit hook for ghost-entry signoffs. Fires post_add and post_remove."""
    if action not in ("post_add", "post_remove"):
        return
    audit_action = "ghost.entry.signed_off" if action == "post_add" else "ghost.entry.signoff_removed"
    User = get_user_model()
    for admin_pk in (pk_set or ()):
        admin = User.objects.filter(pk=admin_pk).only("pk", "email").first()
        AuditLog.objects.create(
            actor=admin,
            action=audit_action,
            target_type="members.PublicSearchEntry",
            target_id=str(instance.pk),
            metadata={
                "signer_pk": admin_pk,
                "signer_email": admin.email if admin else "",
                "signoff_count_after": instance.added_by_admins.count(),
            },
        )


@receiver(pre_delete, sender=RemovalRequest)
def _audit_removal_request_cancelled(sender, instance, **kwargs):
    """If admin manually deletes a pending RemovalRequest from Django admin,
    record the cancellation before the row vanishes (I2 from spec review)."""
    if instance.status == "pending_confirmation":
        AuditLog.objects.create(
            actor=None,
            action="ghost.removal.cancelled",
            target_type="members.RemovalRequest",
            target_id=str(instance.pk),
            metadata={
                "entry_pk": instance.entry_id,
                "requester_email": instance.requester_email,
                "reason": instance.reason,
            },
        )
```

### Admin registrations (extend `members/admin.py`)

- **`RemovalRequestAdmin`** — `list_display`: entry, requester_email, status, requested_at, expires_at. `list_filter`: status. Read-only on requester_email + reason + token + timestamps. Allow delete (which fires the cancellation signal).
- **`AuditLogAdmin`** — `list_display`: created_at, actor, action, target_type, target_id. `list_filter`: action, target_type. `search_fields`: action, target_type, target_id. **Read-only on every field** (`has_add_permission=False`, `has_change_permission=False`, `has_delete_permission=False`). Append-only log.

### Operational

- **No new env vars.** All new behavior is governed by existing `EMAIL_BACKEND`, `RESEND_API_KEY`, `SITE_URL`.
- **`PUBLIC_GHOST_LIST_ENABLED=True` flip** — done by operator in Railway dashboard immediately after P4b deploy is green. The flip is the explicit "go live" moment for the public ghost list.
- **No cron changes for P4b.** Quarterly review automation is P4c.

---

## 5. Testing & rollout

### Test budget — ~22-28 new tests, total suite reaches ~310

**Model tests** (`members/tests/test_audit_log.py`)
- AuditLog admin's `has_change_permission` returns False (append-only at admin layer)
- `target_id` accepts string PKs
- `metadata` JSONField accepts dict, lists, nested structures
- Indexes on `(target_type, target_id)` and `(action, -created_at)` exist (introspect via migration state)

**Model tests** (`members/tests/test_removal_request.py`)
- `confirm_token` is unique
- `expires_at` defaults to `requested_at + 30 days`
- `status` defaults to `"pending_confirmation"`
- Cascade-delete: deleting a `PublicSearchEntry` deletes its `RemovalRequest` rows but leaves AuditLog entries

**Public removal view tests** (`members/tests/test_removal_views.py`)
- `GET /retrait/<token>/` valid: 200, form rendered, entry preview shown
- `GET /retrait/<token>/` unknown token: 404
- `POST /retrait/<token>/` valid: creates `RemovalRequest`, sends `removal_confirmation_pending` email, redirects to `/retrait/merci/`
- `POST /retrait/<token>/` rate limit: 6th submission within 1h returns 429
- `POST /retrait/<token>/` works when `PUBLIC_GHOST_LIST_ENABLED=False` (I3)
- `GET /retrait/confirme/<token>/` valid + pending: sets `entry.removed_at`, marks request confirmed, sends 2 emails (requester + admin staff), 200
- `GET /retrait/confirme/<token>/` already confirmed (idempotent): 200, success page (no second-execution side effects)
- `GET /retrait/confirme/<token>/` expired: marks status `expired`, renders expired page
- `GET /retrait/confirme/<token>/` unknown token: renders expired/invalid page
- `removal_confirm_view` writes 2 AuditLog entries (`ghost.removal.confirmed` + `ghost.removal.executed`)
- After auto-execution, the entry no longer appears in the public ghost queryset (`removed_at` set)
- Basic-auth bypass works: with `BASIC_AUTH_REQUIRED=True`, `/retrait/<token>/` returns non-401

**Signal tests** (`members/tests/test_audit_signals.py`)
- Creating a `PublicSearchEntry` writes `ghost.entry.created` to AuditLog
- Adding an admin to `entry.added_by_admins` writes `ghost.entry.signed_off` with the right `signoff_count_after`
- Adding 2 admins in one `.add(a, b)` call writes 2 separate AuditLog entries (one per admin)
- Removing an admin via `.remove(a)` writes `ghost.entry.signoff_removed`
- Deleting a `pending_confirmation` `RemovalRequest` from admin writes `ghost.removal.cancelled` (pre_delete fires before the row is gone)
- Deleting a `confirmed` `RemovalRequest` does NOT write `ghost.removal.cancelled` (only pending status triggers the audit hook)

**Email template tests** (`members/tests/test_removal_emails.py`)
- All 3 templates render without crashing
- `removal_confirmation_pending` body contains the absolute confirmation URL (with `{{ site_url }}` substituted)
- `removal_completed` body confirms the entry's name + initial + years
- `admin_removal_notification` recipient is the union of all `is_staff=True, is_active=True` user emails
- `admin_removal_notification` is NOT sent if no staff exist (early return, no error)

**Landing template change tests** (extends `core/tests/test_landing_view.py`)
- When `PUBLIC_GHOST_LIST_ENABLED=True` and entries are published, each rendered card contains a "Retirer mon nom" link with the correct `removal_token` in the href
- When `PUBLIC_GHOST_LIST_ENABLED=False`, the card section is absent → no removal links present (already covered by existing test)

**A11y test** (extends `core/tests/test_a11y.py`)
- "Retirer mon nom" link has accessible text (not just an icon)

### Rollout sequence

**Pre-deploy**
- Nothing content-wise. Email copy is in templates (French, mirrors existing P3 voice).

**Code rollout**
1. Branch + plan + execute via `superpowers:subagent-driven-development` (same pattern as P3, P4a)
2. Open PR; visual changes are minimal (just the small "Retirer mon nom" link + 4 new templates)
3. Merge to main → Railway auto-deploys

**Post-deploy ops (5-10 min)**
1. Verify the deploy is green (Railway → Deployments → Active)
2. Smoke-test the removal flow end-to-end:
   - In Django admin, create a test `PublicSearchEntry` with `first_name="Test"`, `last_name_initial="Z."`, `years_at_ceg=[1980]`
   - Add 2 admins to its `added_by_admins`
   - Visit `/retrait/<token>/` in incognito, submit form with your real email
   - Receive `removal_confirmation_pending` email at your inbox; click the link
   - Verify: `entry.removed_at` is now set; you got `removal_completed`; admin staff got `admin_removal_notification`; AuditLog has 5+ entries
3. **Flip the feature flag**: Railway → app service → Variables → set `PUBLIC_GHOST_LIST_ENABLED=true` → save → service redeploys
4. Verify: visit `https://villageretrouvailles.com/` in incognito. The "Nous recherchons aussi…" section should now render the empty-state copy ("Liste en cours de constitution — bientôt") since the test entry was just removed.
5. (Optional) Ask one or two trusted admins to add a real ghost entry via Django admin and add themselves + you as cosigners. Verify the entry now appears publicly with its "Retirer mon nom" link.

**Tag** `v0.4.0b-public-surface-governance`, push, update `STATUS.md`.

### Rollback plan

If the removal flow misfires in production:
1. `git revert <merge-commit>` on `main`, push.
2. Railway redeploys the revert (~3 min).
3. The two new tables (`AuditLog`, `RemovalRequest`) remain in the database with their data intact — additive migrations don't get reversed by a code revert. No data loss.
4. If you also need to flip the public ghost section back off: set `PUBLIC_GHOST_LIST_ENABLED=false` in Railway env vars.

If the rollback itself causes issues, fall back to tag `v0.4.0a-public-surface`.

### What does NOT change

- P3 cooptation flow: untouched
- P4a landing page: only the ghost card template gains a small "Retirer mon nom" link
- Existing 286 tests: all stay green
- Cooptation cron: untouched (P4c will add the quarterly-review sweep)

---

## 6. Risks & accepted tradeoffs

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Griefer with their own email removes a stranger's entry | Medium | Email confirmation gate + AuditLog (re-add possible via 2-admin gate); minimal data exposed → low grief value |
| Bot abuse on form submit | Medium | 5/h rate limit per IP on POST `/retrait/<entry-token>/` |
| Confirmation email delivered to spam | Low-Medium | Resend domain verification (DKIM/SPF/DMARC already configured for villageretrouvailles.com) |
| Hard-deletion of `PublicSearchEntry` orphans AuditLog `target_id` | Low | `PublicSearchEntryAdmin.has_delete_permission` discourages hard-delete; `removed_at` is the supported soft-removal path; AuditLog rows referencing deleted entries are intentional historical artifacts |
| GDPR Art. 15 access query for non-staff requesters needs JSON query | Low | Documented limitation; sequential scan workable at our scale (~few hundred AuditLog rows) |
| Admin manually deletes a confirmed `RemovalRequest` | Very Low | `pre_delete` signal only audits if `status=pending_confirmation`; confirmed requests' history lives in 2+ existing AuditLog entries (`requested`, `confirmed`, `executed`) |
| `expires_at = 30d` set too generously and a vacationing requester confirms after 30d | Low | Friendly expired page invites them to re-submit; the alternative (7d default) was rejected for GDPR alignment |

---

## 7. Open content questions (not blocking spec, blocking deploy)

1. **Admin contact email** — what email address goes in the `removal_completed` template's "if it was a mistake, contact us at..." line? Likely `noreply@villageretrouvailles.com` is wrong; we want `admin@villageretrouvailles.com` or the team's group email. Decide before deploy.
2. **Email copy review** — first-draft French in templates; one team member should read and refine before launch.

---

## 8. References

- Master spec § 6.5: `docs/superpowers/specs/2026-05-01-alumni-platform-design.md`
- P4a spec: `docs/superpowers/specs/2026-05-03-public-surface-design.md`
- P4a plan: `docs/superpowers/plans/2026-05-03-public-surface.md`
- Status tracker: `docs/superpowers/STATUS.md`
- Existing PublicSearchEntry: `members/models.py`
