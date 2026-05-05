"""Re-issue an Allauth password-reset URL for a member who can't be emailed.

For members without email (~80% of the soft-launch cohort, P7), the
standard 'forgot password' email-reset flow doesn't work. They ping
the admin via WhatsApp; admin runs:

    python manage.py reissue_login_link <whatsapp-digits>

…and copy-pastes the printed URL into a WhatsApp DM to that member.
The URL is valid for 7 days (PASSWORD_RESET_TIMEOUT in settings).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from cooptation.services import _build_password_set_url

User = get_user_model()


class Command(BaseCommand):
    help = "Re-issue a one-time login URL for a member identified by username (= WhatsApp digits)."

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            help="The member's WhatsApp digits-only number (their User.username).",
        )

    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(
                f"User with username={username!r} not found. "
                "Pass digits only (e.g. '22790000001', not '+22790000001').",
            ) from exc

        url = _build_password_set_url(user)
        self.stdout.write(f"Magic link for {username} ({user.first_name} {user.last_name}):")
        self.stdout.write(url)
        self.stdout.write(
            "\nCopy the URL above and DM it to the member via WhatsApp. Valid 7 days.",
        )
