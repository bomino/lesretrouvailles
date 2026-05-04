"""Signal-driven AuditLog rows for memoriam events."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_publish_creates_audit_log(make_memoriam_entry):
    from members.models import AuditLog

    entry = make_memoriam_entry(status="draft")
    AuditLog.objects.all().delete()  # clear anything from setup

    from django.utils import timezone

    entry.published_at = timezone.now()
    entry.status = "published"
    entry.save()

    log = AuditLog.objects.get(action="memoriam.entry.published")
    assert log.target_type == "memoriam.InMemoriamEntry"
    assert log.target_id == str(entry.pk)
    assert log.actor_id == entry.created_by_id
    assert log.metadata["full_name"] == entry.full_name
    assert log.metadata["version"] == entry.approved_content_version


@pytest.mark.django_db
def test_archive_creates_audit_log(make_memoriam_entry):
    from members.models import AuditLog

    entry = make_memoriam_entry(status="published")
    AuditLog.objects.all().delete()

    entry.status = "archived"
    entry.save()

    log = AuditLog.objects.get(action="memoriam.entry.archived")
    assert log.target_type == "memoriam.InMemoriamEntry"
    assert log.target_id == str(entry.pk)
    assert log.metadata["full_name"] == entry.full_name


@pytest.mark.django_db
def test_nomination_creates_audit_log(make_memoriam_nomination):
    from members.models import AuditLog

    nom = make_memoriam_nomination()
    log = AuditLog.objects.get(action="memoriam.nomination.created")
    assert log.target_type == "memoriam.InMemoriamNomination"
    assert log.target_id == str(nom.pk)
    assert log.actor_id == nom.nominator.user_id
    assert log.metadata["proposed_name"] == nom.proposed_name
    assert log.metadata["nominator_id"] == nom.nominator_id
