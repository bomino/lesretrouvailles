# P9.3 — WhatsApp Phase A: outbound auth (magic-link auto-DM)

**Status:** 📝 Spec stub (planned). Part of milestone `v1.3.0-engagement-loop`.
**Branch (planned):** `feat/whatsapp-phase-a`
**Sibling phases:** P9.1 (hymne, ships first; runs WA paperwork in parallel), P9.2 (offline PWA)
**Depends on:** P9.1's WA paperwork side-task being complete (Meta business account verified, dedicated number registered, display name approved, auth template approved).

## A. Origin

Today's magic-link flow has a manual operator hop:

1. Member pings the super-admin on WhatsApp: "j'ai perdu mon accès."
2. Operator runs `python manage.py reissue_login_link <username>` on a laptop.
3. Operator copy-pastes the printed URL back into WhatsApp.
4. Same shape for cooptation acceptance: operator sends the activation link manually.

At ~200 members with a realistic 30% reissue rate over the platform's life, that's ~60 manual round-trips per super-admin per cycle. The operator becomes the bottleneck and single point of failure. **Phase A automates the outbound side only:** the platform sends magic links via WhatsApp Cloud API directly to the member's number. No inbound bot. No keyword commands. Operator stays in the loop for human-mediated escalations, but stops being the typist.

## B. Goals

1. `python manage.py reissue_login_link <username>` triggers an automated WhatsApp DM to the member's `Member.whatsapp` number with the magic link, in addition to printing the URL (printing kept as escape hatch).
2. `cooptation.services.approve_application` triggers the same WhatsApp DM with the activation link, replacing the email-only flow for members with WhatsApp numbers.
3. Operators can verify what was sent via `AuditLog.whatsapp.send` rows.
4. A delivery receipt webhook updates the audit row when Meta confirms delivery / read.
5. Failure modes are explicit: invalid number, opt-out, Meta API error → audit row marked failed, operator gets the printed URL fallback.
6. Cost dashboard tile in `/gestion/`: `wa_outbound_count_30d` so the operator sees what Meta will bill (Niger is on a low-cost tier; expectation is < $5/month).

## C. Non-goals (explicit)

- **No inbound bot.** Members can't WhatsApp the platform yet. That's Phase B (separate spec when scoped).
- **No member-initiated photo upload via WhatsApp.** That's Phase C.
- **No marketing or broadcast messages.** Only transactional auth/activation messages.
- **No member-facing opt-out toggle in v1.** Members are expected to want their magic link delivered to the same channel they registered on. If a real opt-out request comes in, we add it as a follow-up.
- **No multi-template support.** Single auth template, single message shape. Future templates added with their own approvals.
- **No fallback to email when WA fails.** If WA send fails, operator escape hatch is the printed URL — they can DM it manually.
- **No charter version bump beyond a one-line addition** acknowledging WhatsApp Cloud API as a transactional-auth processor.

## D. Audience

Same as platform. The member-facing change is invisible: they get a magic link DM as before, just from the bot number instead of the operator's personal number. Operator-facing change: lighter workload, audit-log visibility.

## E. Architecture

### E.1 New `whatsapp/` Django app

Mirrors the existing Cloudinary/Storage client pattern. Model-less (no DB rows live in `whatsapp/`; audit lives in `members.AuditLog`).

```
whatsapp/
    __init__.py
    apps.py                       # AppConfig
    client.py                     # RealWhatsAppClient + FakeWhatsAppClient + factory
    services.py                   # send_magic_link(), send_activation_link()
    tasks.py                      # django-q queued task wrappers
    views.py                      # webhook endpoint
    urls.py
    tests/
        conftest.py
        test_client.py            # Real (mocked HTTP) + Fake parity
        test_services.py          # send_* business logic, audit writes
        test_webhook.py           # signature verification, idempotency, status updates
```

### E.2 Client abstraction

**`RealWhatsAppClient`** wraps Meta Graph API calls:

