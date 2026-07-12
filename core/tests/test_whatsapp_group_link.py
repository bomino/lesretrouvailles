"""F-13: the WhatsApp group links were a hardcoded placeholder.

`https://chat.whatsapp.com/` (no invite code) shipped to production in four
places in base.html. Clicking "Groupe WhatsApp" took a member to a dead page —
on a platform whose entire onboarding channel is WhatsApp.

The URL is now env-driven and the links are hidden until it is configured, so
an unset value can never again render a broken link.
"""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_no_whatsapp_link_rendered_when_url_unset(settings):
    settings.WHATSAPP_GROUP_URL = ""
    body = Client().get("/").content.decode("utf-8")
    assert "chat.whatsapp.com" not in body, "a placeholder link must never render"
    assert "Groupe WhatsApp" not in body


@pytest.mark.django_db
def test_whatsapp_link_renders_when_configured(settings):
    settings.WHATSAPP_GROUP_URL = "https://chat.whatsapp.com/ABC123xyz"
    body = Client().get("/").content.decode("utf-8")
    assert "https://chat.whatsapp.com/ABC123xyz" in body


def test_no_hardcoded_placeholder_left_in_templates():
    """Guard the whole class of bug: no template may hardcode the invite host."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    offenders = []
    for tpl in root.glob("**/templates/**/*.html"):
        if ".venv" in str(tpl):
            continue
        text = tpl.read_text(encoding="utf-8")
        if "chat.whatsapp.com" in text:
            offenders.append(str(tpl.relative_to(root)))
    assert not offenders, f"hardcoded WhatsApp invite URL in: {offenders}"
