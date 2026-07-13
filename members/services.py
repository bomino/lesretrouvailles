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
import hmac
import logging
from typing import Any

from django.db import transaction

from alumni import cloudinary as cloud_mod
from alumni import storage as storage_mod
from members.models import AuditLog, ClassRosterEntry, Member

logger = logging.getLogger(__name__)


class ClaimRefused(Exception):  # noqa: N818 — semantically a refusal, not an error
    """A member may not claim this class-roster entry."""


def _name_tokens(*parts: str) -> set[str]:
    """Accent- and case-insensitive token set, for name comparison."""
    import unicodedata

    text = " ".join(p for p in parts if p)
    folded = unicodedata.normalize("NFD", text.casefold())
    stripped = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    return {t for t in stripped.split() if t}


def can_claim(entry: ClassRosterEntry, member: Member) -> bool:
    """Does `member`'s name identify them as this roster entry?

    Requires **two** matching name tokens, not one.

    One shared token was a security review finding, and rightly: "Moussa
    Issoufou" could claim "Moussa Harouna" purely because both are Moussa. In a
    Sahelian cohort, given names (Moussa, Mariama, Ibrahim, Zeinabou) repeat
    constantly — one shared token is a coincidence, not an identity. Two is a
    person.

    Consequences, both deliberate:
      * A roster row with ONLY a given name (20 of them) can never be
        self-claimed. It identifies nobody, so an admin must make the link.
      * A member whose registered surname differs entirely from the roster
        (marriage, a transcription that dropped a name) is sent to an admin.
        That is the right failure direction: a claim is an identity assertion,
        and an over-eager one is worse than a manual step.

    Nicknames count as a token because surnoms are strong identifiers in this
    community — « Bomino » is exactly one person.

    Still not a wall: every claim is audited with both names and staff can
    unlink anything. But it is no longer a speed bump either.
    """
    entry_tokens = _name_tokens(entry.first_name, entry.last_name, entry.nickname)
    member_tokens = _name_tokens(member.first_name, member.last_name, member.nickname)
    return len(entry_tokens & member_tokens) >= 2


@transaction.atomic
def claim_entry(entry: ClassRosterEntry, *, member: Member, actor) -> ClassRosterEntry:
    """Link a roster entry to the member who says it is them.

    select_for_update: two concurrent claims on the same row would otherwise
    both pass the "already claimed?" check and the last writer would win
    silently. Lock the row for the duration.
    """
    entry = ClassRosterEntry.objects.select_for_update().get(pk=entry.pk)

    if entry.member_id == member.pk:
        return entry  # idempotent
    if entry.member_id is not None:
        raise ClaimRefused("Cette fiche est déjà revendiquée par un autre membre.")
    if not can_claim(entry, member):
        raise ClaimRefused(
            "Ce nom ne correspond pas au vôtre. Demandez à un administrateur de faire le lien."
        )

    # A pupil sits in ONE class per school year. Claiming a second entry for the
    # same year is either a mistake or someone hoovering up identities. Claiming
    # one entry in 1980 AND one in 1981 is legitimate — that is a repeated 6ème,
    # and 12 people in these rosters did exactly that.
    already = ClassRosterEntry.objects.filter(
        member=member,
        school_year_start=entry.school_year_start,
    ).exclude(pk=entry.pk)
    if already.exists():
        raise ClaimRefused(
            "Vous avez déjà revendiqué une fiche pour l'année "
            f"{entry.school_year_label}. Demandez à un administrateur si c'est une erreur."
        )

    entry.member = member
    entry.save(update_fields=["member", "updated_at"])
    AuditLog.objects.create(
        actor=actor,
        action="promotions.entry.claimed",
        target_type="members.ClassRosterEntry",
        target_id=str(entry.pk),
        metadata={
            "member_full_name": member.full_name,
            "entry_full_name": entry.full_name,
            "class_label": entry.class_label,
            "school_year_start": entry.school_year_start,
        },
    )
    return entry


@transaction.atomic
def unclaim_entry(entry: ClassRosterEntry, *, member: Member, actor) -> ClassRosterEntry:
    """Unlink. Only the claimer, or staff, may do this."""
    if entry.member_id is None:
        return entry  # idempotent
    is_staff = bool(getattr(actor, "is_staff", False))
    if entry.member_id != member.pk and not is_staff:
        raise ClaimRefused("Cette fiche est revendiquée par un autre membre.")

    previous = entry.member
    entry.member = None
    entry.save(update_fields=["member", "updated_at"])
    AuditLog.objects.create(
        actor=actor,
        action="promotions.entry.unclaimed",
        target_type="members.ClassRosterEntry",
        target_id=str(entry.pk),
        metadata={
            "member_full_name": previous.full_name if previous else "",
            "entry_full_name": entry.full_name,
            "class_label": entry.class_label,
        },
    )
    return entry


class PurgeIncomplete(Exception):  # noqa: N818 — a refusal to proceed, not a crash
    """External (Cloudinary / bucket) deletion failed, so nothing was purged.

    Raised BEFORE any DB mutation. Retrying is safe and expected: both external
    deletes are idempotent, and no row has been touched. The alternative — the
    old behavior — was to log a warning, delete the DB identity anyway, and
    write `rgpd.member.purged`: the media stays live while the only record of
    who owned it is destroyed.
    """


