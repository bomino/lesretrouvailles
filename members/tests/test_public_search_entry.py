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
def test_entry_with_one_admin_is_published(make_admin):
    """F-12: this asserted the OPPOSITE, pinning a rule production abandoned.

    Since P4d (single-admin governance) the landing page, the admin filter, the
    stale-ghost cron and the launch audit all publish at ONE signoff — the
    creating admin is auto-cosigned and the other staff get a notification, a
    post-publication tripwire rather than a pre-publication gate. Only
    `is_published` still said two, and this test kept it that way: a passing
    suite that contradicted the running site.
    """
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin())
    assert e.is_published is True


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
    """Defense-in-depth: a 3-char value is rejected at the DB layer.
    With max_length=2 it now hits the column-length cap (DataError)
    before reaching the CHECK constraint (IntegrityError). Either is
    acceptable — both are subclasses of DatabaseError."""
    from django.db import DatabaseError, transaction

    from members.models import PublicSearchEntry

    with pytest.raises(DatabaseError):
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
def test_full_clean_rejects_long_initial_with_friendly_message():
    """The model.clean() check fires BEFORE the DB CHECK constraint and
    surfaces a friendly French error to the admin form, rather than the
    raw constraint name."""
    from django.core.exceptions import ValidationError

    from members.models import PublicSearchEntry

    entry = PublicSearchEntry(
        first_name="Oumarou",
        last_name_initial="Moussa",  # full name, not initial — common mistake
        years_at_ceg=[1984],
    )
    with pytest.raises(ValidationError) as exc_info:
        entry.full_clean()

    msg = str(exc_info.value)
    assert "Saisissez 1 à 2 caractères" in msg
    assert "M" in msg  # the worked example
    # The friendly message should NOT mention the raw constraint name
    assert "initial_must_be_one_or_two_chars" not in msg


@pytest.mark.django_db
def test_full_clean_accepts_one_or_two_char_initial():
    from members.models import PublicSearchEntry

    for init in ["M", "m", "M.", "Mc", "Da", "À"]:
        entry = PublicSearchEntry(first_name="Test", last_name_initial=init, years_at_ceg=[1980])
        entry.full_clean()  # must not raise
