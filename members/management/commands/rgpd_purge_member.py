"""CLI wrapper for the RGPD admin-purge service.

Usage:
    python manage.py rgpd_purge_member <email> [--dry-run] [--yes]
                                       [--member-id N] [--actor USER_ID]

See docs/runbooks/rgpd-purge.md and members/services.py for the engine.
"""

from __future__ import annotations

import json
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from members.models import Member
from members.services import PurgeRefused, rgpd_purge_member


def _format_summary(summary: dict, *, dry_run: bool) -> str:
    """Render the engine's summary dict for human reading."""
    counts = summary["deleted_counts"]
    header = "DRY RUN — would delete:" if dry_run else "Purge complete:"
    lines = [
        header,
        f"  member_id              : {summary['member_id']}",
        f"  email_hash             : {summary['email_hash']}",
        f"  memories               : {counts['memories']}",
        f"  cooptation_requests    : {counts['cooptation_requests']}",
        f"  memoriam_nominations   : {counts['memoriam_nominations']}",
        f"  admin_apps_anonymized  : {counts['admin_applications_anonymized']}",
        f"  cloudinary_public_ids  : {counts['cloudinary_public_ids']}",
        f"  bucket_versions        : {counts['bucket_versions']}",
    ]
    if not dry_run and summary.get("audit_log_id") is not None:
        lines.append(f"  audit_log_id           : {summary['audit_log_id']}")
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Hard-purge a member's PII (DB + Cloudinary + bucket + cross-domain refs). RGPD §17."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Email of the member to purge.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be deleted without making any changes.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the interactive confirmation prompt.",
        )
        parser.add_argument(
            "--member-id",
            type=int,
            default=None,
            help="Disambiguate when multiple members share the email.",
        )
        parser.add_argument(
            "--actor",
            type=int,
            default=None,
            help="User ID to record as the audit actor. Defaults to None (anonymous).",
        )

    def handle(self, *args, **options):
        email = options["email"]
        dry_run = options["dry_run"]
        skip_prompt = options["yes"]
        member_id = options["member_id"]
        actor_id = options["actor"]

        # --- Resolve the member ---------------------------------------------
        qs = Member.objects.filter(user__email__iexact=email)
        if member_id is not None:
            qs = qs.filter(id=member_id)

        members = list(qs)
        if not members:
            self.stdout.write(
                f"No member found with email {email!r}. Already purged?"
                + (f" (member_id={member_id})" if member_id else ""),
            )
            return  # idempotent: exit 0

        if len(members) > 1:
            ids = ", ".join(str(m.id) for m in members)
            self.stderr.write(
                f"Multiple members match {email!r}: ids=[{ids}]. "
                "Re-run with --member-id <N> to disambiguate.",
            )
            sys.exit(2)

        member = members[0]

        # --- Resolve the actor ---------------------------------------------
        actor = None
        if actor_id is not None:
            User = get_user_model()  # noqa: N806
            try:
                actor = User.objects.get(id=actor_id)
            except User.DoesNotExist:
                self.stderr.write(f"Actor user_id={actor_id} not found.")
                sys.exit(2)

        # --- Dry run path ---------------------------------------------------
        if dry_run:
            try:
                summary = rgpd_purge_member(member, actor=actor, dry_run=True)
            except PurgeRefused as e:
                self.stderr.write(f"REFUSED: {e}")
                sys.exit(1)
            self.stdout.write(_format_summary(summary, dry_run=True))
            return

        # --- Confirmation prompt -------------------------------------------
        if not skip_prompt:
            # Pre-render the plan so the operator sees what's about to happen
            try:
                plan = rgpd_purge_member(member, actor=actor, dry_run=True)
            except PurgeRefused as e:
                self.stderr.write(f"REFUSED: {e}")
                sys.exit(1)
            self.stdout.write(_format_summary(plan, dry_run=True))
            self.stdout.write("")
            answer = input(f"Purge member {email!r}? Type 'yes' to confirm: ").strip()
            if answer.lower() != "yes":
                self.stdout.write("Aborted.")
                return  # exit 0; not an error

        # --- Execute --------------------------------------------------------
        try:
            summary = rgpd_purge_member(member, actor=actor)
        except PurgeRefused as e:
            self.stderr.write(f"REFUSED: {e}")
            sys.exit(1)

        self.stdout.write(_format_summary(summary, dry_run=False))
        # JSON line for log scrapers / structured callers
        self.stdout.write(f"\nstructured: {json.dumps(summary)}")
