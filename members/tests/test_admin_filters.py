"""Tests for the GhostStatusFilter applied to PublicSearchEntryAdmin."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone


@pytest.fixture
def make_admin(db):
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
def test_ghost_status_filter_buckets(client, make_admin):
    """Each filter value returns the right entries and excludes the others.

    Buckets:
      draft     — 0 cosigners, not removed
      pending   — 1 cosigner,  not removed
      published — 2+ cosigners, not removed, < 365 days old
      stale     — 2+ cosigners, not removed, >= 365 days old
      removed   — removed_at is set (regardless of cosigners)
    """
    from members.models import PublicSearchEntry

    admin_user = make_admin()
    a, b, c = make_admin(), make_admin(), make_admin()

    # Force-login the staff user so the admin changelist is reachable.
    client.force_login(admin_user)

    PublicSearchEntry.objects.create(
        first_name="Draft", last_name_initial="D.", years_at_ceg=[1980]
    )

    e_pending = PublicSearchEntry.objects.create(
        first_name="Pending", last_name_initial="P.", years_at_ceg=[1980]
    )
    e_pending.added_by_admins.add(a)

    e_published = PublicSearchEntry.objects.create(
        first_name="Published", last_name_initial="B.", years_at_ceg=[1980]
    )
    e_published.added_by_admins.add(a, b)

    e_stale = PublicSearchEntry.objects.create(
        first_name="Stale", last_name_initial="T.", years_at_ceg=[1980]
    )
    e_stale.added_by_admins.add(a, b)
    PublicSearchEntry.objects.filter(pk=e_stale.pk).update(
        added_at=timezone.now() - timedelta(days=400)
    )

    e_removed = PublicSearchEntry.objects.create(
        first_name="Removed", last_name_initial="R.", years_at_ceg=[1980]
    )
    e_removed.added_by_admins.add(a, b, c)
    e_removed.removed_at = timezone.now()
    e_removed.save()

    cases = [
        ("draft", "Draft", ["Pending", "Published", "Stale", "Removed"]),
        ("pending", "Pending", ["Draft", "Published", "Stale", "Removed"]),
        ("published", "Published", ["Draft", "Pending", "Stale", "Removed"]),
        ("stale", "Stale", ["Draft", "Pending", "Published", "Removed"]),
        ("removed", "Removed", ["Draft", "Pending", "Published", "Stale"]),
    ]
    for value, expected_present, expected_absent in cases:
        response = client.get(f"/admin/members/publicsearchentry/?ghost_status={value}")
        assert response.status_code == 200, f"GET ?ghost_status={value} failed"
        body = response.content.decode("utf-8")
        assert expected_present in body, f"?ghost_status={value} should include {expected_present}"
        for absent in expected_absent:
            assert absent not in body, f"?ghost_status={value} should NOT include {absent}"
