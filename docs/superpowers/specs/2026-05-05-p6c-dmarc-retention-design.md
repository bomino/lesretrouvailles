# P6c — DMARC monitoring + AuditLog retention (design + plan, combined)

**Status:** Approved.
**Phase:** P6c — closes out P6 (Ops & RGPD).

## Goal

Two unrelated-but-tiny remaining items from P6's scope, shipped together to avoid a multi-week gap before P7:

1. **AuditLog 12-month retention** — master spec §9.4 says audit logs are kept 12 months then purged. The infrastructure (daily cron) exists; this just adds one step.
2. **DMARC monitoring** — master spec line 313 says "DMARC en `p=quarantine` minimum. Surveillance DMARC reports trimestrielle." Production already sends through Resend (handles SPF/DKIM); the work is verifying DNS, setting up aggregate-report ingestion, and documenting the quarterly review procedure.

Plus a one-paragraph STATUS note acknowledging the **Tigris-bucket-lifecycle gap** discovered during P6a (the master spec's "30-day rotation" is unimplementable on Railway's bucket backend; path-dedup keeps the bucket small).

## Non-goals

- Member-self-service RGPD flow (deferred — see P6b non-goals).
- DMARC report parsing / dashboard. Use a free hosted viewer (dmarcian, Postmark, or even raw email forwarding) — building a parser would be 2 weeks of work for marginal value at our scale.
- Cross-cloud DR for media backups. Tigris-only is the conscious tradeoff per P6a §A.

## Architecture

### A. AuditLog retention

New method on the existing `process_cooptation_deadlines` Command class:

```python
def _purge_old_audit_logs(self, now, retention_days: int = 365) -> int:
    cutoff = now - timedelta(days=retention_days)
    deleted, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()
    return deleted
```

Wired into `handle()` between `_purge_old_rejections` and the final `stdout.write`. The retention window (365 days) is the master spec's value; configurable via a constant at module scope so it can be tuned without re-tagging.

The `rgpd.member.purged` entries themselves get deleted along with everything else once they're 12 months old. That's correct per RGPD: the audit-log retention window applies uniformly. If we ever need to keep RGPD-purge audit entries longer for compliance, that becomes a follow-up phase that filters by action.

### B. DMARC monitoring

Operator-driven, no code changes. Runbook covers:

1. **Verify DNS state** — `dig TXT _dmarc.<domain>` should return a record like:
   ```
   v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@<domain>; pct=100; aspf=r; adkim=r;
   ```
   `p=quarantine` is the master spec's minimum; `p=reject` is stricter and acceptable.

2. **Set up aggregate-report ingestion** — pick one:
   - **Free hosted viewer** (recommended): sign up at [dmarcian.com](https://dmarcian.com) (free tier covers our volume), get an `rua=` address from them, paste into the DMARC TXT record. Reports auto-parse + visualize.
   - **Self-hosted email**: configure `rua=mailto:dmarc-reports@<domain>` and forward that mailbox. Works but the raw XML reports are unfriendly to read.
   - **Resend's deliverability dashboard**: covers send-side metrics but doesn't replace third-party DMARC reports (different data source).

3. **Quarterly review procedure** — calendar reminder for once per quarter:
   - Open the report viewer
   - Confirm the `pct` of mail aligned with our SPF/DKIM stays >95%
   - Investigate any spike in `quarantine`/`reject` from legitimate sources (could indicate a misconfigured forwarder or third-party sending on our domain without alignment)

4. **What to do if alignment drops** — document the rollback path: lower `p=` from `quarantine` to `none` temporarily, fix the alignment issue, then re-tighten.

## Tigris lifecycle gap acknowledgment

One-paragraph note in STATUS's P6c section (and a backref from P6a):

> Master spec §8.2 specifies "Sauvegardes médias purge effective dans la fenêtre de rétention 30 jours." Tigris on Railway does not support `PutBucketLifecycleConfiguration` with non-trivial rules (P6a discovery, runbook §1.2). The 30-day rotation is therefore not enforced today. Path-dedup keeps the bucket small (~500 MB peak at our scale); manual cleanup is the operational alternative. Revisit when Tigris adds support, or when scale forces a move to a different S3-compatible target.

## Tests (§G)

Two tests added to `cooptation/tests/test_process_deadlines.py`:

| # | Test | Asserts |
|---|---|---|
| 1 | `test_audit_log_retention_purges_entries_older_than_365_days` | After cron run, AuditLog rows with `created_at < now - 365d` are gone; the rest persist. |
| 2 | `test_audit_log_retention_handles_empty_queryset` | Cron run with no old entries succeeds; existing entries unchanged. |

## Files

### Create
- `docs/runbooks/dmarc.md`

### Modify
- `cooptation/management/commands/process_cooptation_deadlines.py` — add `_purge_old_audit_logs` + wire into `handle()`
- `cooptation/tests/test_process_deadlines.py` — 2 new tests
- `docs/superpowers/STATUS.md` — P6c row + section; flip P6 to Complete

No new pip deps. No migrations. No external infrastructure changes (the DNS work is already done by the operator who shipped to Railway with Resend).

## Tasks

- [ ] **Task 1**: AuditLog retention purge (write tests → implement → suite green → commit)
- [ ] **Task 2**: DMARC runbook (write `docs/runbooks/dmarc.md` → commit)
- [ ] **Task 3**: STATUS update (P6c row + section + Tigris note → commit → final pytest pass)
