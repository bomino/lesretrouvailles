"""Tests that ORM events on PublicSearchEntry / RemovalRequest write
the right AuditLog entries."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


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
def test_creating_entry_writes_audit_entry_created(make_admin):
    from members.models import AuditLog, PublicSearchEntry

    AuditLog.objects.all().delete()  # clear any prior signal noise
    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    log = AuditLog.objects.get(
        action="ghost.entry.created",
        target_type="members.PublicSearchEntry",
        target_id=str(e.pk),
    )
    assert log.metadata["first_name"] == "Idrissa"
    assert log.metadata["last_name_initial"] == "S."


@pytest.mark.django_db
def test_adding_admin_to_signoffs_writes_signed_off(make_admin):
    from members.models import AuditLog, PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    AuditLog.objects.filter(action="ghost.entry.signed_off").delete()
    a = make_admin()
    e.added_by_admins.add(a)
    log = AuditLog.objects.get(
        action="ghost.entry.signed_off",
        target_id=str(e.pk),
    )
    assert log.actor == a
    assert log.metadata["signer_pk"] == a.pk
    assert log.metadata["signoff_count_after"] == 1


@pytest.mark.django_db
def test_adding_two_admins_in_one_call_writes_two_audit_entries(make_admin):
    from members.models import AuditLog, PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    AuditLog.objects.filter(action="ghost.entry.signed_off").delete()
    a, b = make_admin(), make_admin()
    e.added_by_admins.add(a, b)
    logs = AuditLog.objects.filter(action="ghost.entry.signed_off", target_id=str(e.pk))
    assert logs.count() == 2


@pytest.mark.django_db
def test_removing_admin_from_signoffs_writes_signoff_removed(make_admin):
    from members.models import AuditLog, PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    a = make_admin()
    e.added_by_admins.add(a)
    AuditLog.objects.filter(action="ghost.entry.signoff_removed").delete()
    e.added_by_admins.remove(a)
    log = AuditLog.objects.get(action="ghost.entry.signoff_removed", target_id=str(e.pk))
    assert log.actor == a


@pytest.mark.django_db
def test_deleting_pending_removal_request_writes_cancelled(make_admin):
    from members.models import AuditLog, PublicSearchEntry, RemovalRequest

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    r = RemovalRequest.objects.create(entry=e, requester_email="x@y.test")
    rid = r.pk

    AuditLog.objects.filter(action="ghost.removal.cancelled").delete()
    r.delete()
    log = AuditLog.objects.get(action="ghost.removal.cancelled", target_id=str(rid))
    assert log.metadata["entry_pk"] == e.pk
    assert log.metadata["requester_email"] == "x@y.test"


@pytest.mark.django_db
def test_deleting_confirmed_removal_request_does_not_write_cancelled(make_admin):
    """Only pending status triggers the cancellation hook — once confirmed,
    the existing 'requested'/'confirmed'/'executed' chain has the history."""
    from django.utils import timezone

    from members.models import AuditLog, PublicSearchEntry, RemovalRequest

    e = PublicSearchEntry.objects.create(
        first_name="X", last_name_initial="X.", years_at_ceg=[1980]
    )
    r = RemovalRequest.objects.create(
        entry=e, requester_email="x@y.test", status="confirmed", confirmed_at=timezone.now()
    )
    AuditLog.objects.filter(action="ghost.removal.cancelled").delete()
    r.delete()
    assert not AuditLog.objects.filter(action="ghost.removal.cancelled").exists()
