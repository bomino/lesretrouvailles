"""Flow: member activates their account on mobile.

Mirrors guide_membre.md §2 (Activer votre compte). The page targets are
the public allauth login form — accessible without prior auth, so this
flow runs WITHOUT a storage_state.
"""

from __future__ import annotations

from playwright.sync_api import Browser, expect

from docs.handbook.flows._step import flow_recorder, step

FLOW_ID = "member-mobile-login"
TITLE = "Activer votre compte (mobile)"


def run(browser: Browser, base_url: str) -> None:
    # No storage_state: this flow IS the activation, so we start logged out.
    context = browser.new_context(
        viewport={"width": 360, "height": 800},
        is_mobile=True,
        device_scale_factor=2,
        locale="fr-FR",
    )
    page = context.new_page()
    try:
        with flow_recorder(
            flow_id=FLOW_ID,
            title=TITLE,
            audience="member-mobile",
            source_doc="docs/guides/guide_membre.md",
            source_anchor="#activer-votre-compte",
            viewport={"width": 360, "height": 800},
        ) as manifest:
            step(
                page,
                manifest,
                slug="01-login-page",
                caption=(
                    "Ouvrez la page de connexion. Saisissez votre numéro WhatsApp "
                    "(chiffres uniquement, sans le « + ») ou votre adresse email."
                ),
                action=lambda: page.goto(f"{base_url}/accounts/login/"),
            )
            expect(page.locator("input[name='login']")).to_be_visible()

            step(
                page,
                manifest,
                slug="02-fill-username",
                caption=(
                    "Tapez votre identifiant — par exemple 22790000001 — puis "
                    "votre mot de passe initial."
                ),
                action=lambda: page.fill("input[name='login']", "demo_member_01"),
            )

            step(
                page,
                manifest,
                slug="03-fill-password",
                caption="Entrez votre mot de passe puis appuyez sur « Se connecter ».",
                action=lambda: page.fill("input[name='password']", "demo-handbook-pw"),
            )

            step(
                page,
                manifest,
                slug="04-after-login",
                caption=(
                    "Vous arrivez sur la page d'accueil. Le menu en haut à droite "
                    "vous permet d'accéder à votre profil et à l'annuaire."
                ),
                action=lambda: page.click("button[type='submit']"),
            )
            # Doc-test assertion: post-login we should NOT see the login form.
            expect(page.locator("input[name='login']")).to_have_count(0)
    finally:
        context.close()
