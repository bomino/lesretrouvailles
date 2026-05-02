import pytest


@pytest.fixture
def active_member(db):
    """A pre-existing active Member to use as a parrain. Non-staff."""
    from django.contrib.auth import get_user_model

    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="parrain1@example.test",
        email="parrain1@example.test",
        password="x",
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
        username="parrain2@example.test",
        email="parrain2@example.test",
        password="x",
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
def test_signup_get_renders_form(client):
    response = client.get("/inscription/")
    assert response.status_code == 200
    assert b"full_name" in response.content
    assert b"parrain1_email" in response.content
    assert b"parrain2_email" in response.content


@pytest.mark.django_db
def test_signup_post_creates_application_and_two_requests(
    client, active_member, second_active_member, settings
):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation.models import AdminApplication, CooptationRequest

    response = client.post("/inscription/", _form_payload(active_member, second_active_member))
    assert response.status_code == 302
    assert AdminApplication.objects.count() == 1
    assert CooptationRequest.objects.count() == 2


@pytest.mark.django_db
def test_signup_post_sends_4_emails_candidate_2parrains_admin(
    client, active_member, second_active_member, settings
):
    """1 to candidate (received) + 1 to candidate (requests sent) + 2 to parrains
    + 1 to admins (only if any staff exist). Without staff users, total is 4."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    client.post("/inscription/", _form_payload(active_member, second_active_member))
    assert len(FakeResendBackend.sent_messages) == 4


@pytest.mark.django_db
def test_signup_rejects_self_cooptation(client, active_member, second_active_member):
    payload = _form_payload(active_member, second_active_member, email=active_member.user.email)
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"vous parrainer" in response.content


@pytest.mark.django_db
def test_signup_rejects_duplicate_parrains(client, active_member):
    payload = _form_payload(active_member, active_member)
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"deux parrains diff" in response.content


@pytest.mark.django_db
def test_signup_rejects_unknown_parrain(client, active_member):
    payload = _form_payload(active_member, active_member, parrain2_email="ghost@example.test")
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"inconnu" in response.content


@pytest.mark.django_db
def test_signup_rejects_inactive_parrain(client, active_member, second_active_member):
    second_active_member.status = "suspended"
    second_active_member.save()
    payload = _form_payload(active_member, second_active_member)
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"inactif" in response.content or b"inconnu" in response.content


@pytest.mark.django_db
def test_signup_honeypot_silently_rejects(client, active_member, second_active_member):
    """Honeypot field non-empty → render success page but do not create application."""
    from cooptation.models import AdminApplication

    payload = _form_payload(active_member, second_active_member, website_url="http://spam")
    response = client.post("/inscription/", payload)
    assert response.status_code == 302
    assert AdminApplication.objects.count() == 0


@pytest.mark.django_db
def test_signup_records_source_ip(client, active_member, second_active_member):
    from cooptation.models import AdminApplication

    client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member),
        REMOTE_ADDR="203.0.113.5",
    )
    app = AdminApplication.objects.get()
    assert app.source_ip == "203.0.113.5"
