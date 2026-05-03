"""Tests for UTM source-of-arrival capture in the cooptation signup flow.

Visitors arrive at /inscription/?utm_source=whatsapp&utm_campaign=invitation
from the public landing's WhatsApp share button. The view stashes UTM in
session at GET time so it survives form-render → form-submit, then writes
to the new AdminApplication on POST.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def active_member(db):
    """Pre-existing active Member to use as a parrain. Mirrors the fixture
    in test_signup_view.py."""
    from django.contrib.auth import get_user_model

    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="parrain1@example.test", email="parrain1@example.test", password="x"
    )
    return Member.objects.create(
        user=user,
        first_name="Parrain",
        last_name="One",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e", "5e", "4e", "3e"],
        city="Niamey",
    )


@pytest.fixture
def second_active_member(db):
    from django.contrib.auth import get_user_model

    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="parrain2@example.test", email="parrain2@example.test", password="x"
    )
    return Member.objects.create(
        user=user,
        first_name="Parrain",
        last_name="Two",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e", "5e", "4e", "3e"],
        city="Cotonou",
    )


def _form_payload(parrain1, parrain2, **overrides):
    payload = {
        "full_name": "Idrissa Saidou",
        "nickname": "",
        "years_attended": "1980,1981,1982,1983",
        "classes": "6e,5e,4e,3e",
        "city": "Niamey",
        "country": "Niger",
        "profession": "",
        "email": "candidate@example.test",
        "whatsapp": "",
        "parrain1_email": parrain1.user.email,
        "parrain2_email": parrain2.user.email,
        "website_url": "",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_get_with_utm_stashes_into_session(client):
    client.get("/inscription/?utm_source=whatsapp&utm_campaign=invitation")
    assert client.session.get("signup_utm_source") == "whatsapp"
    assert client.session.get("signup_utm_campaign") == "invitation"


@pytest.mark.django_db
def test_post_pops_session_utm_to_application(
    client, active_member, second_active_member, settings
):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication

    client.get("/inscription/?utm_source=whatsapp&utm_campaign=invitation")
    client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member),
        HTTP_REFERER="https://example.com/landing",
    )

    app = AdminApplication.objects.get(email="candidate@example.test")
    assert app.utm_source == "whatsapp"
    assert app.utm_campaign == "invitation"
    assert app.referrer == "https://example.com/landing"


@pytest.mark.django_db
def test_post_without_prior_get_writes_empty_utm(
    client, active_member, second_active_member, settings
):
    """Visitor went directly to /inscription/ — no UTM, no error."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication

    client.post("/inscription/", _form_payload(active_member, second_active_member))

    app = AdminApplication.objects.get(email="candidate@example.test")
    assert app.utm_source == ""
    assert app.utm_campaign == ""
    assert app.referrer == ""


@pytest.mark.django_db
def test_referrer_truncated_at_512(client, active_member, second_active_member, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication

    long_ref = "https://example.com/" + "a" * 1000
    client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member),
        HTTP_REFERER=long_ref,
    )
    app = AdminApplication.objects.get(email="candidate@example.test")
    assert len(app.referrer) == 512


@pytest.mark.django_db
def test_utm_html_special_chars_are_stripped(client):
    # Literal special chars in the URL: Django's test Client passes them
    # raw as QUERY_STRING. Real browsers percent-encode them; QueryDict
    # decodes them back to the same characters, so the sanitization path
    # is identical end-to-end.
    client.get("/inscription/?utm_source=whatsapp<script>&utm_campaign=launch\"'")
    src = client.session.get("signup_utm_source") or ""
    camp = client.session.get("signup_utm_campaign") or ""
    for ch in ("<", ">", '"', "'"):
        assert ch not in src, f"{ch!r} not stripped from utm_source: {src!r}"
        assert ch not in camp, f"{ch!r} not stripped from utm_campaign: {camp!r}"


@pytest.mark.django_db
def test_utm_truncated_at_80_chars(client):
    long_value = "x" * 200
    client.get(f"/inscription/?utm_source={long_value}")
    assert len(client.session.get("signup_utm_source") or "") == 80
