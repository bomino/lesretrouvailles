# Styled Allauth Templates (Design Spec)

**Date:** 2026-05-04
**Status:** Approved (pending implementation)
**Predecessor:** P5a (Mur des souvenirs)

---

## Goal

Override every django-allauth template a real user can hit during normal flows so the entire `/accounts/*` experience matches the rest of the site visually. Today only `login.html`, `logout.html`, and `signup_closed.html` are overridden — the rest fall through to allauth's bundled templates (system serif, no Tailwind, no brand). The most painful path is the cooptation password-set flow at `/accounts/password/reset/key/<uidb36>-set-password/`, where new members hit an unstyled form on their very first visit.

This phase ships **14 new template overrides plus 2 shared partials** (16 new template files total), all styled to match the existing `templates/account/login.html` reference. Per-page hand-tuned headline + subtitle copy gives each surface a warm, intentional feel rather than a templated one.

## Non-goals (explicit YAGNI)

- **Phone-based authentication flows** — `phone_*.html`, `confirm_phone_verification_code.html`. We don't use phone auth.
- **Code-based authentication** — `confirm_login_code.html`, `request_login_code.html`, `confirm_*_code.html`. We don't use email-code auth (we use password auth + cooptation).
- **Passkey signup** — `signup_by_passkey.html`. We don't use passkeys.
- **The abstract `base_*.html`** — `base_entrance.html`, `base_manage.html`, etc. These are parents allauth's leaf templates extend; our leaf overrides bypass them entirely (each leaf extends our project's `base.html`).
- **Allauth `snippets/` directory** — internal helpers our hand-rolled markup doesn't invoke.
- **A11y rewrite of the existing 3 styled templates** — `login.html`, `logout.html`, `signup_closed.html` stay as-is in this phase. Polish later if needed.
- **Branded email templates** (under `account/email/`) — those are TXT files with subject + body for password-reset emails etc. Out of scope; phase to come.

---

## A. Visual approach

**B + C combined** (per brainstorming):

- **(B) Two shared partials** to DRY up the chrome:
  - `templates/account/_input.html` — single form field render: label + `<input>` (or matching widget) + per-field error span. Takes `field`, optional `type`, optional `autocomplete`, optional `extra_classes`.
  - `templates/account/_form_card.html` — the rounded surface card wrapper around `<form>` + non-field error block. Takes `action_url`, `submit_label`, optional `secondary_link_url`, `secondary_link_label`. The body (form fields) is rendered via `{% block fields %}{% endblock %}` so leaf templates fill it in.
- **(C) Hand-tuned headline + subtitle per page** — every page has its own warm pre-headline pill, h1, and subtitle. Examples:
  - `password_reset_from_key.html`: pill **"Bienvenue"**, h1 **"Choisissez votre mot de passe"**, subtitle **"Une dernière étape avant de rejoindre les retrouvailles."**
  - `password_change.html`: pill **"Espace membre"**, h1 **"Changer mon mot de passe"**, subtitle **"Pour la sécurité de votre compte."**
  - `email.html`: pill **"Espace membre"**, h1 **"Mes adresses email"**, subtitle **"Gérez l'adresse principale et les adresses associées à votre compte."**
