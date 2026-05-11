"""Flow: co-admin manages the Mur des souvenirs via /gestion/souvenirs/.

Mirrors guide_admin.md §6 (Gérer le contenu du Mur des souvenirs).
Drives the /gestion/ console as a co-admin to demonstrate the photo
curation workflow that shipped 2026-05-10:

1. Spot the new "Souvenirs en brouillon" tile on the dashboard.
2. Open the Souvenirs list (filter chips + grid + search).
3. Click "Ajouter une photo" to see the create form.
4. Click an existing photo to see the edit page (photo preview +
   prefilled form + status-toggle subform).
"""

from __future__ import annotations

from playwright.sync_api import Browser, expect

from docs.handbook.flows._browser import admin_context
from docs.handbook.flows._step import flow_recorder, step

FLOW_ID = "admin-souvenirs"
TITLE = "Gérer le Mur des souvenirs (ajouter, modifier, publier)"


def run(browser: Browser, base_url: str) -> None:
    with admin_context(browser) as page:
        with flow_recorder(
            flow_id=FLOW_ID,
            title=TITLE,
            audience="admin",
            source_doc="docs/guides/guide_admin.md",
            source_anchor="#gerer-le-contenu-du-mur-des-souvenirs",
            viewport={"width": 1280, "height": 800},
        ) as manifest:
            step(
                page,
                manifest,
                slug="01-dashboard-souvenirs-tile",
                caption=(
                    "Sur le tableau de bord /gestion/, la 4ᵉ tuile "
                    "« Souvenirs en brouillon » compte les photos téléversées "
                    "qui attendent d'être publiées. Cliquez dessus pour "
                    "ouvrir la liste filtrée, ou utilisez le sous-menu "
                    "« Souvenirs »."
                ),
                action=lambda: page.goto(f"{base_url}/gestion/"),
            )

            step(
                page,
                manifest,
                slug="02-list-curation",
                caption=(
                    "La console Souvenirs affiche toutes les photos du Mur. "
                    "Les puces « Toutes / Publiées / Brouillons » filtrent "
                    "par statut. La barre de recherche filtre par légende "
                    "ou lieu (les accents sont tolérés)."
                ),
                action=lambda: page.goto(f"{base_url}/gestion/souvenirs/"),
                full_page=True,
            )

            step(
                page,
                manifest,
                slug="03-create-form",
                caption=(
                    "Cliquez sur « Ajouter une photo » pour téléverser une "
                    "nouvelle image. Formats acceptés : JPEG, PNG, WebP, 8 Mo "
                    "maximum. Légende obligatoire ; date approximative et "
                    "lieu sont optionnels. Choisissez « Brouillon » pour "
                    "préparer en avance ou « Publiée » pour mettre en ligne "
                    "tout de suite."
                ),
                action=lambda: page.click("a:has-text('Ajouter une photo')"),
            )
            expect(page.locator("label:has-text('Légende')")).to_be_visible()

            # Return to the list, then click the first photo card to enter
            # the edit view. The list-card link wraps the thumbnail in an
            # <a href="/gestion/souvenirs/<pk>/modifier/">.
            def _click_first_photo_card() -> None:
                page.goto(f"{base_url}/gestion/souvenirs/")
                # The grid is a <ul><li><a>...</a></li>...</ul>. The first
                # <a> inside a <li> in the grid is the first photo card.
                page.locator("ul li a[href*='/gestion/souvenirs/']").first.click()

            step(
                page,
                manifest,
                slug="04-edit-with-status-toggle",
                caption=(
                    "Cliquez sur une photo dans la liste pour ouvrir sa page "
                    "d'édition. L'aperçu pleine taille s'affiche en haut, "
                    "suivi du formulaire (remplacer la photo, modifier la "
                    "légende/date/lieu/statut). Tout en bas, le bouton "
                    "« Publier » (ou « Dépublier ») bascule le statut sans "
                    "avoir à resauvegarder le reste."
                ),
                action=_click_first_photo_card,
                full_page=True,
            )
