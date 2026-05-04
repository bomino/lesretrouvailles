"""Resend wrappers for memoriam emails. Templates live under
templates/emails/memoriam/ to match alumni.email.send_email's expected
template path."""

from __future__ import annotations

from django.conf import settings

from alumni.email import send_email
from members.models import Member

from .models import InMemoriamEntry, InMemoriamNomination


def send_nomination_received_to_admins(nomination: InMemoriamNomination) -> None:
    send_email(
        list(settings.MEMORIAM_ADMIN_EMAILS),
        "memoriam/nomination_received",
        {"nomination": nomination},
    )


def send_fiche_published_to_member(member: Member, entry: InMemoriamEntry) -> None:
    send_email(
        member.user.email,
        "memoriam/fiche_published",
        {"member": member, "entry": entry},
    )
