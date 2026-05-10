"""Browser context helpers for handbook flow scripts.

Three audience profiles, each with its own viewport and pre-loaded
authentication state. Storage states are bootstrapped by
`_storage_states.py` and cached in `_storage_states/` (gitignored).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page

HANDBOOK_ROOT = Path(__file__).resolve().parent.parent
STATES_DIR = HANDBOOK_ROOT / "flows" / "_storage_states"

# Mobile viewport — 360×800 matches the low-end Android baseline the
# audience actually uses. Below this we'd be testing iOS Safari edge
# cases that don't match the real distribution. Above this we'd miss
# the navbar hamburger pattern shipped in P7.2.
MOBILE_VIEWPORT = {"width": 360, "height": 800}
DESKTOP_VIEWPORT = {"width": 1280, "height": 800}

LOCALE = "fr-FR"


@contextmanager
def member_mobile_context(browser: Browser) -> Iterator[Page]:
    yield from _audience_context(
        browser,
        viewport=MOBILE_VIEWPORT,
        storage_state="member.json",
        is_mobile=True,
    )


@contextmanager
def member_desktop_context(browser: Browser) -> Iterator[Page]:
    yield from _audience_context(
        browser,
        viewport=DESKTOP_VIEWPORT,
        storage_state="member.json",
        is_mobile=False,
    )


@contextmanager
def admin_context(browser: Browser) -> Iterator[Page]:
    yield from _audience_context(
        browser,
        viewport=DESKTOP_VIEWPORT,
        storage_state="coadmin.json",
        is_mobile=False,
    )


def _audience_context(
    browser: Browser,
    *,
    viewport: dict[str, int],
    storage_state: str,
    is_mobile: bool,
) -> Iterator[Page]:
    state_path = STATES_DIR / storage_state
    kwargs: dict = {
        "viewport": viewport,
        "locale": LOCALE,
        "is_mobile": is_mobile,
        "device_scale_factor": 2,  # crisp screenshots on retina/print.
    }
    if state_path.exists():
        kwargs["storage_state"] = str(state_path)
    context: BrowserContext = browser.new_context(**kwargs)
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()