class PurgeRefused(Exception):  # noqa: N818 — semantically a refusal, not an error
    """Precondition violation that blocks a clean cascade.

    Distinct from operational errors so callers (CLI, admin action) can
    render a friendly message instead of a stack trace. Named without an
    `Error` suffix on purpose — it signals "the operation was refused,"
    not "something went wrong" (cf. stdlib `StopIteration`).
    """


def _audit_email_hash(email: str) -> str:
    """A correlation reference for the purge audit row — not a stored email.

    Was `sha1(email)[:12]`, which is dictionary-reversible: this is a ~200-person
    community, so an attacker simply hashes every plausible address and matches.
    That turned the "anonymous" audit trail into a lookup table.

    HMAC-SHA256 keyed with SECRET_KEY: still stable (the same member always maps
    to the same reference, so a purge can be correlated across audit rows) but
    not reversible without the key.
    """
    from django.conf import settings as django_settings

    return hmac.new(
        django_settings.SECRET_KEY.encode("utf-8"),
        email.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]


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
    """Cloudinary public_ids that are the MEMBER'S OWN personal data.

    Their profile photo, and nothing else. Memories they uploaded to the Mur des
    souvenirs are deliberately excluded: those are photos OF the community, not
    personal data OF the uploader, and deleting them would erase shared history
    because the person who happened to upload it exercised their erasure right
    (F-06). The rows survive with `created_by` nulled — see the purge below.

    Residual, and it is a real one: if a retained photo *depicts* the purged
    person, an admin must remove it by hand. The purge summary says so.
    """
    public_ids: set[str] = set()
    if member.photo_public_id:
        public_ids.add(member.photo_public_id)
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
    email_hash = _audit_email_hash(member.user.email)

    # Pre-count for the dry-run summary
    memory_count = Memory.objects.filter(created_by=member.user).count()
    cooptation_count = CooptationRequest.objects.filter(parrain=member).count()
    nomination_count = InMemoriamNomination.objects.filter(nominator=member).count()
    # Email-less members (~80% of the audience) have `user.email == ""`. A
    # naked `email__iexact=""` filter would match every blank-email
    # AdminApplication in the DB and anonymize them — unrelated rows.
    # Guard the lookup so the purge stays scoped to this member's data.
    if member.user.email:
        application_count = (
            AdminApplication.objects.filter(
                email__iexact=member.user.email,
            )
            .exclude(status="purged")
            .count()
        )
    else:
        application_count = 0

    # Claimed Promotions rows carry the member's full name. They cascade with
    # the Member (ClassRosterEntry.member is on_delete=CASCADE) — count them so
    # the summary tells the truth about what the purge erased. A purge that
    # leaves the person's name in the class archive is not a purge.
    roster_count = ClassRosterEntry.objects.filter(member=member).count()

    deleted_counts = {
        "memories_anonymized": memory_count,
        "cooptation_requests": cooptation_count,
        "memoriam_nominations": nomination_count,
        "admin_applications_anonymized": application_count,
        "roster_entries": roster_count,
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
    failures: list[str] = []
    for pid in public_ids:
        try:
            cloud.delete(pid)
        except Exception as e:  # noqa: BLE001 — collected, then raised below
            logger.warning("rgpd_purge: cloudinary delete failed for %s — %s", pid, e)
            failures.append(f"cloudinary:{pid} ({e})")
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
                failures.append(f"bucket:{version.get('path')}/{version.get('file_id')} ({e})")

    # ABORT before touching the DB. These failures used to be swallowed: the
    # media stayed live on Cloudinary, the DB identity was deleted anyway, and
    # `rgpd.member.purged` was written as if it had all worked. That is the worst
    # outcome available — the photo is still served, and the only record of which
    # public_id belonged to whom is gone, so nobody can ever clean it up.
    #
    # Aborting here is safe to retry: Cloudinary's destroy and the bucket's
    # delete_version are both idempotent, and no DB row has been touched yet
    # (external calls deliberately run BEFORE the transaction).
    if failures:
        raise PurgeIncomplete(
            f"{len(failures)} external deletion(s) failed; nothing was purged. "
            "Fix the cause and re-run — the operation is idempotent. "
            f"Failures: {'; '.join(failures[:5])}"
        )

    deleted_counts["bucket_versions"] = bucket_versions_deleted

    # --- Steps 5-8: DB mutations in a single transaction -------------------
    with transaction.atomic():
        # Step 5: hard-delete PROTECT-blocking dependents
        CooptationRequest.objects.filter(parrain=member).delete()
        InMemoriamNomination.objects.filter(nominator=member).delete()

        # Step 6: keep the community's memories, drop the link to the person.
        # These are photos OF the community (Mur des souvenirs, admin-curated),
        # not personal data OF the uploader. Hard-deleting them meant a purged
        # co-admin took the shared gallery down with them (F-06). The Cloudinary
        # assets are likewise retained — see _collect_public_ids.
        Memory.objects.filter(created_by=member.user).update(created_by=None)

        # Step 7: anonymize prior AdminApplications (calls .purge() each).
        # Skip entirely when the member has no email — see the pre-count
        # guard above for the rationale (`email__iexact=""` would match
        # every blank-email row in the DB).
        if member.user.email:
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
