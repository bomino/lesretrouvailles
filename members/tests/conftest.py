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


@pytest.fixture(autouse=True)
def _clear_django_cache():
    """django-ratelimit uses Django's default cache (LocMemCache in tests).
    Clear it between members tests so per-IP/per-user rate limits don't
    bleed across tests sharing the 127.0.0.1 client address."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


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


@pytest.fixture
def consenting_client(db, make_user, make_member):
    """Logged-in member who has signed the charter — passes both
    LoginRequiredMiddleware and ConsentRequiredMiddleware. `.member` is the
    Member instance, so tests can assert against their own name."""
    from django.test import Client

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord

    user = make_user(password="testpass123")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    client = Client()
    client.login(username=user.username, password="testpass123")
    client.member = member
    return client


@pytest.fixture
def make_roster_entry(db):
    """A ClassRosterEntry with a unique source_ref. Synthetic names only."""
    from members.models import ClassRosterEntry

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "source_ref": f"test:6eB:{counter['i']}",
            "school_year_start": 1980,
            "class_label": "6eB",
            "first_name": f"Alpha{counter['i']}",
            "last_name": f"Testeur{counter['i']}",
        }
        defaults.update(kwargs)
        return ClassRosterEntry.objects.create(**defaults)

    return _make


@pytest.fixture(autouse=True)
def _clear_fake_email_backend():
    """FakeResendBackend.sent_messages is a process-wide class attribute.
    Without an autouse clear (cooptation/ and gestion/ have one), residue
    from a previous module leaks in: test_dry_run_makes_no_changes asserts
    `sent_messages == []` and only passed because of collection order."""
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    yield
    FakeResendBackend.sent_messages.clear()
