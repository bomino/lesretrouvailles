from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def staff_user(db):
    User = get_user_model()  # noqa: N806
    return User.objects.create_user(
        username="admin@example.test",
        email="admin@example.test",
        password="x",
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
def test_approve_creates_user_and_member(make_application, staff_user, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.services import approve_application
    from members.models import Member

    FakeResendBackend.sent_messages.clear()
    app = make_application(
        full_name="Idrissa Saidou",
        email="idrissa@example.test",
        city="Niamey",
    )
    user, member = approve_application(app, reviewed_by=staff_user)

    User = get_user_model()  # noqa: N806
    assert User.objects.filter(email="idrissa@example.test").exists()
    assert Member.objects.filter(user=user).exists()
    assert member.first_name == "Idrissa"
    assert member.last_name == "Saidou"
    assert member.status == "active"

    app.refresh_from_db()
    assert app.status == "approved"
    assert app.reviewed_by == staff_user

    assert len(FakeResendBackend.sent_messages) == 1
    assert "/accounts/password/reset/key/" in FakeResendBackend.sent_messages[0]["text"]


@pytest.mark.django_db
def test_approve_copies_whatsapp_digits_to_member(make_application, staff_user, settings):
    """A coopted candidate's AdminApplication.whatsapp (free-form, may have
    + and spaces) is normalized to digits-only and copied into
    Member.whatsapp at approval time."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.services import approve_application

    app = make_application(
        full_name="Awa Diallo",
        email="awa@example.test",
        whatsapp="+227 90 00 01 23",  # free-form, must be normalized
    )
    _, member = approve_application(app, reviewed_by=staff_user)
    assert member.whatsapp == "22790000123"


@pytest.mark.django_db
def test_approve_drops_unrecognizable_whatsapp(make_application, staff_user, settings):
    """If the whatsapp field on the application is missing or doesn't look
    like a phone number (e.g., the candidate left it blank), Member.whatsapp
    stays empty rather than storing garbage."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.services import approve_application

    app = make_application(
        full_name="Awa Diallo",
        email="awa2@example.test",
        whatsapp="",  # blank
    )
    _, member = approve_application(app, reviewed_by=staff_user)
    assert member.whatsapp == ""


@pytest.mark.django_db
def test_approve_handles_full_name_with_one_token(make_application, staff_user):
    """A candidate who put only a single name in full_name still gets a Member;
    last_name becomes empty string rather than crashing."""
    from cooptation.services import approve_application

    app = make_application(full_name="Mononyme", email="m@example.test")
    user, member = approve_application(app, reviewed_by=staff_user)
    assert member.first_name == "Mononyme"
    assert member.last_name == ""


@pytest.mark.django_db
def test_approve_idempotent_on_email(make_application, staff_user):
    """Re-approving the same email (perhaps via a duplicate application)
    does not error and updates the existing Member."""
    from cooptation.services import approve_application

    app1 = make_application(full_name="Same Person", email="same@example.test")
    approve_application(app1, reviewed_by=staff_user)

    app2 = make_application(full_name="Same Person", email="same@example.test", city="Paris")
    user2, member2 = approve_application(app2, reviewed_by=staff_user)
    assert member2.city == "Paris"


@pytest.mark.django_db
def test_reject_sets_retention_until_six_months(make_application, staff_user, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.services import reject_application

    app = make_application(email="r@example.test")
    reject_application(app, reviewed_by=staff_user, note="Promotion non éligible")

    app.refresh_from_db()
    assert app.status == "rejected"
    assert app.review_note == "Promotion non éligible"
    assert app.rejected_at is not None
    assert app.retention_until is not None
    delta = app.retention_until - app.rejected_at
    assert timedelta(days=179) <= delta <= timedelta(days=181)


@pytest.mark.django_db
def test_reject_emails_candidate_with_reason(make_application, staff_user, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.services import reject_application

    FakeResendBackend.sent_messages.clear()
    app = make_application(email="r@example.test")
    reject_application(app, reviewed_by=staff_user, note="Manque de précisions")
    assert "Manque de précisions" in FakeResendBackend.sent_messages[0]["text"]


@pytest.mark.django_db
def test_password_set_url_validates_through_allauth_end_to_end(
    make_application, staff_user, client, settings
):
    """Regression for two stacked bugs:

    1. base64 encoding of the user pk silently decodes to the wrong integer
       under allauth's base36_to_int.
    2. Django's contrib.auth.tokens.default_token_generator produces tokens
       that look syntactically valid but fail allauth's check_token (allauth
       hashes the user's email into the token; Django's generator does not).

    A successful first GET on the key URL must 302-redirect to the
    /set-password/ form (allauth's "valid token" path). A 200 with
    `token_fail=True` in the context — what bug #2 produced — is the silent
    failure mode this test guards against.
    """
    from urllib.parse import urlparse

    from cooptation.services import _build_password_set_url, approve_application

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    app = make_application(full_name="Base36 Tester", email="b36@example.test")
    user, _ = approve_application(app, reviewed_by=staff_user)

    url = _build_password_set_url(user)
    path = urlparse(url).path
    assert path.startswith("/accounts/password/reset/key/")

    resp = client.get(path)
    assert resp.status_code == 302, (
        f"Allauth should redirect on a valid token; got {resp.status_code}"
    )
    # Allauth swaps the actual key for the literal string "set-password" in
    # the redirect URL so the token doesn't leak through the Referer header.
    # If the token were invalid, allauth would return 200 with token_fail=True
    # in the template context and would NOT redirect.
    assert "set-password" in resp["Location"], (
        f"Expected redirect to .../<uidb36>-set-password/; got Location={resp['Location']}"
    )


@pytest.mark.django_db
def test_purge_clears_pii_and_sets_status(make_application):
    from cooptation.services import purge_application

    app = make_application(full_name="X Y", email="x@example.test", whatsapp="+227")
    app.source_ip = "1.2.3.4"
    app.save()
    purge_application(app)
    app.refresh_from_db()
    assert app.status == "purged"
    assert app.full_name == ""
    assert app.email == ""
    assert app.whatsapp == ""
    assert app.source_ip is None
