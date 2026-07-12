"""Shared pytest fixtures for the memoriam app."""

from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone


@pytest.fixture
def make_admin_user(db):
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
    """Authenticated active Member with charter consent."""
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
    return client, member


@pytest.fixture
def make_memoriam_entry(db, make_admin_user):
    """Factory for InMemoriamEntry with sane defaults for a published fiche."""
    from memoriam.models import InMemoriamEntry

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        admin = kwargs.pop("created_by", None) or make_admin_user()
        defaults = {
            "full_name": f"Ahmed Souley {counter['i']}",
            "nickname": "",
            "years_attended": [1980, 1981],
            "classes": ["6e", "5e"],
            "tribute": "Un ami cher.",
            "family_consent_giver": "Sa fille Aïcha",
            "family_consent_date": date(2026, 1, 1),
            "family_consent_canal": "whatsapp",
            "status": "published",
            "created_by": admin,
        }
        defaults.update(kwargs)
        # Mirror the admin save_model invariant: a published fiche always has a
        # publish timestamp. Tests that override status="draft" leave this unset.
        if defaults["status"] == "published" and "published_at" not in defaults:
            defaults["published_at"] = timezone.now()
        return InMemoriamEntry.objects.create(**defaults)

    return _make


@pytest.fixture
def make_memoriam_nomination(db):
    from members.models import Member
    from memoriam.models import InMemoriamNomination

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        nominator = kwargs.pop("nominator", None)
        if nominator is None:
            User = get_user_model()  # noqa: N806
            user = User.objects.create_user(
                username=f"nom{counter['i']}@example.test",
                email=f"nom{counter['i']}@example.test",
                password="x",
            )
            nominator = Member.objects.create(
                user=user,
                first_name="Nom",
                last_name=f"Inator{counter['i']}",
                years_attended=[1980],
                classes=["6e"],
                city="Niamey",
                status="active",
            )
        defaults = {
            "nominator": nominator,
            "proposed_name": f"Camarade Disparu {counter['i']}",
            "proposed_nickname": "",
            "proposed_years": [1980],
            "personal_memory": "Souvenir partagé.",
            "family_contact_hint": "",
        }
        defaults.update(kwargs)
        return InMemoriamNomination.objects.create(**defaults)

    return _make


@pytest.fixture(autouse=True)
def _clear_fake_email_backend():
    """Process-wide class attribute — clear before AND after every test so
    residue can't make a negative assertion pass (or a positive one pass
    against a stale message)."""
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    yield
    FakeResendBackend.sent_messages.clear()
