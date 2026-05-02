import pytest
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model


@pytest.fixture
def superuser(db):
    User = get_user_model()  # noqa: N806
    return User.objects.create_superuser(
        username="root@example.test",
        email="root@example.test",
        password="x",
    )


@pytest.mark.django_db
def test_application_admin_registered():
    from cooptation.models import (
        AdminApplication,
        CooptationRequest,
        KnowledgeQuestion,
        QuestionnaireResponse,
    )

    assert site.is_registered(AdminApplication)
    assert site.is_registered(CooptationRequest)
    assert site.is_registered(KnowledgeQuestion)
    assert site.is_registered(QuestionnaireResponse)


@pytest.mark.django_db
def test_admin_approve_action_creates_member(superuser, make_application, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication
    from members.models import Member

    app = make_application(full_name="Idrissa Saidou", email="i@example.test")
    admin = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser

    admin.approve_action(FakeReq(), AdminApplication.objects.filter(pk=app.pk))
    app.refresh_from_db()
    assert app.status == "approved"
    assert Member.objects.filter(user__email="i@example.test").exists()


@pytest.mark.django_db
def test_admin_reject_action_sets_retention(superuser, make_application, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication

    app = make_application(email="r@example.test")
    admin = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser
        POST = {"reason": "Promotion non éligible"}

    admin.reject_action(FakeReq(), AdminApplication.objects.filter(pk=app.pk))
    app.refresh_from_db()
    assert app.status == "rejected"
    assert app.retention_until is not None


@pytest.mark.django_db
def test_admin_resend_password_link_action(superuser, make_application, settings):
    """After approval, admin can re-send the password-set email."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication
    from cooptation.services import approve_application

    app = make_application(email="i@example.test")
    approve_application(app, reviewed_by=superuser)
    FakeResendBackend.sent_messages.clear()

    admin = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser

    admin.resend_password_link_action(FakeReq(), AdminApplication.objects.filter(pk=app.pk))
    assert len(FakeResendBackend.sent_messages) == 1
    assert "/accounts/password/reset/key/" in FakeResendBackend.sent_messages[0]["text"]
