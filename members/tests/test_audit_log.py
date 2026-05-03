"""Tests for AuditLog — the append-only governance event log."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_audit_log_create_with_actor():
    from members.models import AuditLog

    User = get_user_model()  # noqa: N806
    u = User.objects.create_user(
        username="admin1", email="admin1@example.test", password="x", is_staff=True
    )
    log = AuditLog.objects.create(
        actor=u,
        action="ghost.entry.signed_off",
        target_type="members.PublicSearchEntry",
        target_id="42",
        metadata={"signoff_count_after": 1},
    )
    assert log.actor == u
    assert log.action == "ghost.entry.signed_off"
    assert log.target_id == "42"
    assert log.metadata == {"signoff_count_after": 1}


@pytest.mark.django_db
def test_audit_log_create_anonymous_actor():
    """Anonymous actions (e.g., a public removal request) have actor=None."""
    from members.models import AuditLog

    log = AuditLog.objects.create(
        actor=None,
        action="ghost.removal.requested",
        target_type="members.PublicSearchEntry",
        target_id="42",
        metadata={"requester_email": "x@y.test"},
    )
    assert log.actor is None
    assert log.metadata["requester_email"] == "x@y.test"


@pytest.mark.django_db
def test_audit_log_metadata_accepts_nested_structures():
    from members.models import AuditLog

    log = AuditLog.objects.create(
        actor=None,
        action="ghost.entry.created",
        target_type="members.PublicSearchEntry",
        target_id="1",
        metadata={
            "first_name": "Test",
            "tags": ["one", "two"],
            "deep": {"nested": True},
        },
    )
    log.refresh_from_db()
    assert log.metadata["tags"] == ["one", "two"]
    assert log.metadata["deep"]["nested"] is True


@pytest.mark.django_db
def test_audit_log_str_includes_action_and_target():
    from members.models import AuditLog

    log = AuditLog.objects.create(
        actor=None,
        action="ghost.removal.executed",
        target_type="members.PublicSearchEntry",
        target_id="7",
    )
    s = str(log)
    assert "ghost.removal.executed" in s
    assert "members.PublicSearchEntry:7" in s


@pytest.mark.django_db
def test_audit_log_admin_is_append_only():
    """AuditLogAdmin disables add/change/delete in all paths."""
    from django.contrib import admin

    from members.models import AuditLog

    admin_cls = admin.site._registry[AuditLog].__class__
    a = admin_cls(AuditLog, admin.site)
    assert a.has_add_permission(None) is False
    assert a.has_change_permission(None) is False
    assert a.has_delete_permission(None) is False
