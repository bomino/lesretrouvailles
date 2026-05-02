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
