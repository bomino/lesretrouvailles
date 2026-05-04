"""Shared pytest fixtures for the memoires app."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def make_admin_user(db):
    """Staff+superuser User. Used by admin tests."""
    User = get_user_model()  # noqa: N806
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "username": f"admin{counter['i']}",
            "email": f"admin{counter['i']}@example.test",
            "password": "x",
            "is_staff": True,
            "is_superuser": True,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    return _make


@pytest.fixture
def authed_member_client(db):
    """Authenticated active Member with charter consent. Used by view tests
    so the LoginRequiredMiddleware + ConsentRequiredMiddleware both pass."""
    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="member@example.test",
        email="member@example.test",
        password="x",
    )
    member = Member.objects.create(
        user=user,
        first_name="Test",
        last_name="Member",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    ConsentRecord.objects.create(
        member=member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    client = Client()
    client.force_login(user)
    return client
