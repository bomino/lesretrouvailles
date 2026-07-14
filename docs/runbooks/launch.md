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
railway ssh --service lesretrouvailles -- python manage.py shell -c \
  "from members.models import Member; \
   [print(m.id, m.full_name, m.user.email) for m in Member.objects.all()]"
```

> `railway ssh`, not `railway run`: anything that touches the DB must execute
> *inside* Railway's network, because `DATABASE_URL` points at
> `postgres.railway.internal` which does not resolve from your machine.

Confirm these are test rows (`First1 Last1` / `Niamey` / `Médecin`-type values), not real founders.

### 0.2 — Create the new super admin first

Before any deletion, ensure production never has a state without an admin:

```bash
railway ssh --service lesretrouvailles -- python manage.py createsuperuser
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
railway ssh --service lesretrouvailles -- python manage.py audit_launch_readiness
```

This prints platform-side counts. After Step 0 they'll **all be 0** — including active members: `createsuperuser` creates a `User`, not a `Member` row, and the audit counts `Member` rows. That's expected; the seed-content audit only becomes meaningful after Step 4.

Manual checks the audit can't do:

- [ ] **`WHATSAPP_GROUP_URL`** set on `lesretrouvailles` to the real group invite
  (`https://chat.whatsapp.com/<code>`). While it is empty, every « Groupe WhatsApp »
  link on the site is **hidden** — which is deliberate (it used to render a dead
  placeholder link), but it means the group is unreachable from the platform until
  you set it:
  `railway variables --set WHATSAPP_GROUP_URL=https://chat.whatsapp.com/xxxx --service lesretrouvailles`
- [ ] **`BASIC_AUTH_REQUIRED=false`** on `lesretrouvailles` Railway service. Already done; verify with `railway variables --service lesretrouvailles --json | grep BASIC_AUTH_REQUIRED`.
- [ ] **DMARC** — follow [`dmarc.md`](dmarc.md) §1.1-§1.3 if you haven't yet. `dig TXT _dmarc.villageretrouvailles.com` should show `p=quarantine` (or stricter) + `rua=`.
- [ ] **`backup_media` last run** — Railway dashboard → `media-backup-cron` → Deploys; confirm a successful run within the last 8 days.
- [ ] **Restore drill** — first 90-day drill if not done yet, per [`restore.md`](restore.md) §4.
- [ ] **Promotions archive loaded** — the class-roster archive at `/promotions/` should already hold **352 entries across 11 classes** (6ème 1980-81 A-F, 6ème 1981-82 A-E). It was imported once and is **not** part of the per-launch flow; this is a verification, not a step to run.

  Log in as an admin and open **`/promotions/`** — it lists the 11 classes with a headcount each; they should total 352.

  > ⚠️ Don't try to check this with `railway ssh ... python manage.py shell -c "..."`. `railway ssh` strips quote characters before the remote shell sees them, so any command containing quotes or parentheses fails with a confusing bash syntax error. Pipes and redirects survive, so the working pattern for a real prod query is to base64 a script in and decode it on the other side:

  ```bash
  B64=$(base64 -w0 probe.py)
  railway ssh --service lesretrouvailles -- \
    "cd /app && echo $B64 | base64 -d > _probe.py && python _probe.py; rm -f _probe.py"
  ```

  (The script needs `import django; django.setup()` at the top, and must be written into `/app` — `python /tmp/x.py` puts `/tmp` on `sys.path`, not the app, so `import alumni` fails.)

  If you ever need to re-import: the command is `import_class_roster <csv_path>` (`--dry-run` supported), and it takes the CSV as a **required positional argument**. That CSV lives in gitignored `private-data/` and is deliberately **not** baked into the Docker image — the repo is public and these are 335 real living people. So the import does not run inside the container: run it **locally against the prod DB** via `DATABASE_PUBLIC_URL` (the internal DB host does not resolve outside Railway). The import is idempotent on `source_ref`, so re-running updates in place rather than duplicating.
- [ ] **Understand what members will and won't see of each other.** Since `47a19aa`, `show_email` and `show_whatsapp` default to **False** — contact details are opt-IN, which is what the member guide always promised. So right after the bulk import, the directory shows names, city, promotion and photo, but **no phone numbers or emails** until each member ticks the boxes on their own profile. This is correct and deliberate; don't "fix" it by flipping the defaults. If you want members to share contacts, say so in the WhatsApp announcement (Step 7) and point them at « Paramètres de confidentialité » in the guide.

---

## Step 2 — Roster collection

Collect the data from the WhatsApp group. **Full procedure in a dedicated runbook:** [`roster-collection.md`](roster-collection.md).

In short:

- Recommended cadence: **2-week window** with a Day 7 reminder + Day 12 DM nudge to non-responders.
- Recommended channel: a **Google Form** (template + exact French questions in `roster-collection.md` §2.1) shared via the WhatsApp group (announcement template in §2.2).
- Members without Google accounts or who hit any friction: have them **DM you the info** instead — you transcribe it manually.
- At the end of the 2-week window, close the form and export the responses to CSV. Move to Step 3.

