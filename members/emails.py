"""Email senders for the membership app — thin wrappers over send_email."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from alumni.email import send_email

from .models import RemovalRequest


def send_removal_confirmation_pending(removal_request: RemovalRequest) -> None:
    """To the requester after they submit the form. Contains the
    confirmation link and the entry preview so they can verify they're
    removing the right person."""
    send_email(
        removal_request.requester_email,
        "members/removal_confirmation_pending",
        {"request": removal_request, "entry": removal_request.entry},
    )


def send_removal_completed(removal_request: RemovalRequest) -> None:
    """To the requester after auto-execution. Acknowledgment, no action
    required."""
    send_email(
        removal_request.requester_email,
        "members/removal_completed",
        {"request": removal_request, "entry": removal_request.entry},
    )


def send_admin_removal_notification(removal_request: RemovalRequest) -> None:
    """FYI to all active staff after auto-execution. Transparency, not
    action-required. Lets admins notice patterns (e.g., 5 removals in
    1 minute = bot attack)."""
    User = get_user_model()  # noqa: N806
    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True).values_list("email", flat=True)
    )
    if not staff_emails:
        return
    send_email(
        staff_emails,
        "members/admin_removal_notification",
        {"request": removal_request, "entry": removal_request.entry},
    )


def send_admin_quarterly_ghost_digest(*, purged_logs, currently_listed, since) -> None:
    """Quarterly FYI to staff: list of ghost entries auto-removed in the
    last 90 days because they were >12 months old without admin renewal,
    plus a snapshot of the currently-listed entries with their age in
    months. No-op if no staff users (mirrors send_admin_removal_notification)."""
    User = get_user_model()  # noqa: N806
    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True).values_list("email", flat=True)
    )
    if not staff_emails:
        return
    send_email(
        staff_emails,
        "members/admin_stale_ghost_digest",
        {
            "logs": purged_logs,
            "currently_listed": currently_listed,
            "since": since,
            "purged_count": len(purged_logs),
            "listed_count": len(currently_listed),
        },
    )
