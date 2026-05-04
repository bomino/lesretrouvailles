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
