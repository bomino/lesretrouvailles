"""P7 — auth migration: phone-or-email login.

Verifies the post-P7 auth shape: members can log in with either their
WhatsApp number (set as User.username) or their email address. Also
verifies the allauth settings have been migrated to the new
non-deprecated keys.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_login_via_email_works(client):
    """Existing email-based path still works after the auth migration."""
    User.objects.create_user(
        username="22790000001",
        email="moussa@example.com",
        password="testpass123",
    )
    resp = client.post(
        reverse("account_login"),
        {"login": "moussa@example.com", "password": "testpass123"},
        follow=True,
    )
    assert resp.status_code == 200
    assert resp.context["user"].is_authenticated


@pytest.mark.django_db
def test_login_via_username_works(client):
    """A member with no email can log in using their WhatsApp number as
    the username — the dominant case for the soft-launch cohort."""
    User.objects.create_user(
        username="22790000002",
        email="",  # email-less member, the ~80% case
        password="testpass123",
    )
    resp = client.post(
        reverse("account_login"),
        {"login": "22790000002", "password": "testpass123"},
        follow=True,
    )
    assert resp.status_code == 200
    assert resp.context["user"].is_authenticated


@pytest.mark.django_db
def test_settings_use_new_allauth_keys():
    """Confirm we've migrated to the non-deprecated allauth settings.

    Old keys (ACCOUNT_AUTHENTICATION_METHOD, ACCOUNT_EMAIL_REQUIRED,
    ACCOUNT_USERNAME_REQUIRED) trigger deprecation warnings on every
    container start; the new keys (ACCOUNT_LOGIN_METHODS,
    ACCOUNT_SIGNUP_FIELDS) replace them.
    """
    from django.conf import settings

    # New keys present, with the right shape
    assert hasattr(settings, "ACCOUNT_LOGIN_METHODS")
    assert settings.ACCOUNT_LOGIN_METHODS == {"email", "username"}

    assert hasattr(settings, "ACCOUNT_SIGNUP_FIELDS")
    assert "username*" in settings.ACCOUNT_SIGNUP_FIELDS

    # Deprecated keys removed
    assert not hasattr(settings, "ACCOUNT_AUTHENTICATION_METHOD")
    assert not hasattr(settings, "ACCOUNT_EMAIL_REQUIRED")
    assert not hasattr(settings, "ACCOUNT_USERNAME_REQUIRED")
