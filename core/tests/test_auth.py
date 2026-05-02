import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_login_page_renders(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200
    assert b"Connexion" in response.content or b"login" in response.content.lower()


@pytest.mark.django_db
def test_signup_returns_closed_response(client):
    """Self-signup is disabled. Members enter via cooptation (P3).

    Allauth's SignupView returns the signup_closed template (200) when
    the adapter's is_open_for_signup() returns False — it does NOT 404.
    We assert there is no functional signup form in the response.
    """
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    assert b'name="password1"' not in response.content
    assert b'name="password2"' not in response.content


@pytest.mark.django_db
def test_existing_user_can_login(client):
    User.objects.create_user(email="moussa@example.com", username="moussa", password="testpass123")
    response = client.post(
        reverse("account_login"),
        {"login": "moussa@example.com", "password": "testpass123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.context["user"].is_authenticated
