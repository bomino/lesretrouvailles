"""Flow: co-admin regenerates a magic link for a member.

Mirrors guide_admin.md §4 (Renvoyer un lien magique). Drives the
/gestion/ console as a co-admin (not super-admin), confirming that
the staff_required gate in gestion.decorators allows the journey
end-to-end.
"""

from __future__ import annotations

from playwright.sync_api import Browser, expect

from docs.handbook.flows._browser import admin_context
from docs.handbook.flows._step import flow_recorder, step

FLOW_ID = "admin-magic-link-reissue"
TITLE = "Régénérer un lien de connexion pour un membre"


def run(browser: Browser, base_url: str) -> None:
    with admin_context(browser) as page:
        with flow_recorder(
            flow_id=FLOW_ID,
            title=TITLE,
            audience="admin",
            source_doc="docs/guides/guide_admin.md",
            source_anchor="#renvoyer-un-lien-magique",
            viewport={"width": 1280, "height": 800},
        ) as manifest:
            step(
                page,
                manifest,
                slug="01-gestion-dashboard",
                caption=(
                    "Connectez-vous à /gestion/ avec votre compte co-admin. "
                    "Le tableau de bord récapitule les membres et "
                    "cooptations en attente."
                ),
                action=lambda: page.goto(f"{base_url}/gestion/"),
            )

            step(
                page,
                manifest,
                slug="02-member-list",
                caption=(
                    "Cliquez sur « Membres » pour voir la liste. Chaque "
                    "ligne ouvre la fiche du membre."
                ),
                action=lambda: page.goto(f"{base_url}/gestion/membres/"),
                full_page=True,
            )

            step(
                page,
                manifest,
                slug="03-member-detail",
                caption=(
                    "Sélectionnez le membre concerné — ici Aïcha Moussa. "
                    "La fiche regroupe identité, identifiant WhatsApp, "
                    "statut et actions disponibles."
                ),
                action=lambda: page.click("a:has-text('Aïcha Moussa')"),
            )
            expect(page.locator("text=Aïcha Moussa").first).to_be_visible()

            step(
                page,
                manifest,
                slug="04-link-confirmation",
                caption=(
                    "Cliquez sur « Régénérer un lien de connexion ». La "
                    "page de confirmation rappelle la durée de validité "
                    "(7 jours) et le contexte d'usage."
                ),
                action=lambda: page.click("a:has-text('Régénérer un lien')"),
            )
            expect(page.locator("button:has-text('Générer un nouveau lien')")).to_be_visible()

            step(
                page,
                manifest,
                slug="05-link-generated",
                caption=(
                    "Cliquez sur « Générer un nouveau lien ». Le lien "
                    "apparaît, prêt à copier ou à partager via WhatsApp."
                ),
                action=lambda: page.click("button:has-text('Générer un nouveau lien')"),
            )
            expect(page.locator("#magic-link-url")).to_be_visible()

            step(
                page,
                manifest,
                slug="06-share-options",
                caption=(
                    "Le bouton « Copier » place l'URL dans le presse-papiers. "
                    "« Envoyer par WhatsApp » ouvre wa.me avec un message "
                    "pré-rédigé pour le membre."
                ),
                full_page=True,
            )
