# Roster collection runbook (Step 2 of soft launch)

> Companion to [`launch.md`](launch.md). Operator reference for **collecting** the roster info from the WhatsApp group **before** preparing the CSV and running `import_whatsapp_roster`.
>
> **Current launch (May 2026):** form posted ~2026-05-07; deadline 2026-05-21 (2-week window).

This step is intentionally low-tech: a Google Form + a WhatsApp announcement + DM follow-ups. No automation, no integrations. The signal you're capturing here lives outside the platform; you transcribe it into `roster.csv` afterwards.

---

## Recommended cadence

- **Duration: 2 weeks.** Long enough that members on patchy connections / weekend-only-checkers see the message, short enough to keep momentum. Don't go past 3 weeks — interest fades.
- **Cadence within the 2 weeks:**
  - Day 0 — group announcement
  - Day 7 — light reminder in the group ("À ceux qui n'ont pas encore rempli le formulaire…")
  - Day 12 — DM nudge to non-responders
  - Day 14 — close the form, prepare CSV, move to Step 3 of `launch.md`

---

## Step 2.1 — Build the Google Form

Create a new Google Form titled:

> **Inscription Les Retrouvailles — anciens du CEG 1 Birni (1980-1985)**

### Form intro / description

> Bonjour,
>
> Nous lançons une plateforme privée pour reconnecter les anciens du CEG 1 Birni de Zinder, promotions 1980 à 1985. Merci de remplir ce court formulaire (5 minutes max) — tes informations ne seront accessibles qu'aux camarades validés sur la plateforme.
>
> Tu recevras ensuite un lien d'activation par WhatsApp (ou par email si tu en renseignes un).
>
> Pour toute question, écris-moi ici : **[ton numéro WhatsApp d'admin]**.

### Questions

| # | Question | Type | Required | Help text / options |
|---|---|---|---|---|
| 1 | **Prénom** | Réponse courte | ✓ | — |
| 2 | **Nom de famille** | Réponse courte | ✓ | — |
| 3 | **Surnom (optionnel)** | Réponse courte | ✗ | « Le surnom du quartier ou de l'école, si tu en avais un. » |
| 4 | **Numéro WhatsApp** | Réponse courte | ✓ | « Avec l'indicatif pays, ex: +227 90 00 00 00 » |
| 5 | **Email (optionnel)** | Réponse courte | ✗ | « Si tu en as un que tu consultes. Sinon laisse vide — tu recevras un lien par WhatsApp. » |
| 6 | **Années au CEG 1 Birni** | Cases à cocher | ✓ | Options: `1980` · `1981` · `1982` · `1983` · `1984` · `1985` (multi-select) |
| 7 | **Classes fréquentées (optionnel)** | Réponse longue | ✗ | « Indique tes classes par année si tu t'en souviens. Ex: 6eA en 1980, 5eA en 1981, 4eB en 1982, 3eC en 1983. Tu peux laisser vide — c'est facultatif. » |
| 8 | **Ville actuelle** | Réponse courte | ✓ | « Où vis-tu aujourd'hui ? » |
| 9 | **Pays** | Réponse courte | ✗ | « Niger par défaut. » |
| 10 | **Profession** | Réponse courte | ✗ | « En quelques mots. » |
| 11 | **Consentement** | Case à cocher | ✓ | « J'accepte que ces informations servent à créer mon profil sur la plateforme privée Les Retrouvailles, et à recevoir un lien d'activation par WhatsApp ou email. » |

### Form settings

- ⚙ **Settings → Réponses** → **Collecter les adresses email** = optional. Enable only if you want to track which Google account submitted; this adds login friction for members without a Google account.
- ⚙ **Settings → Réponses** → **Limiter à 1 réponse** = **disabled**. Members might want to fix typos by submitting again.
- ⚙ **Settings → Présentation** → **Message de confirmation** :
  > *Merci ! Tu recevras ton lien d'activation dans les prochains jours via WhatsApp ou email. À bientôt sur Les Retrouvailles.*

---

## Step 2.2 — WhatsApp group announcement (Day 0)

Post in the WhatsApp group with the form URL inserted at `[LIEN GOOGLE FORM]` and the deadline at `[DEADLINE]`.

> 🌅 *Les Retrouvailles* — la plateforme privée des anciens du CEG 1 Birni est prête !
>
> Quarante ans plus tard, on a enfin un espace privé pour nous : un annuaire des anciens, un Mur des souvenirs, un In Memoriam pour ceux qui nous ont quittés en chemin.
>
> 👉 *Ce qu'il faut faire* (5 minutes) :
>
> Remplis ce formulaire pour qu'on crée ton compte :
> **[LIEN GOOGLE FORM]**
>
> 📌 Quoi indiquer :
> • Ton prénom et nom
> • Ton numéro WhatsApp (le même que celui de ce groupe)
> • Tes années au CEG (1980-1985)
> • Ta ville
> • Tes classes et ta profession (optionnel)
>
> 📅 *Avant le [DEADLINE]*
>
> Une fois ta réponse reçue, je crée ton compte et t'envoie un lien personnel pour choisir ton mot de passe — par WhatsApp ou par email selon ce que tu auras indiqué.
>
> 🌍 La plateforme : https://villageretrouvailles.com/
>
> Pour toute question, écris-moi en privé. À très bientôt sur Les Retrouvailles !

**For the current launch:** `[DEADLINE]` = **dimanche 2026-05-21** (formuler comme « avant dimanche 21 mai »).

---

## Step 2.3 — Light reminder in the group (Day 7)

Short follow-up in the same group, much shorter than the announcement:

> 🌅 Petit rappel : pour ceux qui n'ont pas encore rempli le formulaire d'inscription à Les Retrouvailles, c'est par ici 👇
>
> **[LIEN GOOGLE FORM]**
>
> Date limite : **[DEADLINE]**. Ça prend 5 minutes. Tu peux aussi me répondre directement par WhatsApp si tu préfères — je m'occupe du reste.

---

## Step 2.4 — DM follow-up to non-responders (Day 12)

Two days before the deadline, identify who responded vs who didn't (compare the form responses to your WhatsApp group member list — manual eyeballing for ~200 contacts is feasible). DM each non-responder personally:

> Salut **{Prénom}**,
>
> J'avais posté il y a quelques jours un message dans le groupe pour s'inscrire sur Les Retrouvailles, la plateforme privée du CEG 1 Birni. Tu n'as pas encore répondu — pas grave, je te renvoie le lien :
>
> **[LIEN GOOGLE FORM]**
>
> Ça prend 5 minutes. Si tu n'arrives pas à remplir le formulaire (réseau, pas de Google, etc.), réponds-moi simplement ici avec :
> - Ton prénom et nom
> - Tes années au CEG (1980-1985)
> - Ta ville actuelle
> - (Optionnel) tes classes si tu t'en souviens (ex: 6eA, 5eB, 4eA, 3eA)
>
> Je m'occupe du reste. Date limite : **[DEADLINE]**. À bientôt !

---

## Step 2.5 — Edge cases

These come up in any community of ~200 — be prepared.

### Member doesn't have a Google account

The form works without one if you've left "Collecter les adresses email" off in form settings. If they hit a Google-login wall: ask them to reply via WhatsApp DM with the data, you fill the form on their behalf (or skip the form and just transcribe directly into your CSV).

### Member doesn't have a smartphone / can't open links

Same fallback: collect via WhatsApp text DM, transcribe yourself.

### Member's phone number changed since the group was added

Ask in the form itself, or via DM. Their **current** WhatsApp number is what becomes their `username` on the platform — the one where they'll receive the magic link.

### Member submits twice (typo correction)

Both responses come into the same Google Sheet. Keep the most recent submission per phone number when transcribing to CSV. If two submissions disagree on a key field (years, classes, etc.), DM the member to clarify.

### Member doesn't remember their classes / sections

Encourage best-effort: « Mets ce dont tu te souviens, on pourra corriger après ». Bare level (`6e`, `5e`, `4e`, `3e`) is fine. Section letters are nice-to-have.

### Member is hesitant about privacy

Reassure: only validated alumni see the directory; basic public landing has minimal info; full RGPD deletion available on demand. Point at `docs/guides/guide_membre.md` §9 if they want to read the policy.

### Family is asking about a deceased camarade for In Memoriam

Note who they're asking about in your own list. After launch, follow the In Memoriam admin procedure (Annexe D — family consent before publication). See `docs/guides/guide_admin.md` §7.

---

## Step 2.6 — Closing the form

Once the deadline hits:

1. **In Google Forms** : ⚙ Settings → toggle "Accepter les réponses" off. The form now shows the closure message you set:
   > *Merci ! Le formulaire est fermé. Pour toute question, écris-moi sur WhatsApp.*
2. **Export the responses** : Forms → Réponses → menu → "Télécharger en CSV". This is the **raw** export — needs cleanup before becoming `roster.csv`.
3. **Move on to Step 3** of `launch.md` — CSV preparation.

> 💡 **Don't delete the Google Form afterwards.** Keep it accessible (re-open if needed for a Phase 2 wave of late joiners). The Form acts as a permanent record of who consented to be onboarded — keep it as long as the platform runs.

---

## What you'll have at the end of Step 2

- One Google Sheet with N rows (your members), each row = one form submission
- A list of non-responders you DM'd or transcribed manually
- Roughly N entries that map cleanly into `docs/runbooks/roster_template.csv` columns

You're ready for Step 3 (CSV preparation) and Step 4 (pilot import) in `launch.md`.
