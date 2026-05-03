"""End-to-end smoke test of the cooptation pipeline against the live DB.

Idempotent: cleans up its own prior runs before starting. Designed to be run
from a Railway shell against staging:

    railway ssh
    python manage.py smoke_test_cooptation --candidate-email you@example.com

Sends real emails via the configured EMAIL_BACKEND. The candidate inbox
should receive: application_received, cooptation_requests_sent, and
application_approved (with a clickable allauth password-set link). The two
parrain invitations go to throwaway @example.test addresses and bounce
harmlessly — we accept them programmatically inside the command.

Pass --keep to leave the test records in place for inspection. Otherwise
the command tears everything down at the end so it doesn't pollute the
member directory.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from cooptation import emails, services
from cooptation.models import AdminApplication, CooptationRequest
from members.models import Member

SMOKE_PARRAIN_1_EMAIL = "smoke-test-parrain1@example.test"
SMOKE_PARRAIN_2_EMAIL = "smoke-test-parrain2@example.test"
SMOKE_TAG = "[smoke-test]"


class Command(BaseCommand):
    help = "End-to-end cooptation pipeline smoke test (sends real emails)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--candidate-email",
            required=True,
            help="Inbox you can read; receives application_received, "
            "cooptation_requests_sent, and application_approved emails.",
        )
        parser.add_argument(
            "--admin-email",
            default=None,
            help="Staff user email to record as reviewed_by. Defaults to the first staff user.",
        )
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Skip cleanup so you can inspect the records afterward.",
        )

    def handle(self, *args, **opts):
        candidate_email = opts["candidate_email"].strip().lower()
        admin_email = opts["admin_email"]
        keep = opts["keep"]

        self._step("0/6", "Pre-flight cleanup of any prior smoke-test data")
        self._cleanup(candidate_email)

        self._step("1/6", "Resolving / creating staff approver")
        staff_user = self._resolve_staff(admin_email)
        self.stdout.write(f"   staff: {staff_user.email}")

        self._step("2/6", "Seeding two parrain Members")
        p1, p2 = self._seed_parrains()
        self.stdout.write(f"   parrain1: {p1.user.email}")
        self.stdout.write(f"   parrain2: {p2.user.email}")

        self._step("3/6", f"Submitting candidate application for {candidate_email}")
        app, req1, req2 = self._submit_application(candidate_email, p1, p2)
        self.stdout.write(f"   application id={app.pk} status={app.status}")
        self.stdout.write("   sent: application_received, cooptation_requests_sent")
        self.stdout.write("   sent: parrain_invitation x2 (to @example.test, will bounce)")
        self.stdout.write("   sent: admin_new_application")

        self._step("4/6", "Programmatically accepting both parrain vouches")
        self._accept_vouches(req1, req2)
        app.refresh_from_db()
        self.stdout.write(f"   application status={app.status} outcome={app.cooptation_outcome}")
        self.stdout.write("   sent: cooptation_accepted x2 (to candidate)")

        self._step("5/6", "Approving application as staff (creates User + Member)")
        user, member = services.approve_application(app, reviewed_by=staff_user)
        self.stdout.write(f"   created User pk={user.pk} email={user.email}")
        self.stdout.write(f"   created Member pk={member.pk} status={member.status}")
        self.stdout.write("   sent: application_approved (with password-set link)")

        self._step("6/6", "Cleanup" if not keep else "Keeping records (--keep)")
        if keep:
            self.stdout.write(
                self.style.WARNING(
                    "   skipped — re-run without --keep, or call: "
                    "python manage.py smoke_test_cooptation --candidate-email "
                    f"{candidate_email} (will auto-clean before next run)"
                )
            )
        else:
            self._cleanup(candidate_email)
            self.stdout.write(
                "   removed: candidate User, Member, AdminApplication, parrain Members"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{SMOKE_TAG} done. Check {candidate_email} for 3+ emails. "
                "Click the password-set link in 'application_approved' to verify "
                "the C1 base36 fix resolves through allauth."
            )
        )

    # --- step helpers -------------------------------------------------------

    def _step(self, n: str, label: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n[{n}] {label}"))

    def _resolve_staff(self, admin_email: str | None):
        User = get_user_model()  # noqa: N806
        if admin_email:
            try:
                return User.objects.get(email=admin_email, is_staff=True)
            except User.DoesNotExist as exc:
                raise CommandError(
                    f"No staff user with email {admin_email}. "
                    "Pass --admin-email <existing staff email> or omit for the first staff user."
                ) from exc
        staff = User.objects.filter(is_staff=True, is_active=True).order_by("pk").first()
        if staff is None:
            raise CommandError(
                "No staff users exist. Create one via `python manage.py createsuperuser` "
                "or pass --admin-email."
            )
        return staff

    @transaction.atomic
    def _seed_parrains(self) -> tuple[Member, Member]:
        User = get_user_model()  # noqa: N806
        parrains: list[Member] = []
        for i, email in enumerate((SMOKE_PARRAIN_1_EMAIL, SMOKE_PARRAIN_2_EMAIL), start=1):
            user, _ = User.objects.get_or_create(
                username=email,
                defaults={"email": email},
            )
            user.email = email
            user.set_unusable_password()
            user.is_active = True
            user.save()
            member, _ = Member.objects.update_or_create(
                user=user,
                defaults={
                    "first_name": f"SmokeParrain{i}",
                    "last_name": "Test",
                    "years_attended": [1980, 1981, 1982, 1983],
                    "classes": ["6e", "5e", "4e", "3e"],
                    "city": "Niamey" if i == 1 else "Cotonou",
                    "status": "active",
                },
            )
            parrains.append(member)
        return parrains[0], parrains[1]

    def _submit_application(
        self, candidate_email: str, p1: Member, p2: Member
    ) -> tuple[AdminApplication, CooptationRequest, CooptationRequest]:
        # Mirrors signup_view's body. We bypass the HTTP layer (no basic auth,
        # no rate limit, no CSRF) and call the same model + email functions
        # signup_view uses. Emails fire after the atomic exits, same ordering
        # as the view.
        with transaction.atomic():
            app = AdminApplication.objects.create(
                full_name=f"{SMOKE_TAG} Candidat",
                nickname="",
                years_attended=[1980, 1981, 1982, 1983],
                classes=["6e", "5e", "4e", "3e"],
                city="Paris",
                country="France",
                profession="",
                email=candidate_email,
                whatsapp="",
                source_ip=None,
            )
            expires = timezone.now() + timedelta(days=14)
            req1 = CooptationRequest.objects.create(application=app, parrain=p1, expires_at=expires)
            req2 = CooptationRequest.objects.create(application=app, parrain=p2, expires_at=expires)

        emails.send_application_received(app)
        emails.send_cooptation_requests_sent(app, parrain_emails=[p1.user.email, p2.user.email])
        emails.send_parrain_invitation(req1)
        emails.send_parrain_invitation(req2)
        emails.send_admin_new_application(app)
        return app, req1, req2

    def _accept_vouches(self, req1: CooptationRequest, req2: CooptationRequest) -> None:
        # Mirrors parrain_vouch_view's accept branch: stamp the response,
        # email the candidate, then transition the parent application once
        # both vouches are in.
        with transaction.atomic():
            now = timezone.now()
            for req in (req1, req2):
                req.response = "accepted"
                req.responded_at = now
                req.comment = f"{SMOKE_TAG} auto-accept"
                req.save()
            app = req1.application
            app.cooptation_outcome = "all_accepted"
            app.status = "awaiting_admin"
            app.save()

        for req in (req1, req2):
            emails.send_cooptation_accepted(req)

    def _cleanup(self, candidate_email: str) -> None:
        User = get_user_model()  # noqa: N806
        # Candidate side: User + Member created by approve_application,
        # plus the AdminApplication record itself.
        AdminApplication.objects.filter(email=candidate_email).delete()
        AdminApplication.objects.filter(full_name__startswith=SMOKE_TAG).delete()
        candidate_user = User.objects.filter(email=candidate_email).first()
        if candidate_user is not None:
            Member.objects.filter(user=candidate_user).delete()
            candidate_user.delete()
        # Parrain side: delete Members first (FK on user) then the User rows.
        for email in (SMOKE_PARRAIN_1_EMAIL, SMOKE_PARRAIN_2_EMAIL):
            user = User.objects.filter(email=email).first()
            if user is not None:
                Member.objects.filter(user=user).delete()
                user.delete()
