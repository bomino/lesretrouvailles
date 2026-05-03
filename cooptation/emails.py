"""Email senders — one function per template. Thin wrappers over alumni.email.send_email."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from alumni.email import send_email

from .models import AdminApplication, CooptationRequest


def send_application_received(application: AdminApplication) -> None:
    send_email(
        application.email,
        "cooptation/application_received",
        {"application": application},
    )


def send_cooptation_requests_sent(
    application: AdminApplication, *, parrain_emails: list[str]
) -> None:
    send_email(
        application.email,
        "cooptation/cooptation_requests_sent",
        {"application": application, "parrain_emails": parrain_emails},
    )


def send_cooptation_accepted(request: CooptationRequest) -> None:
    send_email(
        request.application.email,
        "cooptation/cooptation_accepted",
        {"application": request.application, "request": request},
    )


def send_cooptation_refused(request: CooptationRequest) -> None:
    send_email(
        request.application.email,
        "cooptation/cooptation_refused",
        {"application": request.application, "request": request},
    )


def send_cooptation_expired(application: AdminApplication, *, questionnaire_url: str) -> None:
    send_email(
        application.email,
        "cooptation/cooptation_expired",
        {"application": application, "questionnaire_url": questionnaire_url},
    )


def send_application_approved(application: AdminApplication, *, password_set_url: str) -> None:
    send_email(
        application.email,
        "cooptation/application_approved",
        {"application": application, "password_set_url": password_set_url},
    )


def send_application_rejected(application: AdminApplication, *, reason: str) -> None:
    send_email(
        application.email,
        "cooptation/application_rejected",
        {"application": application, "reason": reason},
    )


def send_parrain_invitation(request: CooptationRequest) -> None:
    send_email(
        request.parrain.user.email,
        "cooptation/parrain_invitation",
        {"application": request.application, "request": request},
    )


def send_parrain_reminder(request: CooptationRequest) -> None:
    send_email(
        request.parrain.user.email,
        "cooptation/parrain_reminder",
        {"application": request.application, "request": request},
    )


def send_admin_new_application(application: AdminApplication) -> None:
    User = get_user_model()  # noqa: N806
    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True).values_list("email", flat=True)
    )
    if not staff_emails:
        return
    send_email(
        staff_emails,
        "cooptation/admin_new_application",
        {"application": application},
    )
