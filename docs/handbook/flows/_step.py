"""Shared step helper for handbook flow scripts.

Each step runs an action, captures a screenshot, and appends a manifest
entry. The manifest is written by the FlowRecorder context manager when
the flow finishes — so a flow that crashes mid-way still leaves a
partial manifest, useful for debugging.

This helper deliberately does NOT use pytest-playwright fixtures —
flows are run directly by docs/handbook/assemble.py (not under
pytest), so plain Playwright sync API is enough.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

# All paths in this module are relative to docs/handbook/.
HANDBOOK_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = HANDBOOK_ROOT / "screenshots" / "curated"
MANIFEST_DIR = HANDBOOK_ROOT / "flows" / "_output"


@dataclass
class StepRecord:
    slug: str
    screenshot: str  # path relative to HANDBOOK_ROOT
    caption: str


@dataclass
class FlowManifest:
    flow_id: str
    title: str
    audience: str  # "member-mobile" | "member-desktop" | "admin"
    source_doc: str  # e.g. "docs/guides/guide_membre.md"
    source_anchor: str  # e.g. "#activer-votre-compte"
    viewport: dict[str, int]
    steps: list[StepRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "title": self.title,
            "audience": self.audience,
            "source_doc": self.source_doc,
            "source_anchor": self.source_anchor,
            "viewport": self.viewport,
            "steps": [s.__dict__ for s in self.steps],
        }


@contextmanager
def flow_recorder(
    *,
    flow_id: str,
    title: str,
    audience: str,
    source_doc: str,
    source_anchor: str,
    viewport: dict[str, int],
):
    """Context manager that yields a recorder; writes the manifest on exit.

    Used by each flow_*.py script:

        with flow_recorder(flow_id="member-mobile-login", ...) as rec:
            step(page, rec, slug="01-login", caption="...", action=lambda: ...)
    """
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = FlowManifest(
        flow_id=flow_id,
        title=title,
        audience=audience,
        source_doc=source_doc,
        source_anchor=source_anchor,
        viewport=viewport,
    )
    try:
        yield manifest
    finally:
        out = MANIFEST_DIR / f"{flow_id}.json"
        out.write_text(
            json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def step(
    page: Page,
    manifest: FlowManifest,
    *,
    slug: str,
    caption: str,
    action: Callable[[], None] | None = None,
    full_page: bool = False,
) -> None:
    """Run optional action, then screenshot and record the step.

    `slug` becomes part of the screenshot filename. `caption` is the
    French sentence shown beneath the screenshot in the assembled
    handbook.

    `full_page=True` captures the entire scrollable page (used for
    long content like the directory or FAQ); the default captures
    the viewport only, which is what mobile readers actually see.
    """
    if action is not None:
        action()
    # Allow async network/animation to settle before capturing.
    page.wait_for_load_state("networkidle")
    filename = f"{manifest.flow_id}-{len(manifest.steps) + 1:02d}-{slug}.png"
    target = SCREENSHOTS_DIR / filename
    page.screenshot(path=str(target), full_page=full_page)
    rel = target.relative_to(HANDBOOK_ROOT).as_posix()
    manifest.steps.append(StepRecord(slug=slug, screenshot=rel, caption=caption))
