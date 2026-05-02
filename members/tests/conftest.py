import pytest
from django.contrib.auth import get_user_model

from members.models import Member


@pytest.fixture
def make_user(db):
    user_model = get_user_model()
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "username": f"user{counter['i']}",
            "email": f"user{counter['i']}@example.test",
            "password": "secret-pw-1",
        }
        defaults.update(kwargs)
        return user_model.objects.create_user(**defaults)

    return _make


@pytest.fixture
def make_member(db, make_user):
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        user = kwargs.pop("user", None) or make_user()
        defaults = {
            "user": user,
            "first_name": f"First{counter['i']}",
            "last_name": f"Last{counter['i']}",
            "years_attended": [1980, 1981, 1982, 1983],
            "classes": ["6e", "5e", "4e", "3e"],
            "city": "Niamey",
        }
        defaults.update(kwargs)
        return Member.objects.create(**defaults)

    return _make
