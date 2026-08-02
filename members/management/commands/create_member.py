"""Dev/test helper to create a User + Member without going through cooptation."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from members.models import Member, NotificationPreference


class Command(BaseCommand):
    help = "Create a Member (and the underlying User) for dev/test."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", required=True)
        parser.add_argument("--last-name", required=True)
        parser.add_argument("--years", nargs="+", type=int, required=True)
        parser.add_argument("--classes", nargs="+", required=True)
        parser.add_argument("--city", required=True)
        parser.add_argument("--country", default="Niger")
        parser.add_argument("--nickname", default="")
        parser.add_argument("--profession", default="")
        parser.add_argument("--password", default=None)

    @transaction.atomic
    def handle(self, *args, **opts):
        user_model = get_user_model()
        email = opts["email"]
        # filter().first(), not get_or_create: email is NOT unique on User,
        # so two accounts sharing an address raised MultipleObjectsReturned.
        # Attach to the oldest account, matching the resend-action convention.
        user = user_model.objects.filter(email=email).order_by("pk").first()
        created = False
        if user is None:
            user = user_model.objects.create(username=email, email=email)
            created = True
        if opts["password"]:
            user.set_password(opts["password"])
        elif created:
            user.set_unusable_password()
        user.save()

        defaults = {
            "first_name": opts["first_name"],
            "last_name": opts["last_name"],
            "nickname": opts["nickname"],
            "years_attended": opts["years"],
            "classes": opts["classes"],
            "city": opts["city"],
            "country": opts["country"],
            "profession": opts["profession"],
        }
        member, _ = Member.objects.update_or_create(user=user, defaults=defaults)
        try:
            member.full_clean()
        except ValidationError as e:
            # Runs after update_or_create persisted, so @transaction.atomic
            # (via the CommandError) is what actually rolls the write back.
            raise CommandError(str(e)) from None

        # Ensure NotificationPreference exists
        NotificationPreference.objects.get_or_create(member=member)

        self.stdout.write(self.style.SUCCESS(f"Member created/updated: {member.full_name}"))
