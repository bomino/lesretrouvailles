# Onboarding runbook — bulk import + WhatsApp messaging

> Companion to `launch.md`. Operator reference for preparing the roster CSV, running the bulk import, and DM-ing members on WhatsApp.

## CSV columns reference

Template: [`roster_template.csv`](roster_template.csv) (3 sample rows). Copy and replace.

| Column | Required | Format / notes |
|---|---|---|
| `first_name` | ✓ | Prénom. Used for email salutation + on-platform display. |
| `last_name` | ✓ | Nom de famille. |
| `nickname` | optional | Surnom du quartier; shown in the directory next to the name. |
| `whatsapp` | ✓ | E.164 format, with `+` (e.g. `+22790000001`). Digits-only becomes `User.username`. |
| `email` | optional | If present, member receives password-set email via Resend. Empty for ~80% of the roster. |
| `years_attended` | ✓ | Comma-separated, in quotes. Each year between 1980 and 1985. Skipping is fine (`"1980,1982"`). |
| `classes` | ✓ | Comma-separated, in quotes. Format: `6e`, `5e`, `4e`, `3e`, optionally with a section letter (`6eA`, `4eb`). |
| `city` | ✓ | Ville actuelle. |
| `country` | optional (defaults `Niger`) | Pays actuel. |
| `profession` | optional | Métier. Free-form. |
| `photo_filename` | optional | Filename inside `roster_photos/` folder. Empty = no photo at import (member uploads later). |

### Common validation gotchas

- **`6ème` and `6eme`** — both fail the pattern. Use `6e`. Same for `5e`, `4e`, `3e`.
- **`2nde` / `1ere` / `Tle`** — high-school grades. CEG1 Birni only covers college (6e through 3e). Reject these.
- **Year `1986`** — outside the 1980-1985 cohort. If the member attended a different alumni cohort, they don't belong here.
- **Phone with parentheses or dashes** — use plain `+227...`. The validator strips non-digits internally but the column should be clean for human review.
- **Non-Niger phone** — fine. WhatsApp numbers from anywhere work.

## Photo prep

For members whose photo you want to seed at import time:

1. Open WhatsApp → tap their profile → tap the photo → "Save image" (or screenshot if WhatsApp blocks save).
2. Crop to roughly square. Cloudinary auto-faces-crops on render, so anything reasonable works.
3. Save to `roster_photos/<exact-filename-from-csv>.jpg` (or .png/.webp).
4. Reference that filename in the CSV's `photo_filename` column.

Members without a pre-loaded photo: leave `photo_filename` blank. They'll see a monogram avatar on the platform until they upload their own via `Profile → Modifier → Choisir une photo`.

## Running the import

### Step 1 — Dry run (mandatory)

```bash
python manage.py import_whatsapp_roster roster.csv \
    --photos-dir roster_photos \
    --magic-links-out magic_links.csv \
    --dry-run
```

Reads the CSV, validates everything, prints a plan. Makes no DB changes; sends no emails. Fix any errors in the CSV (typos, bad years, missing fields), then re-run.

### Step 2 — Pilot batch (5-10 members)

Make a small CSV (`pilot.csv`) with a handful of trusted members from the WhatsApp group. Run for real:

```bash
python manage.py import_whatsapp_roster pilot.csv \
    --photos-dir roster_photos \
    --magic-links-out pilot_magic_links.csv
```

This:
- Creates `User` + `Member` rows for each pilot.
- For pilots with email: sends the welcome email via Resend.
- For pilots without email: writes their magic-link URL to `pilot_magic_links.csv`.

DM each pilot the appropriate message (templates below). Wait 48 hours, ask each for feedback. Fix anything urgent.

### Step 3 — Full batch

After pilots sign off:

```bash
python manage.py import_whatsapp_roster roster.csv \
    --photos-dir roster_photos \
    --magic-links-out magic_links.csv
```

Resend's free tier is 100 emails/day. With ~30-40 emails (15-20% of 200) the burst is well within the cap. If the cohort grows past 100 emails, use `--no-emails` and send in batches.

After the run completes, open `magic_links.csv` in Excel — it has one row per email-less member with their phone, full name, and URL. Use this as your DM checklist.

## WhatsApp DM templates (copy-paste)

### Template 1 — for members WITH email (informational)

> Salut {{ first_name }},
> Bienvenue sur **Les Retrouvailles**, notre nouvelle plateforme privée pour le CEG1 Birni 1980-1985 ! Tu vas recevoir un email d'activation à {{ email }} pour choisir ton mot de passe. Ce lien est valable 7 jours.
>
> Une fois connecté·e, tu pourras compléter ton profil et retrouver tes camarades.
>
> Si tu ne vois rien dans ta boîte (pense à vérifier le dossier spam) ou si tu rencontres un souci, écris-moi ici.
>
> 🌅 Plateforme : https://villageretrouvailles.com/

### Template 2 — for members WITHOUT email (with magic link)

> Salut {{ first_name }},
> Bienvenue sur **Les Retrouvailles**, notre nouvelle plateforme privée pour le CEG1 Birni 1980-1985 !
>
> Voici ton lien personnel pour activer ton compte (valable 7 jours) :
>
> {{ magic_link_url }}
>
> Tape ou clique sur le lien depuis ton téléphone, choisis un mot de passe que tu retiendras, et tu seras connecté·e. Pour les prochaines connexions, tape ton numéro WhatsApp ({{ whatsapp_with_plus }}) et le mot de passe que tu auras choisi.
>
> Si tu rencontres un souci ou si tu oublies ton mot de passe, écris-moi ici et je te renvoie un nouveau lien.
>
> 🌅 Plateforme : https://villageretrouvailles.com/

### Template 3 — password reset for an email-less member

> Salut {{ first_name }},
> Voici ton nouveau lien de connexion (valable 7 jours) :
>
> {{ new_magic_link_url }}
>
> Choisis ton nouveau mot de passe en suivant le lien.

To generate the new link: `python manage.py reissue_login_link <whatsapp-digits>` (e.g. `reissue_login_link 22790000001`). Copy the printed URL into the message.

## Edge cases

- **Member with email but the email bounces.** The Resend dashboard will show the bounce. Treat them as email-less: re-run `reissue_login_link` for their username and DM them the link.
- **Member whose phone changed since you collected the roster.** Update their `User.username` via Django admin → Auth → Users. They'll log in with the new number afterwards.
- **Two CSV rows with the same phone.** The second one is skipped (idempotent). Check whether one was a typo and re-run after fixing.
- **You imported a member you shouldn't have.** Use `python manage.py rgpd_purge_member <email>` (P6b). Cleanly removes the member, their cascading rows, and their photos from Cloudinary + the bucket. Audit-logged.
