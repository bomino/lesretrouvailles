"""Context processors exposing memoriam settings to templates."""

from __future__ import annotations

from django.conf import settings


def memoriam_contact(request):
    return {"memoriam_contact_email": settings.MEMORIAM_CONTACT_EMAIL}
