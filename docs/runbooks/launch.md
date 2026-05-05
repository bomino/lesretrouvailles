# Soft launch runbook — Les Retrouvailles

> The end-to-end procedure for opening the platform to the existing CEG1 Birni WhatsApp community (~200 members).
>
> Companion runbooks: [`onboarding.md`](onboarding.md) (CSV import + WhatsApp DMs), [`dmarc.md`](dmarc.md) (email deliverability), [`restore.md`](restore.md) (media backup + restore drill), [`rgpd-purge.md`](rgpd-purge.md) (RGPD member deletion).

This is a one-time procedure. Steps 0-7 happen sequentially over a few weeks; Steps 8-9 are the post-launch operating mode.

---

## Step 0 — Pre-launch DB cleanup

The 6 `Member` rows currently in production are dev fixtures from `members/fixtures/seed_members.json`. Delete them so the launch starts from a clean slate.

### 0.1 — Inspect first

```bash
railway run --service lesretrouvailles python manage.py shell -c \
  "from members.models import Member; \
   [print(m.id, m.full_name, m.user.email) for m in Member.objects.all()]"
```

Confirm these are test rows (`First1 Last1` / `Niamey` / `Médecin`-type values), not real founders.

### 0.2 — Create the new super admin first

Before any deletion, ensure production never has a state without an admin:

```bash
railway run --service lesretrouvailles python manage.py createsuperuser
```

Use **your real email** + a strong password. This account:
- Signs in to `/admin/` for cleanup work
- Runs the bulk WhatsApp import
- Becomes the `actor` on cleanup-related audit log events
- Eventually becomes a regular member after the import (you fill in your own row in the roster CSV)

### 0.3 — Delete the test members

Sign in to `/admin/` → Members → select all rows → "Delete selected members". Cascades through `User` → `NotificationPreference` → `ConsentRecord` → `allauth.EmailAddress`.

While in the admin, also clear:
- Any `AdminApplication` rows from test cooptation runs
- Any `Memory` rows in the gallery (test photos)
- Any `AuditLog` entries from test runs (optional; `members → audit log → bulk delete with the action filter`)

### 0.4 — Bucket cleanup (optional)

The Tigris bucket has 2 photos backed up from the test members. They're orphans now (nothing in the DB references them). Path-dedup means the cron won't re-create them; they're ~138 KB total. Leave them or delete via Cloudinary dashboard + `aws s3 rm "s3://media-backup-fissla9lsuj0/<public_id>"`.

---

## Step 1 — Pre-launch checklist

Run through these one by one. None are blocking individually, but all should be ✓ before announcing.

```bash
railway run --service lesretrouvailles python manage.py audit_launch_readiness
```

This prints platform-side counts. After Step 0 they'll all be 0 except active members (= 1, the new super admin). That's expected — the seed-content audit makes sense to re-run after Step 4.

Manual checks the audit can't do:

- [ ] **`BASIC_AUTH_REQUIRED=false`** on `lesretrouvailles` Railway service. Already done; verify with `railway variables --service lesretrouvailles --json | grep BASIC_AUTH_REQUIRED`.
- [ ] **DMARC** — follow [`dmarc.md`](dmarc.md) §1.1-§1.3 if you haven't yet. `dig TXT _dmarc.villageretrouvailles.com` should show `p=quarantine` (or stricter) + `rua=`.
- [ ] **`backup_media` last run** — Railway dashboard → `media-backup-cron` → Deploys; confirm a successful run within the last 8 days.
- [ ] **Restore drill** — first 90-day drill if not done yet, per [`restore.md`](restore.md) §4.

---

## Step 2 — Roster collection

Collect the data needed for the CSV import from the WhatsApp group. Two approaches:

**Google Form** (recommended for ~200 members):
- Fields: prénom, nom, surnom (optionnel), numéro WhatsApp, email (optionnel), années au CEG1 (1980-1985, sélection multiple), classes fréquentées (6e, 6eA, 5e, 5eA, 4e, 4eA, 3e, 3eA…), ville actuelle, pays, profession (optionnel)
- Share the form link in the WhatsApp group with a 1-week deadline
- Members without internet access for forms can DM you their info; you fill in the form on their behalf

**WhatsApp poll + DM follow-up**:
- Less efficient but works for non-form-savvy members
- Post a poll asking who wants to join; DM each yes-vote for their info

Either way: dedupe + sanity-check the responses manually before turning them into a CSV.

---

## Step 3 — CSV preparation

