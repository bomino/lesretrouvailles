"""Anti-regression smoke test: DESIGN.md tokens must reach compiled CSS.

If any of these assertions fail, either DESIGN.md was edited and
`npm run design:export && npm run css:build` was not re-run, or the
tailwind.config.js stopped consuming the exported theme.
"""
from pathlib import Path

from django.conf import settings


def _read_compiled_css() -> str:
    css_path = Path(settings.STATICFILES_DIRS[0]) / "css" / "output.css"
    assert css_path.exists(), "Run `npm run css:build` first"
    return css_path.read_text(encoding="utf-8")


def test_primary_color_token_compiled():
    assert "1A1C1E" in _read_compiled_css() or "1a1c1e" in _read_compiled_css()


def test_sahel_terra_cotta_token_compiled():
    css = _read_compiled_css()
    assert "A04A2C" in css or "a04a2c" in css


def test_in_memoriam_brown_compiled():
    css = _read_compiled_css()
    assert "5A4A3D" in css or "5a4a3d" in css


def test_whatsapp_green_compiled():
    """The logo-derived WhatsApp green must reach the compiled CSS so
    the `whatsapp-link` component can be styled."""
    css = _read_compiled_css()
    assert "1F6B4F" in css or "1f6b4f" in css


def test_ceremonial_gold_compiled():
    """The logo-derived ceremonial gold must reach the compiled CSS so
    the `promo-badge` component can be styled."""
    css = _read_compiled_css()
    assert "C9A227" in css or "c9a227" in css
