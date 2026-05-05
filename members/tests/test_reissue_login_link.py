"""Tests for reissue_login_link helper command (P7)."""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

User = get_user_model()


@pytest.mark.django_db
def test_reissue_prints_url_for_known_username(settings):
    settings.SITE_URL = "https://test.villageretrouvailles.local"
    User.objects.create_user(username="22790000001", email="", password="x")

    out = StringIO()
    call_command("reissue_login_link", "22790000001", stdout=out)

    output = out.getvalue()
    assert "https://test.villageretrouvailles.local/accounts/password/reset/key/" in output
    assert "22790000001" in output  # echoes the username for the operator's WhatsApp DM


@pytest.mark.django_db
def test_reissue_refuses_unknown_username():
    with pytest.raises(CommandError) as exc_info:
        call_command("reissue_login_link", "22799999999", stdout=StringIO())

    assert "not found" in str(exc_info.value).lower()
