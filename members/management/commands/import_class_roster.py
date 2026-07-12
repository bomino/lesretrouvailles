"""Import the historical class rosters into the Promotions archive.

    python manage.py import_class_roster private-data/class_rosters.csv --dry-run
    python manage.py import_class_roster private-data/class_rosters.csv

The CSV is produced by `scripts/convert_class_rosters.py` from the .xlsx
workbooks. Neither the workbooks nor the CSV are ever committed — they hold
the real names of ~335 living alumni and this repo is public (see .gitignore).

Idempotent on `source_ref` ("80-81:6eA:12"), so a re-run updates in place and
never duplicates. Keying on the name instead would be wrong: 20 source rows
have a blank surname, so two genuinely different people could collide.

To run against production, execute locally with prod settings and the PUBLIC
database URL — the internal DATABASE_URL host does not resolve from your
machine. See docs/runbooks/launch.md for the exact procedure.
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from members.models import VALID_CLASS_PATTERN, VALID_YEARS, ClassRosterEntry

REQUIRED_COLUMNS = {
    "source_ref",
    "school_year_start",
    "class_label",
    "first_name",
}


class Command(BaseCommand):
    help = "Import class-roster entries (Promotions archive) from a CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the CSV from convert_class_rosters.py.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report; make no changes.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        dry_run = options["dry_run"]

        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))

        if not rows:
            raise CommandError(f"{csv_path} has no rows.")

        missing = REQUIRED_COLUMNS - set(rows[0])
        if missing:
            raise CommandError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")

        # --- Validate everything before touching the DB ---------------------
        errors: list[str] = []
        seen_refs: set[str] = set()
        cleaned: list[dict] = []

        for i, row in enumerate(rows, start=2):  # line 1 is the header
            ref = (row.get("source_ref") or "").strip()
            first = (row.get("first_name") or "").strip()
            label = (row.get("class_label") or "").strip()
            raw_year = (row.get("school_year_start") or "").strip()

            if not ref:
                errors.append(f"line {i}: source_ref is required")
                continue
            if ref in seen_refs:
                errors.append(f"line {i}: duplicate source_ref {ref!r}")
                continue
            seen_refs.add(ref)

            if not first:
                errors.append(f"line {i} ({ref}): first_name is required")
            if not VALID_CLASS_PATTERN.match(label):
                errors.append(f"line {i} ({ref}): class_label {label!r} is not a valid class")
            try:
                year = int(raw_year)
            except ValueError:
                errors.append(f"line {i} ({ref}): school_year_start {raw_year!r} is not an integer")
                continue
            if year not in VALID_YEARS:
                errors.append(f"line {i} ({ref}): school_year_start {year} outside 1980-1985")
                continue

            cleaned.append(
                {
                    "source_ref": ref,
                    "school_year_start": year,
                    "class_label": label,
                    "first_name": first,
                    "last_name": (row.get("last_name") or "").strip(),
                    "nickname": (row.get("nickname") or "").strip(),
                    "needs_review": bool((row.get("needs_review") or "").strip()),
                }
            )

        existing = set(
            ClassRosterEntry.objects.filter(source_ref__in=seen_refs).values_list(
                "source_ref", flat=True
            )
        )

        header = "DRY RUN — would import:" if dry_run else "Import plan:"
        self.stdout.write(header)
        self.stdout.write(f"  rows read:      {len(rows)}")
        self.stdout.write(f"  valid:          {len(cleaned)}")
        self.stdout.write(f"  would create:   {len(cleaned) - len(existing)}")
        self.stdout.write(f"  would update:   {len(existing)}")
        self.stdout.write(f"  needs review:   {sum(1 for r in cleaned if r['needs_review'])}")
        self.stdout.write(f"  errors:         {len(errors)}")
        for message in errors[:20]:
            self.stdout.write(f"    {message}")
        if len(errors) > 20:
            self.stdout.write(f"    ... and {len(errors) - 20} more")

        if errors:
            raise CommandError("Fix the CSV and re-run; nothing was imported.")

        if dry_run:
            self.stdout.write("\nDRY RUN complete. Re-run without --dry-run to import.")
            return

        # --- Execute ---------------------------------------------------------
        created = updated = 0
        with transaction.atomic():
            for entry in cleaned:
                ref = entry.pop("source_ref")
                # update_or_create on source_ref: re-running is safe, and a
                # corrected name in the CSV propagates to the existing row.
                _, was_created = ClassRosterEntry.objects.update_or_create(
                    source_ref=ref,
                    defaults=entry,
                )
                created += was_created
                updated += not was_created

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"  {created} created, {updated} updated"))
        by_class = (
            ClassRosterEntry.objects.values("school_year_start", "class_label")
            .order_by("school_year_start", "class_label")
            .distinct()
        )
        self.stdout.write(f"  {len(by_class)} classes now in the Promotions archive")
