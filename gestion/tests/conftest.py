"""Fixtures for the gestion app tests.

Mirrors the make_user / make_member / make_application fixtures from
members/tests/conftest.py and cooptation/tests/conftest.py — pytest's
conftest discovery doesn't reach across sibling app trees, so we
duplicate the small builders here rather than monkey-patching the
project layout."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def make_user(db):
    user_model = get_user_model()
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "username": f"gestion_user{counter['i']}",
            "email": f"gestion_user{counter['i']}@example.test",
            "password": "secret-pw-1",
        }
        defaults.update(kwargs)
        return user_model.objects.create_user(**defaults)

    return _make


@pytest.fixture
def make_member(db, make_user):
    from members.models import Member

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


@pytest.fixture
def make_application(db):
    from cooptation.models import AdminApplication

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "full_name": f"Candidate {counter['i']}",
            "nickname": "",
            "years_attended": [1980, 1981],
            "classes": ["6e", "5e"],
            "city": "Niamey",
            "country": "Niger",
            "profession": "",
            "email": f"gestion_candidate{counter['i']}@example.test",
            "whatsapp": "",
        }
        defaults.update(kwargs)
        return AdminApplication.objects.create(**defaults)

    return _make


@pytest.fixture
def make_cooptation_request(db, make_application, make_user):
    """Build a CooptationRequest with a parrain Member behind it."""
    from datetime import timedelta

    from django.utils import timezone

    from cooptation.models import CooptationRequest
    from members.models import Member

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        application = kwargs.pop("application", None) or make_application()
        parrain = kwargs.pop("parrain", None)
        if parrain is None:
            parrain_user = make_user(
                username=f"parrain_gestion_{counter['i']}",
                email=f"parrain_gestion_{counter['i']}@example.test",
            )
            parrain = Member.objects.create(
                user=parrain_user,
                first_name=f"Parrain{counter['i']}",
                last_name="Test",
                years_attended=[1980, 1981, 1982, 1983],
                classes=["6e", "5e", "4e", "3e"],
                city="Niamey",
            )
        defaults = {
            "application": application,
            "parrain": parrain,
            "expires_at": timezone.now() + timedelta(days=14),
        }
        defaults.update(kwargs)
        return CooptationRequest.objects.create(**defaults)

    return _make


@pytest.fixture(autouse=True)
def _clear_fake_email_backend():
    """Mirror cooptation/tests/conftest.py: keep FakeResendBackend.sent_messages
    isolated between gestion tests."""
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    yield
    FakeResendBackend.sent_messages.clear()


@pytest.fixture
def coadmin_user(db):
    """is_staff=True, is_superuser=False — a non-superuser co-admin.

    This is the canonical user gestion is built for: someone who can do
    member-management work via /gestion/ but is NOT allowed to wander into
    /admin/ (that lockdown is enforced in alumni/admin.py)."""
    return User.objects.create_user(
        username="22790000801",
        email="coadmin@example.test",
        password="x",
        is_staff=True,
        is_superuser=False,
    )


@pytest.fixture
def superadmin_user(db):
    """Bomino — full powers, sees the /admin/ escape-hatch link."""
    return User.objects.create_user(
        username="22790000800",
        email="bomino@example.test",
        password="x",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def regular_member_user(db):
    """A non-staff alumni — the 99% of users who must NOT see /gestion/."""
    return User.objects.create_user(
        username="22790000802",
        email="member@example.test",
        password="x",
        is_staff=False,
        is_superuser=False,
    )


@pytest.fixture
def make_memory(db, make_user):
    """Factory for Memory rows. Defaults: status=published, seed public_id.
    Pass status="draft" to build a draft. Pass created_by=user to override
    the auto-created uploader."""
    from memoires.models import Memory

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        created_by = kwargs.pop("created_by", None) or make_user(
            username=f"memory_owner_{counter['i']}",
            email=f"memory_owner_{counter['i']}@example.test",
            is_staff=True,
        )
        defaults = {
            "photo_public_id": f"seed/test-photo-{counter['i']}",
            "caption": f"Test memory {counter['i']}",
            "status": "published",
            "created_by": created_by,
        }
        defaults.update(kwargs)
        return Memory.objects.create(**defaults)

    return _make
