"""Application lifecycle services. Called from admin actions; never from a Django signal."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.http import int_to_base36

from members.models import Member

from . import emails
from .models import AdminApplication


@transaction.atomic
def approve_application(application: AdminApplication, *, reviewed_by) -> tuple:
    """Create User+Member, mark application approved, send password-set email.

    Idempotent on `application.email` — if a User already exists with that
    email, we update its associated Member rather than crashing.
    Returns (user, member).
    """
    User = get_user_model()  # noqa: N806
    user, _ = User.objects.get_or_create(
        email=application.email,
        defaults={"username": application.email},
    )
    user.set_unusable_password()
    user.is_active = True
    user.save()

    parts = application.full_name.split(maxsplit=1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    member, _ = Member.objects.update_or_create(
        user=user,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "nickname": application.nickname,
            "years_attended": application.years_attended,
            "classes": application.classes,
            "city": application.city,
            "country": application.country,
            "profession": application.profession,
            "status": "active",
        },
    )

    application.status = "approved"
    application.reviewed_by = reviewed_by
    application.save()

    password_set_url = _build_password_set_url(user)
    emails.send_application_approved(application, password_set_url=password_set_url)

    return user, member


def _build_password_set_url(user) -> str:
    """Generate an Allauth-compatible password-reset URL for `user`.

    Allauth's URL pattern is `accounts/password/reset/key/<uidb36>-<token>/`
    and it decodes the leading segment with `int_to_base36`/`base36_to_int`,
    NOT base64. Encoding the PK with `urlsafe_base64_encode` produces a
    string allauth interprets as a different integer, so the user lookup
    fails and the link 404s.
    """
    from django.conf import settings as django_settings

    uidb36 = int_to_base36(user.pk)
    token = default_token_generator.make_token(user)
    site_url = getattr(django_settings, "SITE_URL", "https://staging.villageretrouvailles.com")
    return f"{site_url}/accounts/password/reset/key/{uidb36}-{token}/"


@transaction.atomic
def reject_application(application: AdminApplication, *, reviewed_by, note: str) -> None:
    application.status = "rejected"
    application.review_note = note
    application.reviewed_by = reviewed_by
    application.rejected_at = timezone.now()
    application.retention_until = application.rejected_at + timedelta(days=180)
    application.save()
    emails.send_application_rejected(application, reason=note)


def purge_application(application: AdminApplication) -> None:
    application.purge()
