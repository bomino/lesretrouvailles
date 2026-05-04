"""Session cookie config: 90-day sliding expiry so parrains stay logged in
between cooptation email clicks (P3.1 spec)."""

from django.conf import settings


def test_session_cookie_age_is_90_days():
    assert settings.SESSION_COOKIE_AGE == 60 * 60 * 24 * 90


def test_session_saves_every_request_for_sliding_expiry():
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
