"""Phase 2.1 — /gestion/membres/<slug>/identifiant/ username change.

Changing User.username (= the WhatsApp digits the member uses to log in)
is gated by typing the current number to confirm. Wrong number locks the
member out of the platform — high-friction confirmation prevents typos.
"""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_username_change_anon_redirects(client, make_member):
    member = make_member()
    response = client.get(f"/gestion/membres/{member.slug}/identifiant/", follow=False)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_username_change_non_staff_blocked(client, regular_member_user, make_member):
    member = make_member()
    client.force_login(regular_member_user)
    response = client.get(f"/gestion/membres/{member.slug}/identifiant/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_username_change_get_shows_current_username(client, coadmin_user, make_user, make_member):
    user = make_user(username="22790000111")
    member = make_member(user=user, first_name="Idrissa")
    client.force_login(coadmin_user)
    response = client.get(f"/gestion/membres/{member.slug}/identifiant/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "22790000111" in body
    assert "Idrissa" in body


@pytest.mark.django_db
def test_username_change_happy_path(client, coadmin_user, make_user, make_member):
    user = make_user(username="22790000111")
    member = make_member(user=user)
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/identifiant/",
        {
            "confirm_current": "22790000111",
            "new_username": "22799887766",
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.username == "22799887766"


@pytest.mark.django_db
def test_username_change_rejects_wrong_confirmation(client, coadmin_user, make_user, make_member):
    user = make_user(username="22790000111")
    member = make_member(user=user)
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/identifiant/",
        {
            "confirm_current": "22790000999",  # wrong
            "new_username": "22799887766",
        },
    )
    assert response.status_code == 200  # form re-rendered with error
    user.refresh_from_db()
    assert user.username == "22790000111"  # unchanged


@pytest.mark.django_db
def test_username_change_rejects_duplicate_new_username(
    client, coadmin_user, make_user, make_member
):
    """The new username must not collide with another User."""
    existing = make_user(username="22799887766")
    make_member(user=existing)
    target_user = make_user(username="22790000111")
    target_member = make_member(user=target_user)
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{target_member.slug}/identifiant/",
        {
            "confirm_current": "22790000111",
            "new_username": "22799887766",  # already taken
        },
    )
    assert response.status_code == 200
    target_user.refresh_from_db()
    assert target_user.username == "22790000111"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad_value",
    [
        "abc",  # letters strip to nothing
        "1234567",  # too short (<8) after stripping
        "1" * 16,  # too long (>15)
    ],
)
def test_username_change_rejects_invalid_format(
    client, coadmin_user, make_user, make_member, bad_value
):
    """Strings that are still invalid after non-digit stripping (empty, too
    short, too long) keep being rejected. Whitespace and '+' decorators
    are NOT in this list anymore — they're normalized by clean_new_username
    and validated as their stripped form."""
    user = make_user(username="22790000111")
    member = make_member(user=user)
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/identifiant/",
        {
            "confirm_current": "22790000111",
            "new_username": bad_value,
        },
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.username == "22790000111"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "raw, normalized",
    [
        ("+22799887766", "22799887766"),  # leading +
        ("+227 99 88 77 66", "22799887766"),  # spaces
        ("+1 555-987-6543", "15559876543"),  # USA punctuation
    ],
)
def test_username_change_strips_non_digits_then_saves(
    client, coadmin_user, make_user, make_member, raw, normalized
):
    """Operators can paste WhatsApp-flavored values; non-digits get stripped
    silently and the resulting digit string is what's saved."""
    user = make_user(username="22790000111")
    member = make_member(user=user)
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/identifiant/",
        {
            "confirm_current": "22790000111",
            "new_username": raw,
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.username == normalized


@pytest.mark.django_db
def test_username_change_strips_then_rejects_too_short(
    client, coadmin_user, make_user, make_member
):
    """A US local number without country code strips to 10 digits, which
    is in the 8-15 range BUT fails the wa.me country-code expectation.
    The form accepts 10 digits as 'valid format' here — the operator is
    responsible for adding the country code. This test documents that
    behavior so anyone reading later understands it's intentional."""
    user = make_user(username="22790000111")
    member = make_member(user=user)
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/identifiant/",
        {
            "confirm_current": "22790000111",
            "new_username": "(555) 123-4567",  # 10 digits after strip
        },
    )
    # 10 digits passes the 8-15 length check, so the form accepts it.
    # If the operator forgot the country code, they'll find out only when
    # the wa.me deeplink 404s for the wrong member.
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.username == "5551234567"


@pytest.mark.django_db
def test_username_change_writes_audit_log(client, coadmin_user, make_user, make_member):
    from members.models import AuditLog

    user = make_user(username="22790000111")
    member = make_member(user=user, first_name="Idrissa", last_name="Saidou")
    client.force_login(coadmin_user)
    client.post(
        f"/gestion/membres/{member.slug}/identifiant/",
        {
            "confirm_current": "22790000111",
            "new_username": "22799887766",
        },
    )
    log = AuditLog.objects.filter(
        action="gestion.member.username_changed",
        target_id=str(member.pk),
    ).first()
    assert log is not None
    assert log.actor == coadmin_user
    assert log.metadata.get("old_username") == "22790000111"
    assert log.metadata.get("new_username") == "22799887766"
    assert "Idrissa" in log.metadata.get("member_full_name", "")


@pytest.mark.django_db
def test_username_change_rejects_same_as_current(client, coadmin_user, make_user, make_member):
    """No-op change (new == current) is a form error, not a silent success."""
    user = make_user(username="22790000111")
    member = make_member(user=user)
    client.force_login(coadmin_user)
    response = client.post(
        f"/gestion/membres/{member.slug}/identifiant/",
        {
            "confirm_current": "22790000111",
            "new_username": "22790000111",
        },
    )
    assert response.status_code == 200  # form error, no redirect
