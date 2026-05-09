"""Bootstrap Playwright storage states for each handbook audience.

Logs in once per audience (member, co-admin) against the running dev
server, then writes session cookies to `_storage_states/*.json`.
Subsequent flows reuse those cookies via `_browser.py` so they don't
have to re-authenticate.

Idempotent: re-running this script overwrites the JSON files. Safe
to call from `assemble.py` at the start of every handbook build.

Requires the dev server to be running and the demo dataset seeded
(via `seed_handbook_demo`). The credentials match the constants
declared in `members.management.commands.seed_handbook_demo`.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

HANDBOOK_ROOT = Path(__file__).resolve().parent.parent
STATES_DIR = HANDBOOK_ROOT / "flows" / "_storage_states"

# These mirror seed_handbook_demo.DEMO_PASSWORD and the demo usernames.
# Kept verbatim here so this script has zero Django imports — runs from
# any cwd without DJANGO_SETTINGS_MODULE set.
DEMO_PASSWORD = "demo-handbook-pw"  # nosec B105 — local-only handbook fixture
MEMBER_USERNAME = "demo_member_01"
COADMIN_USERNAME = "demo_coadmin"


def _login(page, base_url: str, username: str) -> None:
    """Drive the allauth login form. Username field accepts either
    username or email per the project's auth setup."""
    page.goto(f"{base_url}/accounts/login/")
    page.fill("input[name='login']", username)
    page.fill("input[name='password']", DEMO_PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")


def bootstrap(base_url: str = "http://localhost:8000") -> None:
    STATES_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        for storage_name, username in [
            ("member.json", MEMBER_USERNAME),
            ("coadmin.json", COADMIN_USERNAME),
        ]:
            ctx = browser.new_context(locale="fr-FR")
            page = ctx.new_page()
            _login(page, base_url, username)
            ctx.storage_state(path=str(STATES_DIR / storage_name))
            ctx.close()

        browser.close()


if __name__ == "__main__":
    bootstrap()
