import pytest
from django.test import override_settings
from django.urls import reverse


@override_settings(
    MIDDLEWARE=[
        "core.middleware.BasicAuthMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ],
    BASIC_AUTH_REQUIRED=True,
    BASIC_AUTH_USERNAME="admin",
    BASIC_AUTH_PASSWORD="staging-pass",
)
@pytest.mark.django_db
def test_basic_auth_required_when_enabled(client):
    response = client.get(reverse("health"))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic")


@override_settings(
    MIDDLEWARE=[
        "core.middleware.BasicAuthMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ],
    BASIC_AUTH_REQUIRED=True,
    BASIC_AUTH_USERNAME="admin",
    BASIC_AUTH_PASSWORD="staging-pass",
)
@pytest.mark.django_db
def test_basic_auth_passes_with_correct_credentials(client):
    import base64

    creds = base64.b64encode(b"admin:staging-pass").decode()
    response = client.get(
        reverse("health"),
        HTTP_AUTHORIZATION=f"Basic {creds}",
    )
    assert response.status_code == 200
