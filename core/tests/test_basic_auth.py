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
    # Use a private path that is not in any bypass set.
    response = client.get("/admin/")
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
    """Probes /admin/ specifically because /, /sitemap.xml, /robots.txt all
    bypass the credential check unconditionally now (see PUBLIC_GHOST_LIST_*
    bypass set). Hitting a gated path is what actually exercises the
    base64-decode + compare branch of the middleware."""
    creds = base64.b64encode(b"admin:staging-pass").decode()
    response = client.get("/admin/", HTTP_AUTHORIZATION=f"Basic {creds}")
    # 302 is the Django admin's redirect-to-login when the basic-auth check
    # passes but the user isn't logged in; what we care about is that we got
    # past the 401 from BasicAuthMiddleware.
    assert response.status_code != 401


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


@pytest.mark.django_db
@pytest.mark.parametrize("public_path", ["/", "/sitemap.xml", "/robots.txt"])
def test_basic_auth_exact_match_bypasses_for_public_paths(client, settings, public_path):
    """The landing, sitemap, and robots must be reachable without basic-auth
    credentials so SEO crawlers can index the public surface on staging."""
    settings.MIDDLEWARE = PINNED_MIDDLEWARE
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    response = client.get(public_path)

    # Path resolves (200) or 404/302 from the inner view — what matters is
    # we got past the 401 Basic auth gate.
    assert response.status_code != 401, f"Public path {public_path} was blocked by basic auth"


@pytest.mark.django_db
@pytest.mark.parametrize("private_path", ["/profil/", "/annuaire/", "/admin/"])
def test_basic_auth_blocks_private_paths_when_no_credentials(client, settings, private_path):
    """Regression: a naive `path.startswith('/')` would defeat basic auth
    entirely since every URL starts with '/'. The middleware uses an
    exact-match set for short public paths and prefix-match only for
    explicit prefixes. This test pins that distinction."""
    settings.MIDDLEWARE = PINNED_MIDDLEWARE
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    response = client.get(private_path)
    assert response.status_code == 401, (
        f"Private path {private_path} should require basic auth; got {response.status_code}"
    )


@pytest.mark.django_db
def test_basic_auth_bypasses_static_prefix(client, settings):
    """Static asset prefix bypass — crawler-friendly without exposing credentials."""
    settings.MIDDLEWARE = PINNED_MIDDLEWARE
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    response = client.get("/static/css/output.css")
    assert response.status_code != 401


@pytest.mark.django_db
def test_basic_auth_bypasses_inscription_prefix(client, settings):
    """The cooptation signup URL must be publicly reachable too."""
    settings.MIDDLEWARE = PINNED_MIDDLEWARE
    settings.BASIC_AUTH_REQUIRED = True
    settings.BASIC_AUTH_USERNAME = "admin"
    settings.BASIC_AUTH_PASSWORD = "secret"

    response = client.get("/inscription/")
    assert response.status_code != 401