For the current launch (May 2026): announcement posted ~2026-05-07; deadline 2026-05-21.

---

## Step 3 — CSV preparation

1. Copy [`roster_template.csv`](roster_template.csv) to `roster.csv` (next to wherever you'll run the import command).
2. Fill in one row per member following the column reference in [`onboarding.md`](onboarding.md).
3. Optionally collect WhatsApp profile photos into a `roster_photos/` folder (see onboarding.md "Photo prep").

---

## Step 4 — Pilot batch (5-10 members)

Pick 5-10 trusted members (e.g., the WhatsApp group's most active or your closest co-founders). Make a `pilot.csv` with just those rows:

> **Targeting production.** The import reads a CSV and photo directory that
> live on *your* machine, so it must run locally — but against the production
> database. `railway run` injects prod env vars but keeps the internal
> `postgres.railway.internal` host, which does not resolve outside Railway's
> network. Export the **public** proxy URL instead (Railway dashboard →
> Postgres → Variables → `DATABASE_PUBLIC_URL`):
>
> ```bash
> export DJANGO_SETTINGS_MODULE=alumni.settings.prod
> export DATABASE_URL="$(railway variables --service Postgres --json | jq -r .DATABASE_PUBLIC_URL)"
> export SITE_URL=https://villageretrouvailles.com
> # plus the Resend + Cloudinary vars the import needs:
> export RESEND_API_KEY=... CLOUDINARY_URL=... SECRET_KEY=...
> ```
>
> Without `SITE_URL`, every magic link in the output CSV is built from the
> `http://localhost:8000` default and every DM'd link is dead. Verify with a
> one-row CSV before the full run.

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

Same environment as Step 4 (see the targeting note there — `DJANGO_SETTINGS_MODULE`,
`DATABASE_URL` from `DATABASE_PUBLIC_URL`, and `SITE_URL` must all be exported,
or you will DM ~170 dead `localhost` links).

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
railway ssh --service lesretrouvailles -- python manage.py audit_launch_readiness
```

Address any flagged items:
- **Active members < ~target** — verify the import counts; some rows may have errored.
- **Memory rows < 10** — admin uploads 10-20 historical photos via `/admin/memoires/memory/`. These are the seed photos for Mur des souvenirs.
- **InMemoriamEntry < 1** — admin creates 1-3 fiches via `/admin/memoriam/inmemoriamentry/` (with family consent following Annexe D §D.5).
- **PublicSearchEntry < 3** — admin enters 3+ "ghost" entries via `/admin/members/publicsearchentry/` (the public landing's "Nous recherchons aussi…" list).
- [ ] **`PUBLIC_GHOST_LIST_ENABLED=true`** on the `lesretrouvailles` service. The flag defaults to **false**, so the anonymous landing renders no ghost list at all until you flip it — the entries above stay invisible and the audit still passes. Set it once the entries and the removal flow are in place:
  `railway variables --set PUBLIC_GHOST_LIST_ENABLED=true --service lesretrouvailles`

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

1. Stop sending. `railway variables --set EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend --service lesretrouvailles` (temporary; nothing leaves the container). Setting the var is what works — staging/prod default to `ResendBackend`, so *removing* the variable leaves real sending on.
2. Investigate via DMARC reports + Resend dashboard.
3. Fix the underlying issue (wrong DKIM, etc.).
4. Re-enable; resume.

### Symptom: members can't log in (login form rejects credentials)

1. Print the auth settings the running container actually loaded (they are hardcoded in `alumni/settings/base.py`, never read from env — grepping Railway variables for `ACCOUNT_LOGIN` always returns nothing):
   `railway ssh --service lesretrouvailles -- python manage.py shell -c "from django.conf import settings; print(settings.ACCOUNT_LOGIN_METHODS, settings.SETTINGS_MODULE)"`
2. Check the deploy log for tracebacks during the latest deployment.
3. If it's bad enough, revert to the previous deployment via Railway dashboard → Deployments → previous successful one → "Redeploy".

### Symptom: an undesired account got created (typo, wrong email, etc.)

1. Run `railway ssh --service lesretrouvailles -- python manage.py rgpd_purge_member <email-or-username>` per [`rgpd-purge.md`](rgpd-purge.md). Hard-deletes them cleanly + audit-logs. For the ~80% of members with no email, pass their **username** (the WhatsApp digits) — the command accepts either.

### Symptom: full data loss

1. Restore Postgres from Railway snapshot (last 7 days available); see [`restore.md`](restore.md) §6.
2. Re-run `import_whatsapp_roster` if the imported roster was lost; the command is idempotent so it'll skip already-existing usernames.
3. The Tigris bucket has the media; restore individual photos per [`restore.md`](restore.md) §3.
