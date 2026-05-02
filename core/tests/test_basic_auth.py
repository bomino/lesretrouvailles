import base64

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

# Pinned MIDDLEWARE so the basic-auth tests aren't affected by P2's
# LoginRequiredMiddleware / ConsentRequiredMiddleware. Only the gate under
# test runs in front of the view.
PINNED_MIDDLEWARE = [
    "core.middleware.BasicAuthMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]


@override_settings(
    MIDDLEWARE=PINNED_MIDDLEWARE,
    BASIC_AUTH_REQUIRED=True,
    BASIC_AUTH_USERNAME="admin",
    BASIC_AUTH_PASSWORD="staging-pass",
)
@pytest.mark.django_db
def test_basic_auth_blocks_anonymous_on_gated_path(client):
    # Use the landing path (`/`) — not in the bypass list, so the gate must engage.
    response = client.get("/")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic")


@override_settings(
    MIDDLEWARE=PINNED_MIDDLEWARE,
    BASIC_AUTH_REQUIRED=True,
    BASIC_AUTH_USERNAME="admin",
    BASIC_AUTH_PASSWORD="staging-pass",
)
@pytest.mark.django_db
def test_basic_auth_passes_with_correct_credentials(client):
    creds = base64.b64encode(b"admin:staging-pass").decode()
    response = client.get("/", HTTP_AUTHORIZATION=f"Basic {creds}")
    assert response.status_code == 200


@override_settings(
    MIDDLEWARE=PINNED_MIDDLEWARE,
    BASIC_AUTH_REQUIRED=True,
    BASIC_AUTH_USERNAME="admin",
    BASIC_AUTH_PASSWORD="staging-pass",
)
@pytest.mark.django_db
def test_basic_auth_bypasses_health_endpoint(client):
    """The Docker / Railway healthcheck cannot send credentials. /health
    must always be reachable so the platform can verify the container is up."""
    response = client.get("/health")
    assert response.status_code == 200


def test_basic_auth_raises_when_required_with_empty_username():
    """Empty credentials would otherwise let any caller in via
    `Authorization: Basic Og==` (base64 of `:`). The middleware must refuse
    to start under that misconfiguration."""
    from core.middleware import BasicAuthMiddleware

    with override_settings(
        BASIC_AUTH_REQUIRED=True,
        BASIC_AUTH_USERNAME="",
        BASIC_AUTH_PASSWORD="not-empty",
    ):
        with pytest.raises(ImproperlyConfigured):
            BasicAuthMiddleware(lambda req: None)


def test_basic_auth_raises_when_required_with_empty_password():
    from core.middleware import BasicAuthMiddleware

    with override_settings(
        BASIC_AUTH_REQUIRED=True,
        BASIC_AUTH_USERNAME="admin",
        BASIC_AUTH_PASSWORD="",
    ):
        with pytest.raises(ImproperlyConfigured):
            BasicAuthMiddleware(lambda req: None)


def test_basic_auth_does_not_raise_when_disabled_with_empty_creds():
    """Empty creds are fine when BASIC_AUTH_REQUIRED is False (dev/prod)."""
    from core.middleware import BasicAuthMiddleware

    with override_settings(
        BASIC_AUTH_REQUIRED=False,
        BASIC_AUTH_USERNAME="",
        BASIC_AUTH_PASSWORD="",
    ):
        # Should construct without raising.
        BasicAuthMiddleware(lambda req: None)


# ---- Settings-level guards added during the pre-staging audit ----


def test_staging_settings_reject_realcloudinary_with_fake_cloud(monkeypatch):
    """Operator pointed CLOUDINARY_CLIENT_PATH at the real client but forgot
    to set CLOUDINARY_CLOUD_NAME, so it kept the 'fake-cloud' default. Loading
    staging settings under that combo must raise so the misconfiguration
    surfaces at boot, not as broken upload URLs at runtime."""
    monkeypatch.setenv("CLOUDINARY_CLIENT_PATH", "alumni.cloudinary.RealCloudinary")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "fake-cloud")
    # Provide the other vars so we don't trip a different guard first.
    monkeypatch.setenv("BASIC_AUTH_REQUIRED", "false")

    import importlib
    import sys

    # Drop any cached staging module so the import re-evaluates with the patched env.
    for mod in list(sys.modules):
        if mod.startswith("alumni.settings"):
            del sys.modules[mod]

    with pytest.raises(ImproperlyConfigured):
        importlib.import_module("alumni.settings.staging")

    # Restore for any later tests in the module.
    for mod in list(sys.modules):
        if mod.startswith("alumni.settings"):
            del sys.modules[mod]
