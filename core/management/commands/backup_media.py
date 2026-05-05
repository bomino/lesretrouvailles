"""Walk the DB for Cloudinary public_ids; mirror missing ones to object storage.

Designed to run weekly via the Railway media-backup-cron service. See
docs/superpowers/specs/2026-05-04-media-backup-design.md and
docs/runbooks/restore.md for the full operational picture.
"""

from __future__ import annotations

import logging
import sys

from django.core.management.base import BaseCommand

from alumni import cloudinary as cloud_mod
from alumni import storage as storage_mod

logger = logging.getLogger(__name__)


def _collect_photo_public_ids() -> list[str]:
    """Return a deduplicated, sorted list of photo_public_ids known to the DB.

    Hardcoded model list; see spec §B.2.1. Future phases adding a
    photo_public_id field must update this function.
    """
    from members.models import Member
    from memoires.models import Memory
    from memoriam.models import InMemoriamEntry

    sources = [
        Member.objects.exclude(photo_public_id="").values_list("photo_public_id", flat=True),
        Memory.objects.exclude(photo_public_id="").values_list("photo_public_id", flat=True),
        InMemoriamEntry.objects.exclude(photo_public_id="").values_list(
            "photo_public_id",
            flat=True,
        ),
    ]
    seen: set[str] = set()
    for qs in sources:
        seen.update(qs)
    return sorted(seen)


class Command(BaseCommand):
    help = "Mirror Cloudinary photos to the configured object storage. Run weekly via Railway cron."

    def handle(self, *args, **options):
        photo_ids = _collect_photo_public_ids()
        storage = storage_mod.get_client()
        cloud = cloud_mod.get_client()

        succeeded = skipped = failed = 0

        for public_id in photo_ids:
            storage_path = public_id  # 1:1 mirror — bucket key is the public_id verbatim
            try:
                if storage.head_file(storage_path) is not None:
                    skipped += 1
                    continue
                content = cloud.download(public_id)
                storage.upload_file(storage_path, content)
                succeeded += 1
            except Exception as e:  # noqa: BLE001 — broad on purpose; keep going on per-photo failures
                logger.warning("backup_media: failed %s — %s", public_id, e)
                failed += 1

        attempted = succeeded + failed
        if attempted == 0:
            self.stdout.write(
                f"backup_media: 0 attempted, {skipped} skipped (already backed up)",
            )
            return

        success_rate = succeeded / attempted
        self.stdout.write(
            f"backup_media: {succeeded} uploaded, {skipped} skipped, "
            f"{failed} failed (success rate {success_rate:.1%})",
        )
        if success_rate < 0.95:
            sys.exit(1)
