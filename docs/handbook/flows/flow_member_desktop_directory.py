"""Flow: member searches the directory on desktop.

Mirrors guide_membre.md §5 (Trouver vos camarades). Exercises the
multi-token search and the promotion-year quick-pick chips that
ship in the directory.
"""

from __future__ import annotations

from playwright.sync_api import Browser, expect

from docs.handbook.flows._browser import member_desktop_context
from docs.handbook.flows._step import flow_recorder, step

FLOW_ID = "member-desktop-directory"
TITLE = "Trouver vos camarades (annuaire)"


def run(browser: Browser, base_url: str) -> None:
    with member_desktop_context(browser) as page:
        with flow_recorder(
            flow_id=FLOW_ID,
            title=TITLE,
            audience="member-desktop",
            source_doc="docs/guides/guide_membre.md",
            source_anchor="#trouver-vos-camarades",
            viewport={"width": 1280, "height": 800},
        ) as manifest:
            step(
                page,
                manifest,
                slug="01-directory-landing",
                caption=(
                    "L'annuaire liste tous les membres inscrits, classés par "
                    "ordre alphabétique. La barre de recherche en haut accepte "
                    "le prénom, le nom, le surnom, la ville ou la profession."
                ),
                action=lambda: page.goto(f"{base_url}/annuaire/"),
            )
            expect(page.locator("input[type='search'], input[name='q']").first).to_be_visible()

            step(
                page,
                manifest,
                slug="02-search-by-name",
                caption=(
                    "Tapez plusieurs mots pour affiner — ex. « Aïcha Zinder » "
                    "trouve les camarades dont le prénom ET la ville "
                    "correspondent. La recherche tolère les accents."
                ),
                action=lambda: page.locator("input[name='q']").first.fill("Aïcha Zinder"),
            )
            # Allow HTMX debounce + roundtrip to settle.
            page.wait_for_timeout(800)

            step(
                page,
                manifest,
                slug="03-search-results",
                caption=(
                    "Les résultats apparaissent en dessous. Cliquez sur une "
                    "carte pour ouvrir le profil détaillé."
                ),
                full_page=True,
            )

            def _click_promotion_1980() -> None:
                page.locator("input[name='q']").first.fill("")
                page.wait_for_timeout(400)
                chip = page.locator("nav[aria-label*='promotion' i] a", has_text="1980").first
                chip.click()

            step(
                page,
                manifest,
                slug="04-promotion-chip",
                caption=(
                    "Les puces « Promotion » filtrent l'annuaire par année "
                    "d'arrivée au CEG. Cliquez sur 1980 pour ne voir que les "
                    "camarades qui y étaient cette année-là."
                ),
                action=_click_promotion_1980,
            )
            page.wait_for_timeout(800)

            step(
                page,
                manifest,
                slug="05-filtered-results",
                caption=(
                    "L'annuaire affiche maintenant uniquement les camarades "
                    "de la promotion 1980. Cliquez sur « Toutes » pour "
                    "réinitialiser le filtre."
                ),
                full_page=True,
            )