1. Copy [`roster_template.csv`](roster_template.csv) to `roster.csv` (next to wherever you'll run the import command).
2. Fill in one row per member following the column reference in [`onboarding.md`](onboarding.md).
3. Optionally collect WhatsApp profile photos into a `roster_photos/` folder (see onboarding.md "Photo prep").

---

## Step 4 — Pilot batch (5-10 members)

Pick 5-10 trusted members (e.g., the WhatsApp group's most active or your closest co-founders). Make a `pilot.csv` with just those rows:

```bash
python manage.py import_whatsapp_roster pilot.csv \
    --photos-dir roster_photos \
    --magic-links-out pilot_magic_links.csv \
    --dry-run    # verify first
```

If the dry-run looks clean, re-run without `--dry-run`. DM each pilot using the templates in [`onboarding.md`](onboarding.md).

**Wait 48 hours.** Ask each pilot:
- Did the link work on first tap?
- Could they set a password without confusion?
- Does the directory show their entry correctly?
- Anything broken or surprising?

Fix anything urgent before Step 5.

---

## Step 5 — Full batch

Once pilots have signed off:

```bash
python manage.py import_whatsapp_roster roster.csv \
    --photos-dir roster_photos \
    --magic-links-out magic_links.csv
```

Open `magic_links.csv` in Excel. For each row, DM the member their personal magic-link URL using Template 2 from `onboarding.md`.

This step takes time (a few hours of WhatsApp DMs spread over a day or two). Pace yourself; don't burn out trying to send all 160-170 messages in one sitting.

---

## Step 6 — Re-run the readiness audit

Now that the roster is imported, the seed-content audit becomes meaningful:

```bash
railway run --service lesretrouvailles python manage.py audit_launch_readiness
```

Address any flagged items:
- **Active members < ~target** — verify the import counts; some rows may have errored.
- **Memory rows < 10** — admin uploads 10-20 historical photos via `/admin/memoires/memory/`. These are the seed photos for Mur des souvenirs.
- **InMemoriamEntry < 1** — admin creates 1-3 fiches via `/admin/memoriam/inmemoriamentry/` (with family consent following Annexe D §D.5).
- **PublicSearchEntry < 3** — admin enters 3+ "ghost" entries via `/admin/members/publicsearchentry/` (the public landing's "Nous recherchons aussi…" list).

Re-run the audit until all checks pass.

---

## Step 7 — WhatsApp announcement

When pilot feedback is positive AND seed content is in place, post the announcement to the WhatsApp group:

> 🎉 **Les Retrouvailles, c'est en ligne !**
>
> Chers anciens du CEG1 Birni 1980-1985, voici l'occasion qu'on attendait depuis longtemps : une plateforme privée juste pour nous, pour nous retrouver, partager des souvenirs, et honorer ceux qui nous ont quittés.
>
> 👉 **https://villageretrouvailles.com/**
>
> Vous avez tous reçu (en privé) soit un email soit un lien WhatsApp pour activer votre compte. Si ce n'est pas le cas, écrivez-moi ici et je vous l'envoie.
>
> Une fois connectés, complétez votre profil — c'est ça qui rend l'annuaire utile pour tous.
>
> 🌅 Bonne navigation et longues retrouvailles !

---

## Step 8 — First-week monitoring

Daily for the first 7 days, then every 2-3 days for the next 2 weeks:

- **Member count growth** — `Member.objects.filter(status="active").count()` should rise as people activate.
- **Error rate in Railway logs** — `railway logs --service lesretrouvailles | grep -iE "error|traceback"` — investigate spikes.
- **Resend dashboard** — check bounce rate; >5% means deliverability needs attention.
- **Member-reported issues** — handle them as they come in via WhatsApp DM.
- **Login failures** — if many members can't log in, the magic-link UX may need help text.

---

## Step 9 — Steady state (post-launch operating mode)

Quarterly calendar reminders, all read in the relevant runbook:

- **DMARC review** — [`dmarc.md`](dmarc.md) §2 (every 90 days)
- **Bucket size check** — `railway bucket info --bucket media-backup --json` (every 90 days)
- **Restore drill** — [`restore.md`](restore.md) §4 (every 90 days; first one 7 days after the first successful backup)

Steady-state operations:

- **New password requests** from email-less members → `python manage.py reissue_login_link <whatsapp-digits>`, share the URL via WhatsApp DM.
- **RGPD deletion requests** from members → [`rgpd-purge.md`](rgpd-purge.md). Member emails or DMs you "please delete my account"; you run the admin action or the CLI.
- **New cooptation candidates** from outside the original WhatsApp group → standard P3 cooptation flow via `/inscription/`.

---

## Rollback playbook

If something goes wrong post-launch:

### Symptom: emails are bouncing en masse

1. Stop sending. `railway variables --remove EMAIL_BACKEND --service lesretrouvailles` (temporary; falls back to console backend, no real send).
2. Investigate via DMARC reports + Resend dashboard.
3. Fix the underlying issue (wrong DKIM, etc.).
4. Re-enable; resume.

### Symptom: members can't log in (login form rejects credentials)

1. Verify the auth-method settings on prod: `railway variables --service lesretrouvailles --json | grep -i ACCOUNT_LOGIN`.
2. Check the deploy log for tracebacks during the latest deployment.
3. If it's bad enough, revert to the previous deployment via Railway dashboard → Deployments → previous successful one → "Redeploy".

### Symptom: an undesired account got created (typo, wrong email, etc.)

1. Run `python manage.py rgpd_purge_member <email>` per [`rgpd-purge.md`](rgpd-purge.md). Hard-deletes them cleanly + audit-logs.

### Symptom: full data loss

1. Restore Postgres from Railway snapshot (last 7 days available); see [`restore.md`](restore.md) §6.
2. Re-run `import_whatsapp_roster` if the imported roster was lost; the command is idempotent so it'll skip already-existing usernames.
3. The Tigris bucket has the media; restore individual photos per [`restore.md`](restore.md) §3.
