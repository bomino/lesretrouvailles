"""F-10 / F-11 — the memoriam audit trail credited the wrong person, and the
nomination row became unreadable once its nominator was purged.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from members.models import AuditLog


@pytest.mark.django_db
class TestMemoriamAuditActor:
    def test_publish_credits_the_publisher_not_the_creator(
        self, make_admin_user, make_memoriam_entry
    ):
        """The signal used actor=created_by. When Bomino drafts a tribute and a
        co-admin publishes it, the log claimed Bomino published it."""
        creator = make_admin_user(username="creator")
        publisher = make_admin_user(username="publisher")

        entry = make_memoriam_entry(created_by=creator, published_at=None)
        entry.published_at = timezone.now()
        entry._audit_actor = publisher
        entry.save()

        log = AuditLog.objects.get(action="memoriam.entry.published")
        assert log.actor == publisher

    def test_archive_records_an_actor(self, make_admin_user, make_memoriam_entry):
        """Archiving hard-coded actor=None, so the log could not say who did it."""
        archiver = make_admin_user(username="archiver")
        entry = make_memoriam_entry()

        entry.status = "archived"
        entry._audit_actor = archiver
        entry.save()

        log = AuditLog.objects.get(action="memoriam.entry.archived")
        assert log.actor == archiver

    def test_publish_falls_back_to_the_creator_when_no_actor_is_known(
        self, make_admin_user, make_memoriam_entry
    ):
        """A save() from a shell or a data migration has no request, hence no
        actor. Falling back to created_by beats losing the row entirely."""
        creator = make_admin_user(username="shellcreator")
        entry = make_memoriam_entry(created_by=creator, published_at=None)

        entry.published_at = timezone.now()
        entry.save()

        log = AuditLog.objects.get(action="memoriam.entry.published")
        assert log.actor == creator

    def test_nomination_metadata_carries_a_human_readable_name(
        self, django_user_model, make_memoriam_nomination
    ):
        """CLAUDE.md: 'Metadata always includes a human-readable name ... Don't
        store raw IDs only.' The nomination logged nominator_id and nothing else,
        so the row went unreadable the moment that member was purged."""
        from members.models import Member

        user = django_user_model.objects.create_user(username="22790001111", password="x")
        nominator = Member.objects.create(
            user=user,
            first_name="Alpha",
            last_name="Bravo",
            years_attended=[1980],
            classes=["6e"],
            city="Niamey",
            status="active",
        )

        make_memoriam_nomination(nominator=nominator)

        log = AuditLog.objects.get(action="memoriam.nomination.created")
        assert log.metadata["nominator_full_name"] == "Alpha Bravo"
