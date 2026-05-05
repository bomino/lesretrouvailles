"""Bulk-import the existing WhatsApp roster onto Les Retrouvailles (P7).

Usage:
    python manage.py import_whatsapp_roster roster.csv [options]

CSV columns (header required, exact names):
    first_name, last_name, nickname, whatsapp, email,
    years_attended, classes, city, country, profession, photo_filename

- whatsapp is required; phone digits become User.username
- email is optional; ~80% of the cohort doesn't have one
- photo_filename is optional; references a file inside --photos-dir
- years_attended and classes are comma-separated, in quotes

Behavior:
- Email present  -> standard Allauth password-set email via Resend
- Email blank    -> magic-link URL written to --magic-links-out CSV;
                    operator copy-pastes into a WhatsApp DM

See docs/runbooks/onboarding.md for the full operator procedure.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cooptation.services import _build_password_set_url
from members.models import VALID_CLASS_PATTERN, VALID_YEARS, Member

User = get_user_model()

PHONE_RE = re.compile(r"\+?\d{8,15}")


def _digits_only(phone: str) -> str:
    """Strip leading + and all non-digits. Used to derive User.username."""
    return re.sub(r"\D", "", phone or "")


def _parse_int_list(raw: str) -> list[int]:
    return [int(s.strip()) for s in (raw or "").split(",") if s.strip()]


def _parse_str_list(raw: str) -> list[str]:
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def _validate_row(row: dict, line_no: int) -> list[str]:
    """Return a list of human-readable errors for the row. Empty = OK."""
    errors: list[str] = []
    if not row.get("first_name", "").strip():
        errors.append("first_name is required")
    if not row.get("last_name", "").strip():
        errors.append("last_name is required")
    phone = row.get("whatsapp", "").strip()
    if not phone:
        errors.append("whatsapp is required")
    elif not PHONE_RE.fullmatch(phone):
        errors.append(f"whatsapp '{phone}' is not a valid phone number")
    if not row.get("city", "").strip():
        errors.append("city is required")
    try:
        years = _parse_int_list(row.get("years_attended", ""))
        if not years:
            errors.append("years_attended is required (comma-separated, in quotes)")
        else:
            bad = [y for y in years if y not in VALID_YEARS]
            if bad:
                errors.append(f"years_attended {bad!r} outside 1980-1985")
    except ValueError:
        errors.append("years_attended must be integers, comma-separated")

    classes = _parse_str_list(row.get("classes", ""))
    if not classes:
        errors.append("classes is required (comma-separated, in quotes)")
    else:
        bad_classes = [c for c in classes if not VALID_CLASS_PATTERN.match(c)]
        if bad_classes:
            errors.append(
                f"classes {bad_classes!r} don't match pattern (e.g. 6e, 5eA, 4eb)",
            )
    return errors


class Command(BaseCommand):
    help = "Bulk-import the WhatsApp roster from a CSV. See module docstring."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the roster CSV file.")
        parser.add_argument(
            "--photos-dir",
            default=None,
            help="Directory containing photo files referenced by photo_filename.",
        )
        parser.add_argument(
            "--magic-links-out",
            required=True,
            help="Where to write the magic-links CSV for no-email rows.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report; make no changes; send no emails.",
        )
        parser.add_argument(
            "--no-emails",
            action="store_true",
            help="Create accounts but skip the password-set emails (use later batch send).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process only the first N valid rows.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        photos_dir = Path(options["photos_dir"]) if options["photos_dir"] else None
        magic_links_path = Path(options["magic_links_out"])
        dry_run = options["dry_run"]
        no_emails = options["no_emails"]
        limit = options["limit"]

        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))

        # --- Validation pass -----------------------------------------------
        valid_rows: list[dict] = []
        errors: list[tuple[int, str, list[str]]] = []
        for i, row in enumerate(rows, start=2):  # line 1 is header
            row_errors = _validate_row(row, i)
            if row_errors:
                errors.append((i, row.get("whatsapp", "?"), row_errors))
            else:
                valid_rows.append(row)

        if limit:
            valid_rows = valid_rows[:limit]

        # --- Output planning summary ---------------------------------------
        header = "DRY RUN — would import:" if dry_run else "Import plan:"
        self.stdout.write(header)
        self.stdout.write(f"  rows read:      {len(rows)}")
        self.stdout.write(f"  valid:          {len(valid_rows)}")
        self.stdout.write(f"  errors:         {len(errors)}")
        if errors:
            self.stdout.write("  errors:")
            for line_no, phone, msgs in errors[:20]:
                for m in msgs:
                    self.stdout.write(f"    line {line_no} ({phone}): {m}")
            if len(errors) > 20:
                self.stdout.write(f"    ... and {len(errors) - 20} more")

        if dry_run:
            self.stdout.write("\nDRY RUN complete. Re-run without --dry-run to import.")
            return

        # --- Execute --------------------------------------------------------
        created = skipped = photos_uploaded = emails_sent = magic_link_count = 0
        magic_links_rows: list[dict] = []

        for row in valid_rows:
            phone = row["whatsapp"].strip()
            username = _digits_only(phone)
            if User.objects.filter(username=username).exists():
                skipped += 1
                self.stdout.write(f"  SKIP {phone}: already exists")
                continue

            try:
                with transaction.atomic():
                    user, member = self._create_user_and_member(row, username)
                    if photos_dir and row.get("photo_filename"):
                        if self._upload_photo(member, photos_dir, row["photo_filename"]):
                            photos_uploaded += 1
                created += 1
            except Exception as e:  # noqa: BLE001
                self.stderr.write(f"  ERROR {phone}: {e}")
                continue

            password_set_url = _build_password_set_url(user)
            email = (row.get("email") or "").strip()

            if email and not no_emails:
                self._send_welcome_email(member, password_set_url, email)
                emails_sent += 1
            elif not email:
                magic_links_rows.append(
                    {
                        "whatsapp": phone,
                        "full_name": member.full_name,
                        "magic_link_url": password_set_url,
                    },
                )
                magic_link_count += 1

        # --- Write magic_links.csv -----------------------------------------
        if magic_links_rows:
            magic_links_path.parent.mkdir(parents=True, exist_ok=True)
            with magic_links_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["whatsapp", "full_name", "magic_link_url"],
                )
                writer.writeheader()
                for r in magic_links_rows:
                    writer.writerow(r)

        # --- Final summary --------------------------------------------------
        self.stdout.write("")
        self.stdout.write(f"  {created} created, {skipped} skipped, {len(errors)} errors")
        self.stdout.write(f"  {emails_sent} password-set emails sent")
        self.stdout.write(f"  {magic_link_count} magic-link URLs in {magic_links_path}")
        self.stdout.write(f"  {photos_uploaded} photos uploaded")

        if magic_link_count:
            self.stdout.write(
                "\nNext step: open the magic-links CSV and DM each URL to "
                "the corresponding member via WhatsApp.",
            )

        # Non-zero exit if some rows had errors AND nothing was created
        if errors and created == 0:
            sys.exit(1)

    def _create_user_and_member(self, row, username):
        """Create User and Member from one validated row. Returns (user, member)."""
        email = (row.get("email") or "").strip()
        user = User.objects.create(
            username=username,
            email=email,
            first_name=row["first_name"].strip(),
            last_name=row["last_name"].strip(),
        )
        user.set_unusable_password()
        user.save()
        if email:
            from allauth.account.models import EmailAddress

            EmailAddress.objects.get_or_create(
                user=user,
                email=email,
                defaults={"verified": False, "primary": True},
            )

        member = Member.objects.create(
            user=user,
            first_name=row["first_name"].strip(),
            last_name=row["last_name"].strip(),
            nickname=row.get("nickname", "").strip(),
            years_attended=_parse_int_list(row["years_attended"]),
            classes=_parse_str_list(row["classes"]),
            city=row["city"].strip(),
            country=row.get("country", "").strip() or "Niger",
            profession=row.get("profession", "").strip(),
            status="active",
        )
        return user, member

    def _upload_photo(self, member, photos_dir: Path, filename: str) -> bool:
        """Upload one photo to Cloudinary; set member.photo_public_id. Returns True on success."""
        path = photos_dir / filename
        if not path.exists():
            self.stderr.write(
                f"  WARN {member.user.username}: photo {filename!r} not found in {photos_dir}",
            )
            return False
        try:
            from alumni import cloudinary as cloud_mod

            cloud = cloud_mod.get_client()
            with path.open("rb") as fh:
                public_id = cloud.upload_file(fh, folder=f"members/{member.slug}")
            member.photo_public_id = public_id
            member.save(update_fields=["photo_public_id"])
            return True
        except Exception as e:  # noqa: BLE001
            self.stderr.write(
                f"  WARN {member.user.username}: photo upload failed — {e}",
            )
            return False

    def _send_welcome_email(self, member, password_set_url, email):
        """Send the French welcome email with the password-set URL."""
        from alumni.email import send_email

        send_email(
            email,
            "members/welcome_imported",
            {"full_name": member.full_name, "password_set_url": password_set_url},
        )
