"""Signal handlers for the membership app.

These hooks intentionally use signals (not explicit calls in admin /
service code) so the audit trail is automatic — adding a new way to
sign off or remove an entry doesn't require remembering to write to
AuditLog. The cost: signal handlers are easy to miss when grepping;
each handler has an explicit comment naming the audit hook.
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_save, pre_delete
from django.dispatch import receiver

from .models import AuditLog, Member, NotificationPreference, PublicSearchEntry, RemovalRequest


@receiver(post_save, sender=Member)
def create_preferences_for_new_member(sender, instance, created, **kwargs):
    """Existing P2 hook — auto-create NotificationPreference for new Members."""
    if created:
        NotificationPreference.objects.create(member=instance)


@receiver(post_save, sender=PublicSearchEntry)
def _audit_entry_created(sender, instance, created, **kwargs):
    """Audit hook for PublicSearchEntry creation."""
    if created:
        AuditLog.objects.create(
            actor=None,
            action="ghost.entry.created",
            target_type="members.PublicSearchEntry",
            target_id=str(instance.pk),
            metadata={
                "first_name": instance.first_name,
                "last_name_initial": instance.last_name_initial,
            },
        )


@receiver(m2m_changed, sender=PublicSearchEntry.added_by_admins.through)
def _audit_signoff_change(sender, instance, action, pk_set, **kwargs):
    """Audit hook for ghost-entry signoffs. Fires post_add and post_remove."""
    if action not in ("post_add", "post_remove"):
        return
    audit_action = (
        "ghost.entry.signed_off" if action == "post_add" else "ghost.entry.signoff_removed"
    )
    User = get_user_model()  # noqa: N806
    for admin_pk in pk_set or ():
        admin = User.objects.filter(pk=admin_pk).only("pk", "email").first()
        AuditLog.objects.create(
            actor=admin,
            action=audit_action,
            target_type="members.PublicSearchEntry",
            target_id=str(instance.pk),
            metadata={
                "signer_pk": admin_pk,
                "signer_email": admin.email if admin else "",
                "signoff_count_after": instance.added_by_admins.count(),
            },
        )


@receiver(pre_delete, sender=RemovalRequest)
def _audit_removal_request_cancelled(sender, instance, **kwargs):
    """Audit hook for admin-cancellation of a pending RemovalRequest.

    Only fires when status is still 'pending_confirmation'. Confirmed and
    expired requests have their history in the existing
    'requested'/'confirmed'/'executed' chain.
    """
    if instance.status != "pending_confirmation":
        return
    AuditLog.objects.create(
        actor=None,
        action="ghost.removal.cancelled",
        target_type="members.RemovalRequest",
        target_id=str(instance.pk),
        metadata={
            "entry_pk": instance.entry_id,
            "requester_email": instance.requester_email,
            "reason": instance.reason,
        },
    )
