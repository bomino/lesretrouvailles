import pytest


@pytest.fixture
def fake_backend(settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.DEFAULT_FROM_EMAIL = "Les Retrouvailles <noreply@example.test>"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    return FakeResendBackend


@pytest.mark.django_db
def test_application_received_renders_to_candidate(fake_backend, make_application):
    from cooptation.emails import send_application_received

    app = make_application(full_name="Idrissa Saidou", email="idrissa@example.test")
    send_application_received(app)
    msgs = fake_backend.sent_messages
    assert len(msgs) == 1
    m = msgs[0]
    assert m["to"] == ["idrissa@example.test"]
    assert "Idrissa Saidou" in m["text"]
    assert "<" in m["html"]
    assert m["subject"]
    assert "\n" not in m["subject"]


@pytest.mark.django_db
def test_parrain_invitation_includes_token_url(fake_backend, make_cooptation_request):
    from cooptation.emails import send_parrain_invitation

    req = make_cooptation_request()
    send_parrain_invitation(req)
    msg = fake_backend.sent_messages[0]
    assert msg["to"] == [req.parrain.user.email]
    assert req.token in msg["text"]
    assert req.token in msg["html"]


@pytest.mark.django_db
def test_parrain_reminder_renders(fake_backend, make_cooptation_request):
    from cooptation.emails import send_parrain_reminder

    req = make_cooptation_request()
    send_parrain_reminder(req)
    assert len(fake_backend.sent_messages) == 1


@pytest.mark.django_db
def test_cooptation_accepted_renders(fake_backend, make_cooptation_request):
    from cooptation.emails import send_cooptation_accepted

    req = make_cooptation_request()
    send_cooptation_accepted(req)
    assert len(fake_backend.sent_messages) == 1
    assert fake_backend.sent_messages[0]["to"] == [req.application.email]


@pytest.mark.django_db
def test_cooptation_refused_renders(fake_backend, make_cooptation_request):
    from cooptation.emails import send_cooptation_refused

    req = make_cooptation_request()
    send_cooptation_refused(req)
    assert len(fake_backend.sent_messages) == 1


@pytest.mark.django_db
def test_cooptation_requests_sent_renders(fake_backend, make_application):
    from cooptation.emails import send_cooptation_requests_sent

    app = make_application(email="c@example.test")
    send_cooptation_requests_sent(app, parrain_emails=["p1@example.test", "p2@example.test"])
    msg = fake_backend.sent_messages[0]
    assert "p1@example.test" in msg["text"] or "p1@example.test" in msg["html"]


@pytest.mark.django_db
def test_cooptation_expired_includes_questionnaire_url(fake_backend, make_application):
    from cooptation.emails import send_cooptation_expired

    app = make_application(email="c@example.test")
    send_cooptation_expired(app, questionnaire_url="https://example.test/questionnaire/abc/")
    msg = fake_backend.sent_messages[0]
    assert "https://example.test/questionnaire/abc/" in msg["text"]


@pytest.mark.django_db
def test_application_approved_includes_password_set_url(fake_backend, make_application):
    from cooptation.emails import send_application_approved

    app = make_application(email="c@example.test")
    send_application_approved(
        app, password_set_url="https://example.test/accounts/password/reset/key/abc/"
    )
    msg = fake_backend.sent_messages[0]
    assert "https://example.test/accounts/password/reset/key/abc/" in msg["text"]


@pytest.mark.django_db
def test_application_rejected_includes_reason(fake_backend, make_application):
    from cooptation.emails import send_application_rejected

    app = make_application(email="c@example.test")
    send_application_rejected(app, reason="Promotion non éligible")
    msg = fake_backend.sent_messages[0]
    assert "Promotion non éligible" in msg["text"]


@pytest.mark.django_db
def test_admin_new_application_to_all_staff(fake_backend, make_application):
    from django.contrib.auth import get_user_model

    User = get_user_model()  # noqa: N806
    User.objects.create_user(
        username="staff1", email="staff1@example.test", password="x", is_staff=True
    )
    User.objects.create_user(
        username="staff2", email="staff2@example.test", password="x", is_staff=True
    )
    User.objects.create_user(
        username="user1", email="user1@example.test", password="x"
    )  # not staff

    from cooptation.emails import send_admin_new_application

    app = make_application()
    send_admin_new_application(app)
    msg = fake_backend.sent_messages[0]
    assert sorted(msg["to"]) == ["staff1@example.test", "staff2@example.test"]


@pytest.mark.django_db
def test_links_use_configured_site_url_not_hardcoded_staging(
    fake_backend, make_application, make_cooptation_request, settings
):
    """Regression: parrain/admin emails must build URLs from SITE_URL, not the
    hardcoded staging host. Otherwise prod parrains would be sent to the
    basic-auth-gated staging site."""
    settings.SITE_URL = "https://prod.example.test"

    from django.contrib.auth import get_user_model

    from cooptation.emails import (
        send_admin_new_application,
        send_parrain_invitation,
        send_parrain_reminder,
    )

    User = get_user_model()  # noqa: N806
    User.objects.create_user(
        username="staff", email="staff@example.test", password="x", is_staff=True
    )

    app = make_application(email="c@example.test")
    req = make_cooptation_request(application=app)

    send_parrain_invitation(req)
    send_parrain_reminder(req)
    send_admin_new_application(app)

    for msg in fake_backend.sent_messages:
        for body in (msg["text"], msg.get("html", "")):
            assert "staging.villageretrouvailles.com" not in body
            assert "https://prod.example.test" in body


@pytest.mark.django_db
def test_each_template_includes_french_phrase(
    fake_backend, make_application, make_cooptation_request
):
    """Smoke test that French strings render."""
    from cooptation.emails import (
        send_admin_new_application,
        send_application_approved,
        send_application_received,
        send_application_rejected,
        send_cooptation_accepted,
        send_cooptation_expired,
        send_cooptation_refused,
        send_cooptation_requests_sent,
        send_parrain_invitation,
        send_parrain_reminder,
    )

    app = make_application(email="c@example.test")
    req = make_cooptation_request(application=app)

    send_application_received(app)
    send_application_approved(app, password_set_url="https://x/")
    send_application_rejected(app, reason="x")
    send_cooptation_accepted(req)
    send_cooptation_refused(req)
    send_cooptation_requests_sent(app, parrain_emails=["a@b"])
    send_cooptation_expired(app, questionnaire_url="https://x/")
    send_parrain_invitation(req)
    send_parrain_reminder(req)
    send_admin_new_application(app)

    assert len(fake_backend.sent_messages) == 10
    french_markers = [
        "bonjour",
        "cher",
        "votre",
        "merci",
        "cooptation",
        "communauté",
        "communaute",
        "membre",
    ]
    for m in fake_backend.sent_messages:
        text_lower = m["text"].lower()
        assert any(marker in text_lower for marker in french_markers), m["subject"]
