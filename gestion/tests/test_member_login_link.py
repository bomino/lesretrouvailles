"""Phase 3 — /gestion/membres/<slug>/lien/ magic-link reissue.

The dominant ~80%-no-email cohort signs in via WhatsApp DMs containing
allauth password-reset URLs. When a member loses or expires their link,
the operator regenerates one here, copies it, and DMs them — without
shelling into Railway to run reissue_login_link.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest


@pytest.mark.django_db
def test_login_link_anon_redirects(client, make_member):
    member = make_member()
    response = client.get(f"/gestion/membres/{member.slug}/lien/", follow=False)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_login_link_non_staff_blocked(client, regular_member_user, make_member):
    member = make_member()
    client.force_login(regular_member_user)
    response = client.get(f"/gestion/membres/{member.slug}/lien/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_login_link_get_shows_form_no_link(client, coadmin_user, make_member):
    """GET shows the confirmation page with the member's name and a
    'Générer' button. No link is generated yet (link only appears after
    POST so the operator doesn't accidentally leak it via browser back-
    button)."""
    member = make_member(first_name="Idrissa", last_name="Saidou")
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/lien/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Idrissa" in body
    # No actual reset URL in the response yet
    assert "/accounts/password/reset/key/" not in body


@pytest.mark.django_db
def test_login_link_post_generates_valid_allauth_url(
    client, coadmin_user, make_user, make_member, settings
):
    settings.SITE_URL = "https://test.villageretrouvailles.local"
    user = make_user(username="22790000123", email="m@example.test")
    member = make_member(user=user)
    client.force_login(coadmin_user)
    response = client.post(f"/gestion/membres/{member.slug}/lien/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Allauth password-reset key path (uidb36-token shape)
    match = re.search(
        r"https://test\.villageretrouvailles\.local/accounts/password/reset/key/[a-z0-9]+-[a-z0-9-]+/",
        body,
    )
    assert match is not None, "No allauth reset URL found in response"


@pytest.mark.django_db
def test_login_link_post_writes_audit_log(client, coadmin_user, make_user, make_member):
    from members.models import AuditLog

    user = make_user(username="22790000456")
    member = make_member(user=user, first_name="Awa")
    client.force_login(coadmin_user)
    client.post(f"/gestion/membres/{member.slug}/lien/")
    log = AuditLog.objects.filter(
        action="gestion.login_link.reissued",
        target_id=str(member.pk),
    ).first()
    assert log is not None
    assert log.actor == coadmin_user
    assert log.metadata.get("target_username") == "22790000456"
    assert "Awa" in log.metadata.get("member_full_name", "")


@pytest.mark.django_db
def test_login_link_get_does_not_write_audit(client, coadmin_user, make_member):
    """GET must not generate a link or write an audit row — only POST does."""
    from members.models import AuditLog

    member = make_member()
    client.force_login(coadmin_user)
    client.get(f"/gestion/membres/{member.slug}/lien/")
    assert (
        AuditLog.objects.filter(
            action="gestion.login_link.reissued",
            target_id=str(member.pk),
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_login_link_post_renders_wa_me_link(client, coadmin_user, make_user, make_member):
    """A wa.me share button targets the member's WhatsApp number with a
    pre-filled French message containing the magic link."""
    user = make_user(username="22790000789")
    member = make_member(user=user, first_name="Boubou")
    client.force_login(coadmin_user)
    response = client.post(f"/gestion/membres/{member.slug}/lien/")
    body = response.content.decode("utf-8")
    # wa.me URL targets the digits-only phone
    match = re.search(
        r'href="(https://wa\.me/22790000789\?text=[^"]+)"',
        body,
    )
    assert match is not None, "No wa.me share link found"
    parsed = urlparse(match.group(1))
    qs = parse_qs(parsed.query)
    text = qs["text"][0]
    # The decoded message contains the member's first name
    assert "Boubou" in text
    # And the magic link
    assert "/accounts/password/reset/key/" in text


@pytest.mark.django_db
def test_login_link_post_renders_copy_button(client, coadmin_user, make_member):
    """The Copier button must be present so the operator can paste the
    URL into a non-WhatsApp channel (email, SMS, etc.) when needed."""
    member = make_member()
    client.force_login(coadmin_user)
    response = client.post(f"/gestion/membres/{member.slug}/lien/")
    body = response.content.decode("utf-8")
    assert "Copier" in body
    # The clipboard JS reads the URL from a data-attribute or text content
    assert "data-copy-url" in body or 'id="magic-link-url"' in body


@pytest.mark.django_db
def test_login_link_hides_wa_me_button_for_non_digit_username(
    client, coadmin_user, make_user, make_member
):
    """wa.me only resolves digits-only WhatsApp numbers. For users whose
    username is an email (cooptation flow) or an admin handle (super-admin),
    the deeplink would 404. The button must be hidden in that case so the
    operator doesn't end up on a WhatsApp 'phone number invalid' page."""
    user = make_user(username="bominomla")  # alphabetic admin handle
    member = make_member(user=user)
    client.force_login(coadmin_user)
    response = client.post(f"/gestion/membres/{member.slug}/lien/")
    body = response.content.decode("utf-8")
    assert "https://wa.me/" not in body
    # The Copier button still renders so the operator can paste manually
    assert "Copier" in body
    # And we explain why the wa.me button is missing
    assert "n'est pas un num" in body  # "n'est pas un numéro WhatsApp"


@pytest.mark.django_db
def test_login_link_hides_wa_me_button_for_email_username(
    client, coadmin_user, make_user, make_member
):
    """Coopted members get username = email (cooptation/services.py:30).
    Same defensive hiding (when member.whatsapp is also empty)."""
    user = make_user(username="candidate@example.test")
    member = make_member(user=user)
    member.whatsapp = ""  # explicit: no whatsapp set
    member.save()
    client.force_login(coadmin_user)
    response = client.post(f"/gestion/membres/{member.slug}/lien/")
    body = response.content.decode("utf-8")
    assert "https://wa.me/" not in body
    assert "Copier" in body


@pytest.mark.django_db
def test_login_link_uses_member_whatsapp_when_set(client, coadmin_user, make_user, make_member):
    """The wa.me URL targets Member.whatsapp when set, not User.username.
    This is the path that makes the share button work for coopted members
    and manually-created admins who provided a phone number separately."""
    user = make_user(username="candidate@example.test")  # email, NOT digits
    member = make_member(user=user)
    member.whatsapp = "22790000888"  # explicit phone
    member.save()
    client.force_login(coadmin_user)
    response = client.post(f"/gestion/membres/{member.slug}/lien/")
    body = response.content.decode("utf-8")
    assert "https://wa.me/22790000888" in body
    # The email-as-username should NOT appear in the wa.me URL
    assert "wa.me/candidate" not in body
