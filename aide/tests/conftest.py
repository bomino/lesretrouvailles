"""Shared pytest fixtures for the aide app."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


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
