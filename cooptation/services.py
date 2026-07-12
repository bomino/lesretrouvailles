"""Application lifecycle services. Called from admin actions; never from a Django signal."""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from allauth.account.forms import default_token_generator as allauth_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from members.models import VALID_WHATSAPP_PATTERN, Member

from . import emails
from .models import AdminApplication

logger = logging.getLogger(__name__)


def _digits_only(phone: str) -> str:
    """Normalize a free-form phone string to digits only (no +, no spaces)."""
    return re.sub(r"\D", "", phone or "")


class ApplicationStateError(ValueError):
    """The application is not in a state where this transition is allowed.

    Approve and reject both raise it, so a caller can guard both with one
    `except`. UI checks are not enough: admin bulk actions and direct POSTs
    reach these services without passing through a template.
    """


# Kept so existing callers (`except ApprovalError`) keep working.
ApprovalError = ApplicationStateError

# The only states from which an application can still be decided. Anything
# else — approved, rejected, purged — is terminal: re-deciding it would
# resurrect a purged record, reset the 180-day retention clock on a rejection,
# or silently re-approve someone.
DECIDABLE_STATUSES = frozenset({"cooptation_pending", "awaiting_admin"})
APPROVABLE_STATUSES = DECIDABLE_STATUSES  # back-compat alias


def approve_application(application: AdminApplication, *, reviewed_by) -> tuple:
    """Create User+Member, mark application approved, send password-set email.

    Refuses (ApplicationStateError) when the application is not in a decidable
    status, has a blank email (purged records), or when a User already exists
    with that email or username — adopting an existing account would wipe its
    password and overwrite its Member profile (account hijack).

    The email is sent AFTER the transaction commits, and a send failure is
    logged rather than raised: it used to sit inside @transaction.atomic, so a
    Resend outage rolled the approval back and one flaky provider blocked every
    co-admin from approving anyone. The candidate's password link can always be
    re-sent from the admin ("Renvoyer le lien de mot de passe").

    Returns (user, member).
    """
    if application.status not in DECIDABLE_STATUSES:
        raise ApprovalError(
            f"Application {application.pk} has status {application.status!r}; "
            "only cooptation_pending/awaiting_admin can be approved."
        )
    if not application.email:
        raise ApprovalError(f"Application {application.pk} has no email; cannot approve.")

    User = get_user_model()  # noqa: N806
    # Both fields matter: email is not unique, username IS. A coopted member
    # whose email was later changed or blanked leaves a User whose *username*
    # is still the old address — creating a second User with that username
    # would raise IntegrityError, which callers don't catch (only
    # ApprovalError), so it would 500 the gestion view and abort the admin
    # bulk action mid-queryset.
    if User.objects.filter(Q(email=application.email) | Q(username=application.email)).exists():
        raise ApprovalError(
            f"A user already exists with email or username {application.email!r}; "
            "refusing to adopt an existing account."
        )
    with transaction.atomic():
        user = User.objects.create(username=application.email, email=application.email)
        user.set_unusable_password()
        user.is_active = True
        user.save()

        parts = application.full_name.split(maxsplit=1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        # Coopted members come in with a whatsapp number on the AdminApplication
        # (free-form, possibly with +/spaces). Strip to digits-only so wa.me deep
        # links and operator DMs work without further normalization. Drop it if
        # the result doesn't match the expected 8-15 digit shape.
        candidate_whatsapp = _digits_only(application.whatsapp)
        if not VALID_WHATSAPP_PATTERN.fullmatch(candidate_whatsapp):
            candidate_whatsapp = ""

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
                "whatsapp": candidate_whatsapp,
                "status": "active",
            },
        )

        application.status = "approved"
        application.reviewed_by = reviewed_by
        application.save()

    # Committed. The email is best-effort from here — see the docstring.
    password_set_url = _build_password_set_url(user)
    try:
        emails.send_application_approved(application, password_set_url=password_set_url)
    except Exception:
        logger.exception(
            "approve_application: password-set email failed for application %s "
            "(the account WAS created; re-send from the admin)",
            application.pk,
        )

    return user, member


def _build_password_set_url(user) -> str:
    """Generate an Allauth-compatible password-reset URL for `user`.

    Allauth's URL pattern is `accounts/password/reset/key/<uidb36>-<key>/`.
    Two non-obvious requirements:

    1. The uidb36 segment must be base36 (NOT base64) — allauth decodes it
       with `base36_to_int`. We use allauth's own `user_pk_to_url_str` so
       any future encoding change in allauth carries through automatically.
    2. The token must come from allauth's `EmailAwarePasswordResetTokenGenerator`
       (its `default_token_generator`), NOT Django's contrib.auth one.
       Allauth's generator includes the user's email in the hash; tokens
       generated by Django's default look syntactically valid but fail
       allauth's `check_token`, rendering the page with a "bad link" error.
    """
    from django.conf import settings as django_settings

    uidb36 = user_pk_to_url_str(user)
    token = allauth_token_generator.make_token(user)
    site_url = getattr(django_settings, "SITE_URL", "https://staging.villageretrouvailles.com")
    return f"{site_url}/accounts/password/reset/key/{uidb36}-{token}/"


def reject_application(application: AdminApplication, *, reviewed_by, note: str) -> None:
    """Reject a decidable application.

    Refuses (ApplicationStateError) on a terminal status: re-rejecting an
    approved candidate would strand their live account, and re-rejecting an
    already-rejected or purged record would reset the 180-day retention clock,
    keeping PII past the RGPD window. UI checks are not enough — the admin bulk
    action reaches this service directly.

    Like approve_application, the email is sent after the commit and a failure
    is logged, not raised: a Resend outage must not roll back the decision.
    """
    if application.status not in DECIDABLE_STATUSES:
        raise ApplicationStateError(
            f"Application {application.pk} has status {application.status!r}; "
            "only cooptation_pending/awaiting_admin can be rejected."
        )

    with transaction.atomic():
        application.status = "rejected"
        application.review_note = note
        application.reviewed_by = reviewed_by
        application.rejected_at = timezone.now()
        application.retention_until = application.rejected_at + timedelta(days=180)
        application.save()

    try:
        emails.send_application_rejected(application, reason=note)
    except Exception:
        logger.exception(
            "reject_application: rejection email failed for application %s "
            "(the rejection WAS recorded)",
            application.pk,
        )


def purge_application(application: AdminApplication) -> None:
    application.purge()
