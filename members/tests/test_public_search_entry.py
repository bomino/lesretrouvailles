"""Tests for PublicSearchEntry — the public 'ghost list' model.

Privacy-by-design: a name only renders publicly when 2+ Super Admins have
signed off (M2M added_by_admins) AND the entry has not been removed.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone


@pytest.fixture
def make_admin(db):
    """A staff/superuser usable as one of the 2 publication co-signers."""
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


@pytest.mark.django_db
def test_entry_with_zero_admins_is_unpublished(make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    assert e.is_published is False


@pytest.mark.django_db
def test_entry_with_one_admin_is_unpublished(make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin())
    assert e.is_published is False


@pytest.mark.django_db
def test_entry_with_two_admins_is_published(make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin(), make_admin())
    assert e.is_published is True


@pytest.mark.django_db
def test_removed_entry_is_unpublished_regardless_of_admin_count(make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin(), make_admin(), make_admin())
    e.removed_at = timezone.now()
    e.save()
    assert e.is_published is False


@pytest.mark.django_db
def test_last_name_initial_check_constraint_rejects_three_chars():
    from django.db import transaction

    from members.models import PublicSearchEntry

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PublicSearchEntry.objects.create(
                first_name="X", last_name_initial="ABC", years_at_ceg=[1980]
            )


@pytest.mark.django_db
def test_removal_token_unique_when_set():
    from django.db import transaction

    from members.models import PublicSearchEntry

    PublicSearchEntry.objects.create(
        first_name="A", last_name_initial="A.", years_at_ceg=[1980], removal_token="tok1"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PublicSearchEntry.objects.create(
                first_name="B",
                last_name_initial="B.",
                years_at_ceg=[1980],
                removal_token="tok1",
            )


@pytest.mark.django_db
def test_removal_token_nullable_allows_multiple_unset():
    from members.models import PublicSearchEntry

    PublicSearchEntry.objects.create(
        first_name="A", last_name_initial="A.", years_at_ceg=[1980], removal_token=None
    )
    PublicSearchEntry.objects.create(
        first_name="B", last_name_initial="B.", years_at_ceg=[1980], removal_token=None
    )
    assert PublicSearchEntry.objects.filter(removal_token__isnull=True).count() == 2
