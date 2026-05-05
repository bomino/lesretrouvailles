"""Member-level service operations.

P6b adds rgpd_purge_member() — hard-deletes a member's PII end-to-end
(DB + Cloudinary + Tigris bucket + cross-domain references) in one
auditable operation. See:
    docs/superpowers/specs/2026-05-05-rgpd-admin-purge-design.md
    docs/runbooks/rgpd-purge.md

Future PROTECT-bound models tied to Member or User must extend
_collect_blockers() below or risk being silently cascaded.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from django.db import transaction

from alumni import cloudinary as cloud_mod
from alumni import storage as storage_mod
from members.models import AuditLog, Member

logger = logging.getLogger(__name__)


class PurgeRefused(Exception):  # noqa: N818 — semantically a refusal, not an error
    """Precondition violation that blocks a clean cascade.

    Distinct from operational errors so callers (CLI, admin action) can
    render a friendly message instead of a stack trace. Named without an
    `Error` suffix on purpose — it signals "the operation was refused,"
    not "something went wrong" (cf. stdlib `StopIteration`).
    """


def _collect_blockers(member: Member) -> list[str]:
    """Return human-readable reasons we cannot proceed. Empty list = OK."""
    from memoriam.models import InMemoriamEntry

    blockers: list[str] = []

    # PROTECT FK from InMemoriamEntry.created_by → User. Cascading via
    # member.user.delete() would raise IntegrityError. Force the operator
    # to reassign manually rather than fail mid-cascade.
    fiche_count = InMemoriamEntry.objects.filter(created_by=member.user).count()
    if fiche_count:
        blockers.append(
            f"Member has created {fiche_count} In Memoriam fiche(s). "
            "Reassign created_by manually (Django admin → In Memoriam) or delete "
            "those fiches before purging this member."
        )
    return blockers


def _collect_public_ids(member: Member) -> set[str]:
    """All Cloudinary public_ids tied to this member (profile + authored memories)."""
    from memoires.models import Memory

    public_ids: set[str] = set()
    if member.photo_public_id:
        public_ids.add(member.photo_public_id)
    public_ids.update(
        Memory.objects.filter(created_by=member.user)
        .exclude(photo_public_id="")
        .values_list("photo_public_id", flat=True),
    )
    return public_ids


def rgpd_purge_member(
    member: Member,
    *,
    actor: Any | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Hard-purge a member's PII end-to-end.

    Returns a structured summary. Raises PurgeRefused on precondition
    violations (created In Memoriam fiches, self-purge attempt). Other
    errors propagate.

    Order of operations is load-bearing — see spec §C. External calls
    (Cloudinary, bucket) happen BEFORE the DB transaction so a transient
    network failure doesn't leave half-deleted DB state. The AuditLog
    entry is the LAST step; its presence is the signal of full success.
    """
    from cooptation.models import AdminApplication, CooptationRequest
    from memoires.models import Memory
    from memoriam.models import InMemoriamNomination

    # --- Step 1: pre-flight refusals ---------------------------------------
    if actor is not None and getattr(actor, "id", None) == member.user_id:
        raise PurgeRefused("Cannot purge yourself. Ask another admin.")

    blockers = _collect_blockers(member)
    if blockers:
        raise PurgeRefused(" ".join(blockers))

    # --- Step 2: collect external-system targets ---------------------------
    public_ids = _collect_public_ids(member)

    cloud = cloud_mod.get_client()
    storage = storage_mod.get_client()

    member_id = member.id
    email_hash = hashlib.sha1(member.user.email.encode("utf-8")).hexdigest()[:12]

    # Pre-count for the dry-run summary
    memory_count = Memory.objects.filter(created_by=member.user).count()
    cooptation_count = CooptationRequest.objects.filter(parrain=member).count()
    nomination_count = InMemoriamNomination.objects.filter(nominator=member).count()
    application_count = (
        AdminApplication.objects.filter(
            email__iexact=member.user.email,
        )
        .exclude(status="purged")
        .count()
    )

    deleted_counts = {
        "memories": memory_count,
        "cooptation_requests": cooptation_count,
        "memoriam_nominations": nomination_count,
        "admin_applications_anonymized": application_count,
        "cloudinary_public_ids": len(public_ids),
        "bucket_versions": 0,  # filled in below if not dry_run
    }

    if dry_run:
        return {
            "member_id": member_id,
            "email_hash": email_hash,
            "deleted_counts": deleted_counts,
            "audit_log_id": None,
            "dry_run": True,
        }

    # --- Step 3 + 4: external systems first --------------------------------
    bucket_versions_deleted = 0
    for pid in public_ids:
        try:
            cloud.delete(pid)
        except Exception as e:  # noqa: BLE001 — best-effort; log and continue
            logger.warning("rgpd_purge: cloudinary delete failed for %s — %s", pid, e)
        for version in storage.list_versions(prefix=pid):
            try:
                storage.delete_version(version["path"], version["file_id"])
                bucket_versions_deleted += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "rgpd_purge: bucket delete_version failed for %s/%s — %s",
                    version.get("path"),
                    version.get("file_id"),
                    e,
                )

    deleted_counts["bucket_versions"] = bucket_versions_deleted

    # --- Steps 5-8: DB mutations in a single transaction -------------------
    with transaction.atomic():
        # Step 5: hard-delete PROTECT-blocking dependents
        CooptationRequest.objects.filter(parrain=member).delete()
        InMemoriamNomination.objects.filter(nominator=member).delete()

        # Step 6: hard-delete authored memories
        Memory.objects.filter(created_by=member.user).delete()

        # Step 7: anonymize prior AdminApplications (calls .purge() each)
        for app in AdminApplication.objects.filter(
            email__iexact=member.user.email,
        ).exclude(status="purged"):
            app.purge()

        # Step 8: cascade-delete via the User row (sweeps Member, prefs,
        # consent records, sessions; SET_NULLs the audit-log actor refs)
        user = member.user
        user.delete()

    # --- Step 9: audit (after commit so its presence == "fully complete") --
    audit = AuditLog.objects.create(
        actor=actor,
        action="rgpd.member.purged",
        target_type="Member",
        target_id=str(member_id),
        metadata={
            "email_hash": email_hash,
            "deleted_counts": deleted_counts,
        },
    )

    logger.info(
        "rgpd_purge: member_id=%s purged by actor=%s", member_id, getattr(actor, "id", None)
    )

    return {
        "member_id": member_id,
        "email_hash": email_hash,
        "deleted_counts": deleted_counts,
        "audit_log_id": audit.id,
        "dry_run": False,
    }
