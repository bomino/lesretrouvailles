"""Smoke test: prove pytest + Django settings load correctly."""

from django.conf import settings


def test_settings_loaded():
    assert settings.SECRET_KEY != ""
    assert "core" in settings.INSTALLED_APPS