- **Page width**: uniform `max-w-md` (matches the existing login.html). Single exception: `email.html` uses `max-w-2xl` because it's a list-with-actions surface, not a form-with-fields surface.
- **Typography**: heritage serif (`font-display`) on h1, system on body. Same as existing pages.
- **Buttons**: primary action uses the existing tertiary-bg button style from `login.html` (`bg-tertiary text-on-tertiary rounded-lg px-4 py-2.5`). Secondary/ghost uses `border-secondary/25 hover:border-tertiary/40`.
- **Errors**: non-field errors render as a styled alert block (red-50 bg, red-300 border, red-800 text) at the top of the form. Per-field errors render as a small red `<p>` directly under the field. Never `class="errorlist"`.
- **Password validator help**: small muted text under the password field (Django's `field.help_text`). Not a top-level bullet list.
- **Mobile-first**: all pages render correctly at 320px. Form inputs are full-width within the card.
- **Brand chrome inheritance**: every leaf template `{% extends "base.html" %}` so it gets the navbar, footer, fonts, htmx, etc.

### Per-page copy (load-bearing decisions baked in)

| Template | Pill | Headline | Subtitle |
|---|---|---|---|
| password_reset.html | "Espace membre" | "Mot de passe oublié ?" | "Entrez votre email — nous vous enverrons un lien pour réinitialiser votre mot de passe." |
| password_reset_done.html | "Espace membre" | "Email envoyé" | "Si l'adresse correspond à un compte, vous recevrez un lien sous quelques minutes. Vérifiez aussi vos spams." |
| password_reset_from_key.html | "Bienvenue" | "Choisissez votre mot de passe" | "Une dernière étape avant de rejoindre les retrouvailles." |
| password_reset_from_key_done.html | "Espace membre" | "Mot de passe enregistré" | "Vous pouvez maintenant vous connecter avec votre nouveau mot de passe." |
| password_change.html | "Espace membre" | "Changer mon mot de passe" | "Pour la sécurité de votre compte." |
| password_set.html | "Espace membre" | "Définir un mot de passe" | "Choisissez un mot de passe pour votre compte." |
| email.html | "Espace membre" | "Mes adresses email" | "Gérez l'adresse principale et les adresses associées à votre compte." |
| email_change.html | "Espace membre" | "Changer mon adresse email" | "Vous recevrez un lien de confirmation à la nouvelle adresse." |
| email_confirm.html | "Espace membre" | "Confirmer cette adresse email" | "Cliquez sur Confirmer pour valider l'adresse {{ confirmation.email_address.email }}." |
| verification_sent.html | "Espace membre" | "Email de vérification envoyé" | "Vérifiez votre boîte de réception et cliquez sur le lien pour activer votre compte." |
| account_inactive.html | "Espace membre" | "Compte inactif" | "Votre compte n'est plus actif. Contactez l'équipe si vous pensez qu'il s'agit d'une erreur." |
| verified_email_required.html | "Espace membre" | "Vérification requise" | "Veuillez confirmer votre adresse email avant de continuer." |
| reauthenticate.html | "Espace membre" | "Confirmation de sécurité" | "Veuillez saisir votre mot de passe pour confirmer cette opération." |
| signup.html | "Inscription" | "Bienvenue parmi les anciens" | "Cette plateforme est privée. Pour vous inscrire, demandez à deux camarades de vous coopter." (with link to /inscription/) |

### Special case: `password_reset_from_key.html` token failure branch

The bundled template has two branches based on a `token_fail` context variable. When the token is invalid/expired/already-used, it shows "Bad Token" + a CTA to request a new reset. Our override preserves both branches:

- **Token valid**: render the password-set form per the table above.
- **Token failed**: show pill **"Lien expiré"**, h1 **"Lien invalide ou déjà utilisé"**, subtitle **"Demandez un nouveau lien de réinitialisation."** + a styled button linking to `{% url 'account_reset_password' %}`.

---

## B. Tests

New file `core/tests/test_allauth_templates.py`. One test per overridden template (12 tests covering the new overrides, plus light coverage of the existing 3 to prevent regressions if anyone touches them).

For each template, the test:
1. Issues a GET (with appropriate fixture setup — authenticated member for logged-in pages, anonymous for entrance pages).
2. Asserts response status 200 (or 302 if the view redirects, e.g., `account_inactive` for an inactive user — handle per template).
3. Asserts the response body contains a brand marker proving `base.html` was extended (e.g., `"Les Retrouvailles"` from the footer, or `"img/logo.png"` from the header).
4. Asserts the response body does NOT contain `class="errorlist"` (Django's default error markup).

For templates that need rare state to GET cleanly, replace the GET-200 assertion with a **file-content test** — open `templates/account/<name>.html` from disk and assert: (a) the file exists, (b) the source contains `{% extends "base.html" %}`, (c) the source contains a partial-include (`{% include "account/_form_card.html"` or `{% include "account/_input.html"`) so we know it uses the shared chrome and not bare allauth output. This is a static check on the template source — adequate for templates we can't easily render in a test client.

Templates that need rare state:
- `email_confirm.html` — needs an EmailConfirmation object with a valid key. Build via fixture or skip GET test.
- `account_inactive.html` — needs an inactive user logged in. Fixture: create User with `is_active=False`, force_login.
- `reauthenticate.html` — needs sensitive operation redirect. Skip GET test; verify partial inclusion.
- `verified_email_required.html` — needs unverified email + EMAIL_VERIFICATION setting. Skip GET test; verify partial inclusion.

Estimated ~14 tests in `test_allauth_templates.py`. Plus a separate test that POSTs deliberately invalid data to `/accounts/password/reset/` and asserts the rendered error message uses the styled alert form, NOT `errorlist`.

---

## C. Phase plan summary

| # | Task | Files | Tests |
|---|------|-------|-------|
| 1 | Shared partials: `_input.html` + `_form_card.html` | new | partial-include smoke test |
| 2 | Password-reset flow templates (4) | password_reset, password_reset_done, password_reset_from_key (incl. token_fail branch), password_reset_from_key_done | 4 GET tests |
| 3 | Logged-in password management (2) | password_change, password_set | 2 GET tests |
| 4 | Email management (4) | email, email_change, email_confirm, verification_sent | 2 GET tests + 2 file-exists tests |
| 5 | Edge-case templates (3) | account_inactive, verified_email_required, reauthenticate | 1 GET test + 2 file-exists tests |
| 6 | Resilience signup override (1) | signup.html | 1 file-exists test (the active path is signup_closed) |
| 7 | Negative test: deliberately failing form POST renders styled errors | extends test_allauth_templates.py | 1 |
| 8 | STATUS.md update | docs/superpowers/STATUS.md | — |

Estimated: ~half a day. ~14 new tests, no migrations, no new dependencies. **16 new template files** (14 leaf overrides incl. signup-resilience + 2 shared partials).

---

## D. File touch list

**Create:**
- `templates/account/_input.html` (partial — single form field)
- `templates/account/_form_card.html` (partial — rounded surface card with form scaffold)
- `templates/account/password_reset.html`
- `templates/account/password_reset_done.html`
- `templates/account/password_reset_from_key.html`
- `templates/account/password_reset_from_key_done.html`
- `templates/account/password_change.html`
- `templates/account/password_set.html`
- `templates/account/email.html`
- `templates/account/email_change.html`
- `templates/account/email_confirm.html`
- `templates/account/verification_sent.html`
- `templates/account/account_inactive.html`
- `templates/account/verified_email_required.html`
- `templates/account/reauthenticate.html`
- `templates/account/signup.html`
- `core/tests/test_allauth_templates.py`

**Modify:**
- `docs/superpowers/STATUS.md` — add row + section for this phase.

**Touched but unchanged:**
- The 3 existing styled templates (`login.html`, `logout.html`, `signup_closed.html`) stay as-is. The new partials are NOT retrofitted into them in this phase — that's a follow-up cleanup if/when we touch them next.

---

## E. Brand markers used in tests

The test asserts at least one of these strings is in every rendered template (chosen because they appear stably in the navbar/footer of `base.html`):
- `"Les Retrouvailles"` (footer brand text)
- `"img/logo.png"` (header logo path)
- `"Promotion 1980"` (footer founding-year badge — only on landing variant, skip)

Pick `"Les Retrouvailles"` as the canonical marker. It appears in the footer regardless of auth state and won't move around.

## F. Risks / migration notes

- **No DB schema changes.** Pure template work.
- **No new pip dependencies.**
- **Allauth version pin**: `allauth>=65.0`. If this is bumped to a major where bundled templates' context variables change, our overrides need re-checking. Document the version we tested against in the spec (currently `allauth>=65.x`).
- **Operational ripple**: when these templates ship, every flow becomes prettier. No behavior changes — just visuals. The cooptation password-set flow becomes the most visible win (first-time visitors).
