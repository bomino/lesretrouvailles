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


@pytest.mark.django_db
def test_message_user_swallows_only_messages_plumbing_failures(superuser, monkeypatch):
    """T3 (2026-08-01 review tail): the override caught `(TypeError,
    Exception)` — i.e., everything — so a real failure silently discarded the
    per-row "non approuvée" warnings and the admin believed a bulk approve
    fully succeeded. Only the messages-framework plumbing failures (bare
    FakeRequest → TypeError, missing middleware → MessageFailure) are safe
    to drop."""
    from django.contrib import admin as django_admin

    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication

    admin_obj = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser

    # Plumbing failure (not an HttpRequest): swallowed, as before.
    admin_obj.message_user(FakeReq(), "hello")

    # A genuine bug in the stack must propagate.
    def boom(self, request, message, **kwargs):
        raise RuntimeError("messages framework exploded")

    monkeypatch.setattr(django_admin.ModelAdmin, "message_user", boom)
    with pytest.raises(RuntimeError):
        admin_obj.message_user(FakeReq(), "hello")


@pytest.mark.django_db
def test_admin_reject_action_records_explicit_generic_reason(superuser, make_application, settings):
    """The changelist action POST has no reason field — no admin UI ever
    supplied one, so the request.POST.get("reason") read was dead code
    implying a feature that doesn't exist. The bulk action is now explicit
    about being generic; reasoned rejections live in /gestion/."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication

    app = make_application(email="generic@example.test")
    admin_obj = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser
        # No POST at all — like a call from code paths without a form.

    admin_obj.reject_action(FakeReq(), AdminApplication.objects.filter(pk=app.pk))
    app.refresh_from_db()
    assert app.status == "rejected"
    assert app.review_note == "Demande non éligible"


@pytest.mark.django_db
def test_admin_resend_password_link_finds_user_by_username(superuser, make_application, settings):
    """approve_application creates the account with username=email; the email
    field itself is mutable and non-unique. Matching on email alone silently
    skipped users whose address was later corrected in /admin/."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend
    from cooptation.admin import AdminApplicationAdmin
    from cooptation.models import AdminApplication
    from cooptation.services import approve_application

    app = make_application(email="original@example.test")
    user, _ = approve_application(app, reviewed_by=superuser)
    user.email = "corrected@example.test"  # address fixed after approval
    user.save(update_fields=["email"])
    FakeResendBackend.sent_messages.clear()

    admin_obj = AdminApplicationAdmin(AdminApplication, site)

    class FakeReq:
        user = superuser

    admin_obj.resend_password_link_action(FakeReq(), AdminApplication.objects.filter(pk=app.pk))
    assert len(FakeResendBackend.sent_messages) == 1
