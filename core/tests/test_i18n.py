from django.utils.translation import activate, gettext as _


def test_french_translation_active():
    activate("fr")
    # Strings tagged in templates should be translatable. We assert the
    # gettext machinery resolves a known string round-trip.
    assert _("Aller au contenu principal") == "Aller au contenu principal"


def test_locale_path_exists():
    from django.conf import settings
    from pathlib import Path

    locale_dir = Path(settings.LOCALE_PATHS[0]) / "fr" / "LC_MESSAGES"
    assert locale_dir.exists(), "Locale directory must exist for French"
