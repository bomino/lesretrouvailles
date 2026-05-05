# DMARC monitoring runbook

> Quarterly verification + aggregate-report review for the production sending domain.
>
> Master spec §313: "DMARC en `p=quarantine` minimum. Surveillance DMARC reports trimestrielle."

**Production sending domain:** `villageretrouvailles.com`
**Email provider:** Resend (handles SPF + DKIM signing automatically once DNS records are in place)
**Spec:** [docs/superpowers/specs/2026-05-05-p6c-dmarc-retention-design.md](../superpowers/specs/2026-05-05-p6c-dmarc-retention-design.md)

---

## Why this matters

Without correct SPF/DKIM/DMARC alignment on outgoing mail, our cooptation emails, parrain reminders, and In Memoriam notifications get filed as spam by Gmail, Outlook, and others. At our scale (~200 members, ~hundreds of emails per month), bad alignment is an existential issue for the platform's actual purpose.

`p=quarantine` is the master spec minimum: receiving servers should put unauthenticated mail claiming to be from us in spam, not the inbox. `p=reject` is stricter and acceptable; we don't want `p=none` (monitor-only) past the initial setup phase.

---

## 1. One-time DNS setup (verify; do once if missing)

### 1.1 Confirm SPF + DKIM are present

These are set up by Resend during domain onboarding. Verify from any machine:

```bash
# SPF — should include "include:_spf.resend.com" (or similar Resend reference)
dig TXT villageretrouvailles.com | grep -i spf

# DKIM — Resend uses selectors like "resend._domainkey"
dig TXT resend._domainkey.villageretrouvailles.com
```

If either is missing or returns NXDOMAIN, **DMARC is not yet meaningful** — fix the upstream issue first via the Resend dashboard → Domains → click the domain → "DNS Records" tab → copy values to your DNS host (Cloudflare, registrar, etc).

### 1.2 Confirm the DMARC record

```bash
dig TXT _dmarc.villageretrouvailles.com
```

Expected (one TXT record):

```
"v=DMARC1; p=quarantine; rua=mailto:<aggregate-report-address>; pct=100; aspf=r; adkim=r;"
```

Field-by-field check:

| Field | Required value | Why |
|---|---|---|
| `v=DMARC1` | exact | Protocol version. |
| `p=` | `quarantine` or `reject` | The action receivers take on unaligned mail. Master spec minimum is `quarantine`. |
| `rua=` | `mailto:<address>` | Where aggregate (XML) reports go. Required to do quarterly review at all. See §1.3 below for picking an address. |
| `pct=` | `100` | Percentage of mail subject to the policy. Anything less is a soft rollout — fine during initial onboarding, not for steady state. |
| `aspf=` / `adkim=` | `r` (relaxed) or `s` (strict) | Alignment mode for SPF / DKIM. Relaxed is the safer default; strict is fine if Resend's DNS setup uses exact alignment. |

If `rua=` is missing → §1.3.
If `p=none` → bump to `quarantine` once you've watched a quarter of reports without alignment failures.

### 1.3 Set up aggregate-report ingestion

Pick **one** path:

#### Path A — free hosted viewer (recommended)

[dmarcian.com](https://dmarcian.com) has a free tier that easily covers our volume.

1. Sign up at dmarcian.com with the operator's email.
2. Add the domain `villageretrouvailles.com` to the dashboard.
3. dmarcian gives you an `rua=` address that looks like `<random>@rua.dmarcian.com`.
4. Update the DMARC TXT record to use that address. Wait for DNS propagation (5–60 min).
5. Within 24 hours dmarcian's dashboard starts showing the first reports.

Alternatives if dmarcian doesn't fit:
- [Postmark DMARC monitoring](https://dmarc.postmarkapp.com/) — also free for our volume.
- [URIports](https://www.uriports.com/) — free tier is small but enough.

#### Path B — self-hosted email forwarding (if you'd rather not use a SaaS)

1. Set up a forwarding alias like `dmarc-reports@villageretrouvailles.com` → operator's personal inbox.
2. Set `rua=mailto:dmarc-reports@villageretrouvailles.com` in the DMARC TXT.
3. The aggregate reports arrive as XML attachments — readable but unfriendly. Process manually or feed into a parser like `parsedmarc`.

Choose Path A unless you already enjoy reading XML. The free tier on dmarcian is sufficient.

---

## 2. Quarterly review (every 90 days)

Calendar reminder: every 90 days, log in to the report viewer (or check the inbox if you went Path B) and answer three questions:

### 2.1 Is alignment ≥ 95% for legitimate sources?

Look at the "DMARC compliance" or "Pass rate" column. If it dropped below 95%, something is sending mail claiming to be us without proper alignment. Causes:

- A new third-party service we wired up (CRM, newsletter tool) without configuring SPF/DKIM for the domain.
- A misconfigured forwarder (Gmail forwarding old mail to a new address can break SPF; that's normal noise — should be a small percentage).
- An actual phishing attempt impersonating the domain.

### 2.2 Are there unexpected sending sources?

The viewer lists IP addresses and SPF/DKIM domains that have sent mail claiming to be us. Expected sources today:
- Resend's IP ranges (the legit ones)
- Forwarders (Gmail, etc.) — small volume, expected to fail SPF but pass DKIM if the body wasn't modified

Anything else (esp. unfamiliar IP ranges, foreign hosters) → investigate. If it's an obvious phishing source, no action needed beyond confirming `p=quarantine` is doing its job (the receiving servers will quarantine those messages on our behalf).

### 2.3 Have receivers stopped reporting?

DMARC reports come from large mailbox providers (Google, Microsoft, Yahoo, etc.). If reports stop arriving for >2 weeks across all of them, the `rua=` destination might be broken. Check:

```bash
dig TXT _dmarc.villageretrouvailles.com
```

Confirm `rua=` still points where you expect.

---

## 3. What to do if alignment drops

If the quarterly check shows alignment <95% for legit sources and you can't immediately fix the upstream cause:

1. **Loosen temporarily** — change `p=quarantine` to `p=none` so legit-but-unaligned mail still reaches inboxes during the diagnosis window.
2. Investigate which sender is breaking alignment (the report viewer pinpoints by IP and domain).
3. Fix the alignment issue (most common: missing DKIM key on a forwarder, or a third-party service sending without SPF authorization).
4. **Re-tighten** to `p=quarantine` once aligned percentage is back above 95%.

Document the incident + resolution in a comment on the relevant Linear/Notion ticket (or this runbook's bottom).

---

## 4. Pre-soft-launch checklist (before P7)

Before the soft launch sends meaningful volume, run through this checklist once:

- [ ] `dig TXT villageretrouvailles.com` → SPF includes Resend.
- [ ] `dig TXT resend._domainkey.villageretrouvailles.com` → DKIM key present.
- [ ] `dig TXT _dmarc.villageretrouvailles.com` → `p=quarantine` (or stricter), `rua=` set.
- [ ] First DMARC aggregate report arrived in the dashboard within 48 hours of sending the first batch.
- [ ] 95%+ of legit-source mail aligned in the first report.

If any of those fail, hold the soft launch until resolved — bouncing 10% of cooptation invitations to spam at launch is a brand and operational risk we shouldn't take voluntarily.
