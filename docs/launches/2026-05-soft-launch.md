# Soft launch — May 2026 — playbook

> **One-time, dated playbook for the May 2026 soft launch of Les Retrouvailles.** Specific dates, ready-to-paste messages, and a tracking grid for the 2-week window. Companion to (not replacement for) the reusable runbook [`docs/runbooks/roster-collection.md`](../runbooks/roster-collection.md), which holds the generic procedure and rationale.
>
> Keep this doc as a historical record after launch; future onboarding waves get their own dated playbook.

---

## Calendar — the 2-week window

| Day | Date | Action |
|---|---|---|
| **0** | 2026-05-07 (jeudi) | Post the group announcement (template in §1 below) |
| **7** | 2026-05-14 (jeudi) | Light reminder in the group (template in §2) |
| **12** | 2026-05-19 (mardi) | DM each non-responder personally (template in §3) |
| **14** | 2026-05-21 (jeudi) | Close the form, export to CSV, move to Step 3 of `launch.md` |

The deadline communicated to members in the announcement is **dimanche 2026-05-21**, giving weekend stragglers a window between the Day-12 DM and form closure.

---

## Step 1 — Google Form

Build the form once, on Day 0 (or the day before). Detailed schema and question text in [`roster-collection.md`](../runbooks/roster-collection.md) §2.1.

Quick checklist:

- [ ] Title: **Inscription Les Retrouvailles — anciens du CEG 1 Birni (1980-1985)**
- [ ] Description: see `roster-collection.md` §2.1
- [ ] 11 questions (Prénom · Nom · Surnom · WhatsApp · Email · Années 1980-1985 · Classes · Ville · Pays · Profession · Consentement)
- [ ] Confirmation message: *« Merci ! Tu recevras ton lien d'activation dans les prochains jours via WhatsApp ou email. À bientôt sur Les Retrouvailles. »*
- [ ] **Settings → Réponses → Limiter à 1 réponse: désactivé** (allow typo corrections)
- [ ] Publish, copy the share URL — you'll paste it into the announcement at `[LIEN_FORM]` below

Form URL once published: `___________________________________________________`
*(fill in here for your own reference)*

---

## §1 — Day 0 group announcement (post 2026-05-07)

Copy-paste into the WhatsApp group, replacing only `[LIEN_FORM]` with the form's URL.

```
🌅 *Les Retrouvailles* — la plateforme privée des anciens du CEG 1 Birni est prête !

Quarante ans plus tard, on a enfin un espace privé pour nous : un annuaire des anciens, un Mur des souvenirs, un In Memoriam pour ceux qui nous ont quittés en chemin.

👉 *Ce qu'il faut faire* (5 minutes) :

Remplis ce formulaire pour qu'on crée ton compte :
[LIEN_FORM]

📌 Quoi indiquer :
• Ton prénom et nom
• Ton numéro WhatsApp (le même que celui de ce groupe)
• Tes années au CEG (1980-1985) et tes classes
• Ta ville et ta profession (optionnel)

📅 *Avant dimanche 21 mai*

Une fois ta réponse reçue, je crée ton compte et t'envoie un lien personnel pour choisir ton mot de passe — par WhatsApp ou par email selon ce que tu auras indiqué.

🌍 La plateforme : https://villageretrouvailles.com/

Pour toute question, écris-moi en privé. À très bientôt sur Les Retrouvailles !
```

---

## §2 — Day 7 reminder (post 2026-05-14)

Short follow-up in the same group.

```
🌅 Petit rappel : pour ceux qui n'ont pas encore rempli le formulaire d'inscription à Les Retrouvailles, c'est par ici 👇

[LIEN_FORM]

Date limite : *dimanche 21 mai*. Ça prend 5 minutes. Tu peux aussi me répondre directement par WhatsApp si tu préfères — je m'occupe du reste.
```

---

## §3 — Day 12 DM follow-up to non-responders (send 2026-05-19)

