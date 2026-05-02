"""Resend email integration: production backend + test fake + render helper."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class ResendBackend(BaseEmailBackend):
    """Sends each EmailMessage via Resend's REST API.

    Required settings:
        RESEND_API_KEY  — set in env.
    """

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        import resend  # imported lazily so tests don't require network

        resend.api_key = settings.RESEND_API_KEY
        sent = 0
        for msg in email_messages:
            payload: dict[str, Any] = {
                "from": msg.from_email or settings.DEFAULT_FROM_EMAIL,
                "to": list(msg.to),
                "subject": msg.subject,
                "text": msg.body,
            }
            html = next(
                (alt[0] for alt in (msg.alternatives or []) if alt[1] == "text/html"),
                None,
            )
            if html is not None:
                payload["html"] = html
            try:
                resend.Emails.send(payload)
                sent += 1
            except Exception:
                logger.exception("Resend delivery failed for to=%s", msg.to)
                if not self.fail_silently:
                    raise
        return sent


class FakeResendBackend(BaseEmailBackend):
    """Records messages in-process for tests; no network calls."""

    sent_messages: list[dict[str, Any]] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def send_messages(self, email_messages):
        sent = 0
        for msg in email_messages:
            rec: dict[str, Any] = {
                "from": msg.from_email or "",
                "to": list(msg.to),
                "subject": msg.subject,
                "text": msg.body,
            }
            html = next(
                (alt[0] for alt in (msg.alternatives or []) if alt[1] == "text/html"),
                None,
            )
            if html is not None:
                rec["html"] = html
            type(self).sent_messages.append(rec)
            sent += 1
        return sent


def send_email(to: str | list[str], template_base: str, context: dict[str, Any]) -> None:
    """Render `<template_base>.subject.txt`, `.txt`, and `.html` from
    `templates/emails/` and send a multipart message via Django's configured
    email backend.

    Example:
        send_email("alice@example.test",
                   "cooptation/parrain_invitation",
                   {"candidate": app, "vouch_url": url})
    """
    recipients = [to] if isinstance(to, str) else list(to)
    subject = render_to_string(f"emails/{template_base}.subject.txt", context).strip()
    text_body = render_to_string(f"emails/{template_base}.txt", context)
    html_body = render_to_string(f"emails/{template_base}.html", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()
