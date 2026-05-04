"""Pending-vouches dashboard at /cooptations-a-valider/ — member-only listing
of CooptationRequests still awaiting a response from the current user."""

import pytest
from django.test import Client

URL = "/cooptations-a-valider/"


@pytest.mark.django_db
def test_anonymous_user_redirects_to_login():
    response = Client().get(URL)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_authenticated_user_without_member_sees_empty_state(make_user):
    """Admin or any auth'd user with no Member profile gets an empty list,
    not a 500 — the view defends with getattr(..., 'member', None)."""
    user = make_user(password="x")
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get(URL)
    assert response.status_code == 200
    assert b"aucune cooptation en attente" in response.content
