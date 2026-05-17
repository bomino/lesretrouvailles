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


@pytest.fixture(autouse=True)
def _clear_django_cache():
    """django-ratelimit uses Django's default cache (LocMemCache in tests).
    Clear it between aide tests so per-IP rate limits don't bleed across
    tests sharing the 127.0.0.1 client address."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
