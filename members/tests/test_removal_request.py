"""Tests for RemovalRequest — the public 'Retirer mon nom' record."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError


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


@pytest.fixture
def entry(db, make_admin):
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    e.added_by_admins.add(make_admin(), make_admin())
    return e


@pytest.mark.django_db
def test_removal_request_default_status_pending(entry):
    from members.models import RemovalRequest

    r = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    assert r.status == "pending_confirmation"


@pytest.mark.django_db
def test_removal_request_expires_at_30_days_default(entry):
    from members.models import RemovalRequest

    r = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    delta = r.expires_at - r.requested_at
    assert timedelta(days=29, hours=23) <= delta <= timedelta(days=30, minutes=1)


@pytest.mark.django_db
def test_removal_request_confirm_token_unique(entry):
    from django.db import transaction

    from members.models import RemovalRequest

    RemovalRequest.objects.create(
        entry=entry, requester_email="a@x.test", confirm_token="dup-token"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RemovalRequest.objects.create(
                entry=entry, requester_email="b@x.test", confirm_token="dup-token"
            )


@pytest.mark.django_db
def test_removal_request_confirm_token_auto_generated(entry):
    from members.models import RemovalRequest

    r1 = RemovalRequest.objects.create(entry=entry, requester_email="a@x.test")
    r2 = RemovalRequest.objects.create(entry=entry, requester_email="b@x.test")
    assert r1.confirm_token
    assert r2.confirm_token
    assert r1.confirm_token != r2.confirm_token


@pytest.mark.django_db
def test_removal_request_cascade_delete_with_entry(entry):
    """Deleting an entry deletes its RemovalRequests; AuditLog rows stay
    (covered separately in test_audit_signals.py)."""
    from members.models import RemovalRequest

    r = RemovalRequest.objects.create(entry=entry, requester_email="x@y.test")
    rid = r.pk
    entry.delete()
    assert not RemovalRequest.objects.filter(pk=rid).exists()


@pytest.mark.django_db
def test_public_search_entry_removal_token_auto_generated_and_unique(make_admin):
    """P4b tightens removal_token to non-null with default. Two entries
    must get distinct tokens automatically."""
    from members.models import PublicSearchEntry

    e1 = PublicSearchEntry.objects.create(
        first_name="A", last_name_initial="A.", years_at_ceg=[1980]
    )
    e2 = PublicSearchEntry.objects.create(
        first_name="B", last_name_initial="B.", years_at_ceg=[1980]
    )
    assert e1.removal_token
    assert e2.removal_token
    assert e1.removal_token != e2.removal_token
