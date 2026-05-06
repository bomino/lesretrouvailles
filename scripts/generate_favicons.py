"""Regenerate the favicon set from static/img/logo.png.

Run from the project root:

    python scripts/generate_favicons.py

Outputs:
    static/favicon.ico            (multi-size: 16, 32, 48 — legacy + IE)
    static/img/favicon-16x16.png  (browser tab)
    static/img/favicon-32x32.png  (browser tab high-DPI)
    static/img/favicon-48x48.png  (Google search results — minimum recommended)
    static/img/favicon-96x96.png  (Windows pinned tile / extra)
    static/img/favicon-180x180.png (apple-touch-icon — iOS home screen)
    static/img/favicon-192x192.png (Android home screen)
    static/img/favicon-512x512.png (PWA splash / Android maskable)

Re-run whenever logo.png changes. Pillow is the only dependency.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "static" / "img" / "logo.png"
PNG_DIR = REPO_ROOT / "static" / "img"
ICO_PATH = REPO_ROOT / "static" / "favicon.ico"

PNG_SIZES = [16, 32, 48, 96, 180, 192, 512]
ICO_SIZES = [(16, 16), (32, 32), (48, 48)]


def main() -> int:
    if not SOURCE.exists():
        print(f"ERROR: source logo not found at {SOURCE}")
        return 1

    src = Image.open(SOURCE).convert("RGBA")
    print(f"source: {SOURCE} ({src.size}, {src.mode})")

    for size in PNG_SIZES:
        out = PNG_DIR / f"favicon-{size}x{size}.png"
        im = src.resize((size, size), Image.LANCZOS)
        im.save(out, "PNG", optimize=True)
        print(f"  wrote {out.relative_to(REPO_ROOT)} ({out.stat().st_size} bytes)")

    src.resize((48, 48), Image.LANCZOS).save(ICO_PATH, format="ICO", sizes=ICO_SIZES)
    print(f"  wrote {ICO_PATH.relative_to(REPO_ROOT)} ({ICO_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
