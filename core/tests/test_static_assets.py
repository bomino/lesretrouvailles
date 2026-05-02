from pathlib import Path

from django.conf import settings


def test_compiled_css_is_findable():
    """Tailwind output.css must be present in STATICFILES_DIRS for whitenoise."""
    css_path = Path(settings.STATICFILES_DIRS[0]) / "css" / "output.css"
    assert css_path.exists(), (
        "Compiled CSS missing. Run `npm run css:build` before tests, or add it to the test setup."
    )


def test_htmx_js_is_findable():
    js_path = Path(settings.STATICFILES_DIRS[0]) / "js" / "htmx.min.js"
    assert js_path.exists()