Two days before the deadline, identify who hasn't responded yet by comparing the form responses (Google Sheet) to your WhatsApp group member list. DM each non-responder personally, replacing `{Prénom}` with their actual first name:

```
Salut {Prénom},

J'avais posté il y a quelques jours un message dans le groupe pour s'inscrire sur Les Retrouvailles, la plateforme privée du CEG 1 Birni. Tu n'as pas encore répondu — pas grave, je te renvoie le lien :

[LIEN_FORM]

Ça prend 5 minutes. Si tu n'arrives pas à remplir le formulaire (réseau, pas de Google, etc.), réponds-moi simplement ici avec :
- Ton prénom et nom
- Tes années au CEG (1980-1985)
- Tes classes (ex: 6eA, 5eB, 4eA, 3eA)
- Ta ville actuelle

Je m'occupe du reste. Date limite : *dimanche 21 mai*. À bientôt !
```

---

## §4 — Day 14 close + handoff to Step 3 (do 2026-05-21)

When the window closes:

1. **In Google Forms**: ⚙ Settings → toggle **Accepter les réponses** off. Set the closure message:
   > *« Merci ! Le formulaire est fermé. Pour toute question, écris-moi sur WhatsApp. »*
2. **Export the responses**: Forms → Réponses → menu (⋮) → **Télécharger en CSV**. This is the **raw** export. Save it locally as `roster_raw.csv`.
3. **Move to `launch.md` Step 3** — CSV preparation. Transcribe the raw export into [`docs/runbooks/roster_template.csv`](../runbooks/roster_template.csv) format (column rename + format normalization). Walk-through in [`onboarding.md`](../runbooks/onboarding.md).
4. **Don't delete the Google Form** — keep it accessible for a Phase 2 wave of late joiners.

---

## Tracking grid — fill in as you go

Use this section to keep a running log during the 2 weeks. Update at end of each day; commit changes if you want a permanent record.

| Day | Date | Done? | Notes |
|---|---|---|---|
| 0 | 2026-05-07 | ⬜ | Form built and announcement posted at HH:MM. Form URL: ____ |
| 1 | 2026-05-08 | ⬜ | _N_ responses so far |
| 2 | 2026-05-09 | ⬜ | _N_ responses |
| 3 | 2026-05-10 | ⬜ | _N_ responses |
| 4 | 2026-05-11 | ⬜ | _N_ responses |
| 5 | 2026-05-12 | ⬜ | _N_ responses |
| 6 | 2026-05-13 | ⬜ | _N_ responses |
| 7 | 2026-05-14 | ⬜ | Reminder posted. Total responses: _N_ |
| 8 | 2026-05-15 | ⬜ | _N_ responses |
| 9 | 2026-05-16 | ⬜ | _N_ responses |
| 10 | 2026-05-17 | ⬜ | _N_ responses |
| 11 | 2026-05-18 | ⬜ | _N_ responses |
| 12 | 2026-05-19 | ⬜ | DMs sent to _N_ non-responders |
| 13 | 2026-05-20 | ⬜ | _N_ responses (final stragglers) |
| 14 | 2026-05-21 | ⬜ | Form closed. Final count: _N_ responses. CSV exported. Moving to Step 3. |

### Notable issues / edge cases encountered

(Use this space to log anything unexpected — members without smartphones, duplicate phone numbers, families asking about deceased camarades, etc. Helps refine the procedure for future waves.)

- _empty_

---

## Reference

- Reusable runbook: [`docs/runbooks/roster-collection.md`](../runbooks/roster-collection.md)
- Full launch procedure: [`docs/runbooks/launch.md`](../runbooks/launch.md)
- After Step 2 → Step 3 (CSV prep): [`docs/runbooks/onboarding.md`](../runbooks/onboarding.md)
- CSV template: [`docs/runbooks/roster_template.csv`](../runbooks/roster_template.csv)
- Bulk-import command: `python manage.py import_whatsapp_roster <csv> --photos-dir roster_photos --magic-links-out magic_links.csv [--dry-run]`
