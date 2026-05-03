import pytest
from bs4 import BeautifulSoup
from django.test import Client


@pytest.mark.django_db
def test_signup_form_inputs_have_labels():
    response = Client().get("/inscription/")
    soup = BeautifulSoup(response.content, "html.parser")
    inputs = soup.select("form input[type='text'], form input[type='email']")
    for inp in inputs:
        assert inp.find_parent("label") is not None, f"Input {inp.get('name')} has no parent label"


@pytest.mark.django_db
def test_signup_includes_noindex_implicitly():
    """Public form pages don't need to be noindex (the home page IS the
    public surface eventually) — but for now, until P4, we noindex."""
    response = Client().get("/inscription/")
    assert b'name="robots"' in response.content
