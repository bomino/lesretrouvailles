"""Orchestrator for `make handbook`.

Sequence:
  1. Start `manage.py runserver` (background).
  2. Wait for the server to accept connections.
  3. Bootstrap Playwright storage states (login as demo member + co-admin).
  4. For each flow module: import + run; each writes a manifest JSON.
  5. Read all manifests + the existing markdown guides + FAQ entries.
  6. Render Jinja2 template -> docs/handbook/handbook.html.
  7. Use Playwright to print handbook.html -> docs/handbook/handbook.pdf.
  8. Stop runserver (always, even on flow failure).

Run from the repo root:  python docs/handbook/assemble.py
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

# Repo root (this file is at docs/handbook/assemble.py — go up two).
ROOT = Path(__file__).resolve().parent.parent.parent
HANDBOOK = ROOT / "docs" / "handbook"
GUIDES = ROOT / "docs" / "guides"

# Make `from aide.faq import ...` and `from docs.handbook.flows...` resolvable.
sys.path.insert(0, str(ROOT))

FLOW_MODULES = [
    "docs.handbook.flows.flow_member_mobile_login",
    "docs.handbook.flows.flow_member_desktop_directory",
    "docs.handbook.flows.flow_admin_magic_link_reissue",
    "docs.handbook.flows.flow_admin_souvenirs",
]

BASE_URL = "http://localhost:8000"
SERVER_BIND = "127.0.0.1:8000"


def main() -> int:
    server = _start_runserver()
    try:
        _wait_for_server()
        _run_flows()
        manifests = _load_manifests()
        html = _render_handbook(manifests)
        out_html = HANDBOOK / "handbook.html"
        out_html.write_text(html, encoding="utf-8")
        print(f"  -> {out_html.relative_to(ROOT)}")
        out_pdf = HANDBOOK / "handbook.pdf"
        _render_pdf(out_html, out_pdf)
        print(f"  -> {out_pdf.relative_to(ROOT)}")
    finally:
        _stop_runserver(server)
    return 0


def _start_runserver() -> subprocess.Popen:
    print("[handbook] starting runserver...")
    log = HANDBOOK / "flows" / "_output" / "runserver.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "alumni.settings.dev")
    return subprocess.Popen(
        [sys.executable, "manage.py", "runserver", "--noreload", SERVER_BIND],
        cwd=str(ROOT),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=env,
    )


def _wait_for_server(timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL, timeout=1):
                print("[handbook] runserver ready.")
                return
        except Exception as exc:
            last_err = exc
            time.sleep(0.5)
    raise RuntimeError(
        f"runserver did not start within {timeout}s. Last error: {last_err}. "
        f"Check {HANDBOOK / 'flows' / '_output' / 'runserver.log'}"
    )


def _stop_runserver(p: subprocess.Popen) -> None:
    print("[handbook] stopping runserver...")
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()


def _run_flows() -> None:
    from playwright.sync_api import sync_playwright

    from docs.handbook.flows import _storage_states

    print("[handbook] bootstrapping storage states...")
    _storage_states.bootstrap(BASE_URL)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for module_name in FLOW_MODULES:
                print(f"[handbook] running {module_name.rsplit('.', 1)[-1]}...")
                mod = importlib.import_module(module_name)
                mod.run(browser, BASE_URL)
        finally:
            browser.close()


def _load_manifests() -> list[dict]:
    out = HANDBOOK / "flows" / "_output"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out.glob("*.json"))]


def _render_handbook(manifests: list[dict]) -> str:
    import markdown
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    md = markdown.Markdown(extensions=["extra", "toc"], output_format="html5")
    guide_membre_html = md.convert((GUIDES / "guide_membre.md").read_text(encoding="utf-8"))
    md.reset()
    guide_admin_html = md.convert((GUIDES / "guide_admin.md").read_text(encoding="utf-8"))

    # FAQ — typed Python list. Each entry has .category, .question, .answer
    # (markdown-with-bleach pipeline lives in aide/views.py; for the handbook
    # we re-render with a plain markdown converter — the source already passes
    # bleach so the HTML is safe.)
    from aide.faq import CATEGORY_META, FAQ_ENTRIES

    md_faq = markdown.Markdown(extensions=["extra"])
    faq_by_category: dict[str, list[dict]] = {key: [] for key in CATEGORY_META}
    for entry in FAQ_ENTRIES:
        faq_by_category[entry.category].append(
            {
                "question": entry.question,
                "answer_html": md_faq.convert(entry.answer_md),
                "anchor": entry.slug,
            }
        )
        md_faq.reset()

    chapters = [
        {
            "id": "ch-member-mobile",
            "title": "Pour les membres (mobile)",
            "intro": (
                "Captures d'écran prises sur un téléphone Android (largeur 360 px). "
                "C'est l'expérience que vivent ~80 % des membres."
            ),
            "flows": [m for m in manifests if m["audience"] == "member-mobile"],
        },
        {
            "id": "ch-member-desktop",
            "title": "Pour les membres (ordinateur)",
            "intro": "Mêmes parcours, vus sur ordinateur (largeur 1280 px).",
            "flows": [m for m in manifests if m["audience"] == "member-desktop"],
        },
        {
            "id": "ch-admin",
            "title": "Pour les administrateurs",
            "intro": (
                "Console /gestion/ vue par un co-admin. Le super-admin voit "
                "exactement les mêmes pages plus l'accès au panneau Django /admin/."
            ),
            "flows": [m for m in manifests if m["audience"] == "admin"],
        },
    ]

    env = Environment(
        loader=FileSystemLoader(str(HANDBOOK)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("template.html")
    return template.render(
        title="Les Retrouvailles — Guide illustré",
        build_date=date.today().isoformat(),
        chapters=chapters,
        guide_membre_html=guide_membre_html,
        guide_admin_html=guide_admin_html,
        faq_categories=CATEGORY_META,
        faq_by_category=faq_by_category,
    )


def _render_pdf(html_path: Path, pdf_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    print("[handbook] rendering PDF...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(f"file:///{html_path.as_posix()}")
            page.wait_for_load_state("networkidle")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={
                    "top": "1.5cm",
                    "right": "1.2cm",
                    "bottom": "1.5cm",
                    "left": "1.2cm",
                },
            )
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