```python
class RealWhatsAppClient:
    def send_template(
        self,
        to: str,                     # E.164 digits-only
        template_name: str,          # e.g., "magic_link_v1"
        variables: list[str],
    ) -> WhatsAppSendResult:
        # POST https://graph.facebook.com/v20.0/<phone_id>/messages
        # Headers: Authorization: Bearer <system_user_token>
        # Body: { messaging_product: "whatsapp", to, type: "template", template: {...} }
        ...
```

Returns a small dataclass: `WhatsAppSendResult(message_id, status, error)`.

**`FakeWhatsAppClient`** records calls in a class-level list (mirrors `FakeCloudinary`, `FakeStorage`); used by all tests; reset between tests via fixture.

**Factory:** `get_whatsapp_client()` reads `settings.WHATSAPP_CLIENT_PATH` (defaults to fake; `prod.py` sets `alumni.whatsapp.RealWhatsAppClient`). Mirrors the existing settings pattern.

**Settings (new, all in `prod.py`/env):**
- `WHATSAPP_PHONE_NUMBER_ID` — Meta phone-number ID after registration.
- `WHATSAPP_BUSINESS_ACCOUNT_ID` — Meta WABA ID.
- `WHATSAPP_ACCESS_TOKEN` — system-user token (long-lived).
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN` — random secret for webhook subscribe.
- `WHATSAPP_APP_SECRET` — for HMAC signature verification on inbound webhooks.
- `WHATSAPP_TEMPLATE_MAGIC_LINK` — `magic_link_v1` (or whatever Meta approved).

### E.3 Background worker (django-q)

The current stack has no async worker. Adding django-q because:

- **Single dependency**, not a stack (Redis-free unlike Celery).
- **Postgres-backed broker** — reuses existing DB; no new Railway service.
- **Lightweight admin** at `/admin/django_q/` for inspecting failed tasks (super-admin only via the existing `GestionAdminSite` gate).
- **Cron capability** — could replace `process_cooptation_deadlines` cron eventually (out of scope for P9.3 but a nice optionality).

**Setup:**
- `pyproject.toml`: add `django-q2` (the maintained fork; `django-q` original is unmaintained).
- `INSTALLED_APPS`: append `django_q`.
- `Q_CLUSTER` settings dict in `base.py` (concurrency 2, retry 60s, timeout 30s, ORM-broker).
- New Railway service: `q-cluster` running `python manage.py qcluster`. Same Docker image, different command. ~$5/month additional Railway cost.
- Migrations: django-q owns its tables; one `migrate` cycle on first deploy.

**Tasks:**
- `whatsapp.tasks.send_magic_link_task(member_id, link_url)` — wraps `services.send_magic_link()`. Idempotent (re-running same call is safe; audit row uses Meta's `wa_message_id` for deduplication).
- Retry policy: 3 retries with exponential backoff for Meta API 5xx; 0 retries for 4xx (bad input — fail loud, operator sees the failure in audit log).

### E.4 Webhook endpoint

`POST /webhooks/whatsapp/` and `GET /webhooks/whatsapp/` (Meta's verify handshake on subscribe).

- **GET handler:** echoes `hub.challenge` if `hub.verify_token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN`. One-time, when subscribing the webhook in Meta admin.
- **POST handler:**
  - Verifies HMAC: `X-Hub-Signature-256` header against `hmac.new(WHATSAPP_APP_SECRET, body, sha256).hexdigest()`. Reject 403 on mismatch.
  - Parses Meta's webhook payload. Phase A only handles `statuses` events (delivered, read, failed) — message events (`messages`) are received but ignored (logged as `whatsapp.inbound.ignored`).
  - For each status event, find the matching `AuditLog` row by `wa_message_id` in metadata, update its status field, write a new `whatsapp.delivery_receipt` row.
  - Idempotency: status events can be retried; updating the same row N times with the same status is safe.
  - Returns 200 OK fast (<500ms) regardless of internal processing — Meta retries on timeout.

### E.5 Hooks into existing flows

**`reissue_login_link` command:**
- Default behavior: still prints the URL to stdout (escape hatch preserved).
- New default: ALSO enqueues `send_magic_link_task` if the target member has `whatsapp` set.
- New flag `--no-dm`: skip the queued send (for emergencies, debugging, members with explicit no-WA).
- New flag `--dry-run`: print what would happen, don't enqueue or print real URL.

**`cooptation.services.approve_application`:**
- After creating the `Member` and `User`, if `member.whatsapp` is set: enqueue `send_activation_link_task` (separate task name; uses the same template approved as auth).
- If not set: existing email-only flow.
- If both: send via WA only (avoid double-link confusion).

### E.6 AuditLog extensions

New action choices added to `AuditLog.ACTION_CHOICES`:

- `whatsapp.send.queued` — task enqueued.
- `whatsapp.send.success` — Meta returned a `messages[0].id`.
- `whatsapp.send.failed` — Meta returned an error or timeout.
- `whatsapp.delivery_receipt` — Meta webhook reported delivered/read/failed status.
- `whatsapp.inbound.ignored` — inbound message received but Phase A doesn't handle (Phase B will).

Metadata always includes `member_full_name` (per project rule), `wa_message_id` when known, `template_name`, `error_code` for failures.

### E.7 Cost dashboard tile

In `/gestion/` dashboard, alongside existing KPI tiles, add:

- **WhatsApp envoyés (30j)** — count of `whatsapp.send.success` rows in last 30 days.
- **Échecs (30j)** — count of `whatsapp.send.failed`.
- Tooltip / link: "Voir le journal" → filtered audit log view.

### E.8 Charter / privacy doc update

One-line addition to existing privacy/charter doc acknowledging WhatsApp Cloud API (Meta) as a sub-processor for transactional authentication messages. No DPIA expansion required given existing email processor relationships and the transactional-only scope.

## F. Locked decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | API provider | **Meta Cloud API direct** | Cheapest; one number; no need for BSP abstraction. |
| 2 | Background worker | **django-q2** | Postgres-backed; no Redis; single new Railway service. |
| 3 | Client abstraction | **Real + Fake pattern** | Mirrors Cloudinary/Storage; tests stay unit-level. |
| 4 | Settings naming | `WHATSAPP_*` envs | Mirrors `CLOUDINARY_*` / `STORAGE_*` prefix convention. |
| 5 | Phone number | **Dedicated Niger SIM** confirmed by owner | One-time SIM cost; bot identity separate from any human's WA. |
| 6 | Inbound handling | **Log-and-ignore in Phase A** | Phase B adds command parsing; A doesn't break webhook subscription. |
| 7 | Email fallback when WA fails | **Out of scope** | Operator gets printed URL escape hatch; auto-fallback is Phase B. |
| 8 | Opt-out mechanism | **None in v1** | Member voluntarily registered with WA; transactional-only scope; revisit if real request lands. |
| 9 | Charter version | **Minor amendment, no version bump** | Transactional sub-processor addition; no scope change. |
| 10 | Templates | **Single `magic_link_v1`** initially | One approval at a time; activation reuses same template (variables differ). |
| 11 | Retry policy | **3 retries 5xx, 0 retries 4xx** | Standard transactional pattern; bad input fails loud. |
| 12 | Dashboard tile | **30-day rolling counts** | Operator-friendly; matches Meta's billing window. |

## G. Open questions

1. **Single template or two?** Magic-link reissue vs. cooptation activation — same template body works (`Bonjour {{1}}, voici votre lien : {{2}}`), or split for clearer auditing? Recommendation: one template, one approval, save calendar time.
2. **Member opt-out signal.** If a member messages the bot "STOP" before Phase B exists, we ignore it. Is this acceptable for the v1 launch window? (Yes per non-goals; revisit if a real STOP comes in.)
3. **What happens for members with email AND whatsapp?** Currently default to email for cooptation acceptance. New default: WA. The email backend stays available for super-admin via `--email` flag on the command. OK?
4. **Bot identity in Gestion UI.** Operators viewing the audit log see "WhatsApp envoyé à Aïssa S. (#22790...)". Want to label it with the bot's display name? (Default yes — clear provenance.)

## H. Tasks (preliminary)

| # | Task | Notes |
|---|------|-------|
| 1 | Owner confirms Meta WA paperwork all complete (from P9.1 side-task) | **Blocking gate** |
| 2 | Add `django-q2` dependency + `Q_CLUSTER` settings + INSTALLED_APPS | Minimal config |
| 3 | First migration: django-q tables | Auto-generated |
| 4 | Create `whatsapp/` app skeleton (apps.py, urls.py, empty models.py) | Standard scaffold |
| 5 | `RealWhatsAppClient` + `FakeWhatsAppClient` + factory | TDD: parity tests |
| 6 | `services.py::send_magic_link` and `send_activation_link` | TDD: audit writes, idempotency, error paths |
| 7 | `tasks.py` — django-q wrapped versions of services | TDD: retry config, fail-loud on 4xx |
| 8 | Webhook view: GET (verify) + POST (HMAC + status updates) | TDD: signature verify, idempotency |
| 9 | `AuditLog.ACTION_CHOICES` extension for the 5 new actions | One-line change |
| 10 | Hook into `reissue_login_link` command (with `--no-dm`, `--dry-run` flags) | TDD: verify both paths |
| 11 | Hook into `cooptation.services.approve_application` | TDD: WA-preferred flow |
| 12 | Gestion dashboard tile (`wa_outbound_count_30d`) + filtered audit view | TDD: tile renders, count correct |
| 13 | Railway: new `q-cluster` service + WA env vars | Operator step; doc in launch runbook |
| 14 | Charter / privacy doc one-line update | `docs/legal/charte.md` (or wherever it lives) |
| 15 | Operator runbook: `docs/runbooks/whatsapp-bot.md` (subscribe webhook, rotate token, debug failures) | New doc |
| 16 | End-to-end manual QA: real send to operator's personal number with test member | Pre-merge gate |
| 17 | Full suite green; merge; tag `v1.3.0-engagement-loop` | Tag the milestone here |

## I. Risks

- **Meta approval slipping.** Display name or template rejection delays the build. **Mitigation:** P9.1 side-task starts paperwork early; have a fallback display name pre-decided.
- **Token rotation surprise.** Long-lived tokens still expire; without monitoring, sends start failing silently. **Mitigation:** dashboard shows `wa_outbound_failed_24h`; operator runbook has the rotation procedure documented.
- **Webhook signature regression.** A code change could break HMAC verification, causing all status updates to be silently dropped. **Mitigation:** dedicated test asserts both happy path + bad-signature 403; integration test signs with real-shape payload.
- **Cost surprise.** Niger pricing tier unconfirmed at scale. **Mitigation:** dashboard tile makes consumption visible; auth-template messages are the cheapest tier; cap messaging frequency in middleware if it ever spikes.
- **q-cluster failure invisibility.** If the worker dies, sends queue forever. **Mitigation:** Railway healthcheck on the worker process; super-admin sees a "queue depth" indicator on the dashboard if it grows beyond 10.
- **Send-to-self loop in tests.** A misconfigured local dev could accidentally send a real WhatsApp message. **Mitigation:** `dev.py` and `staging.py` set `WHATSAPP_CLIENT_PATH` to `FakeWhatsAppClient` explicitly; one passing test asserts this.
- **Member's WhatsApp number is wrong / belongs to someone else.** Magic link delivered to wrong person = full account takeover. **Mitigation:** existing operator-driven process for username changes (Gestion v1) requires confirmation of old number first; same trust assumption applies. Member responsible for keeping `Member.whatsapp` accurate.

## J. Out of scope (deferred to Phase B / Phase C)

- **Phase B — Inbound keyword bot.** STOP, AIDE, LIEN (self-service magic-link request), PROMO. Doable as ~3-day phase once Phase A is stable.
- **Phase C — Inbound media (photo upload via WhatsApp).** Member sends photo to bot → bot uploads to Cloudinary → super-admin moderation queue. Significantly more complex; only if usage signals demand.
- **Multi-language templates.** Hausa template if/when Hausa locale lands.
- **Outbound-broadcast announcements.** Marketing/Service tier templates; out-of-scope until charter framework supports them.
- **Two-factor auth via WhatsApp OTP.** Could replace magic links eventually; not now.
