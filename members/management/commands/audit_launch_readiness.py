"""Pre-launch sanity check (P7).

Prints current counts vs master-spec minimums and flags anything below
threshold. Pure informational; never mutates. Run this before
announcing the platform widely.

    python manage.py audit_launch_readiness
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print launch-readiness counts vs master-spec minimums. Read-only."

    def handle(self, *args, **options):
        from members.models import Member, PublicSearchEntry
        from memoires.models import Memory
        from memoriam.models import InMemoriamEntry

        member_count = Member.objects.filter(status="active").count()
        memory_count = Memory.objects.filter(status="published").count()
        memoriam_count = InMemoriamEntry.objects.filter(status="published").count()
        ghost_count = (
            PublicSearchEntry.objects.filter(removed_at__isnull=True)
            .filter(added_by_admins__isnull=False)
            .distinct()
            .count()
        )

        rows = [
            ("Active members", member_count, 1, "import the WhatsApp roster"),
            (
                "Memory rows (Mur des souvenirs)",
                memory_count,
                10,
                "admin uploads via /admin/memoires/memory/",
            ),
            (
                "InMemoriamEntry published",
                memoriam_count,
                1,
                "admin creates via /admin/memoriam/inmemoriamentry/",
            ),
            (
                "PublicSearchEntry published",
                ghost_count,
                3,
                "admin adds via /admin/members/publicsearchentry/",
            ),
        ]

        self.stdout.write("Launch-readiness audit")
        self.stdout.write("=" * 60)
        below = 0
        for label, current, target, action in rows:
            mark = "✓" if current >= target else "⚠"
            if current < target:
                below += 1
            self.stdout.write(
                f"  {mark}  {label:40s}  {current:>3} (target ≥{target})",
            )
            if current < target:
                self.stdout.write(f"        action: {action}")

        self.stdout.write("")
        self.stdout.write("Manual checks (not enforced here, see runbooks):")
        self.stdout.write("  - DMARC TXT record present (docs/runbooks/dmarc.md §1.2)")
        self.stdout.write("  - BASIC_AUTH_REQUIRED=false on lesretrouvailles service")
        self.stdout.write("  - Last `backup_media` cron run successful (< 8 days ago)")
        self.stdout.write("  - audit_launch_readiness re-run after roster import")

        if below:
            self.stdout.write("")
            self.stdout.write(f"{below} item(s) below threshold. Address before announcing.")
        else:
            self.stdout.write("")
            self.stdout.write("All threshold checks passed.")
