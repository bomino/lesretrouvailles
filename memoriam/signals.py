"""AuditLog signal handlers for the memoriam app.

Following the pattern from members/signals.py: handlers register at app
startup via MemoriamConfig.ready() and write to members.AuditLog whenever
a domain event happens that should be auditable.
"""

from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from members.models import AuditLog

from .models import InMemoriamEntry, InMemoriamNomination


def _actor_for(instance):
    """Who to credit for this save.

    A signal cannot see the request, so the publish handler used to credit
    `created_by` — meaning when Bomino drafted a tribute and a co-admin
    published it, the audit log said Bomino published it. Archive was worse:
    it hard-coded actor=None, so the log could never say who did it.

    The mutation sites (memoriam/admin.py) now stash the real actor on the
    instance before calling save(). `created_by` remains the fallback for saves
    with no request behind them — a shell session or a data migration — because
    a slightly-wrong actor beats an unattributable row.
    """
    actor = getattr(instance, "_audit_actor", None)
    if actor is not None and getattr(actor, "is_authenticated", False):
        return actor
    return getattr(instance, "created_by", None)


@receiver(pre_save, sender=InMemoriamEntry)
def _stash_pre_save_state(sender, instance, **kwargs):
    """Stash the pre-save published_at and status so post_save can detect
    transitions. Stored on the instance (not DB) so it survives only the
    duration of this save() cycle."""
    if instance.pk:
        try:
            db_obj = sender.objects.get(pk=instance.pk)
            instance._memoriam_pre_save_published_at = db_obj.published_at
            instance._memoriam_pre_save_status = db_obj.status
        except sender.DoesNotExist:
            instance._memoriam_pre_save_published_at = None
            instance._memoriam_pre_save_status = None
    else:
        instance._memoriam_pre_save_published_at = None
        instance._memoriam_pre_save_status = None


@receiver(post_save, sender=InMemoriamEntry)
def _audit_publish_or_archive(sender, instance, created, **kwargs):
    pre_pub = getattr(instance, "_memoriam_pre_save_published_at", None)
    pre_status = getattr(instance, "_memoriam_pre_save_status", None)

    # Publish: published_at was None pre-save and is now set.
    if pre_pub is None and instance.published_at is not None:
        AuditLog.objects.create(
            actor=_actor_for(instance),
            action="memoriam.entry.published",
            target_type="memoriam.InMemoriamEntry",
            target_id=str(instance.pk),
            metadata={
                "full_name": instance.full_name,
                "version": instance.approved_content_version,
            },
        )

    # Archive: status transitioned to 'archived' from something else.
    if instance.status == "archived" and pre_status != "archived":
        AuditLog.objects.create(
            actor=_actor_for(instance),
            action="memoriam.entry.archived",
            target_type="memoriam.InMemoriamEntry",
            target_id=str(instance.pk),
            metadata={"full_name": instance.full_name},
        )


@receiver(post_save, sender=InMemoriamNomination)
def _audit_nomination_created(sender, instance, created, **kwargs):
    if not created:
        return
    AuditLog.objects.create(
        actor=instance.nominator.user if instance.nominator_id else None,
        action="memoriam.nomination.created",
        target_type="memoriam.InMemoriamNomination",
        target_id=str(instance.pk),
        metadata={
            "proposed_name": instance.proposed_name,
            "nominator_id": instance.nominator_id,
            # CLAUDE.md: metadata always carries a human-readable name, so the
            # row still means something after the nominator is renamed or purged.
            "nominator_full_name": (
                f"{instance.nominator.first_name} {instance.nominator.last_name}".strip()
                if instance.nominator_id
                else ""
            ),
        },
    )
