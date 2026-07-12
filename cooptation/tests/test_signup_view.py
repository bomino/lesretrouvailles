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
def test_signup_rejects_email_matching_existing_member(client, active_member, second_active_member):
    """Regression: a candidate cannot apply with an email already attached to
    an existing Member. Otherwise approval would silently overwrite that
    Member's profile via approve_application's update_or_create path."""
    from django.contrib.auth import get_user_model

    from cooptation.models import AdminApplication
    from members.models import Member

    User = get_user_model()  # noqa: N806
    existing_user = User.objects.create_user(
        username="duplicate@example.test",
        email="duplicate@example.test",
        password="x",
    )
    Member.objects.create(
        user=existing_user,
        first_name="Duplicate",
        last_name="Owner",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
    )

    payload = _form_payload(active_member, second_active_member, email="duplicate@example.test")
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"correspond" in response.content or b"compte" in response.content
    assert AdminApplication.objects.count() == 0


@pytest.mark.django_db
def test_signup_rejects_email_matching_existing_user_without_member(
    client, active_member, second_active_member
):
    """Security regression: the superuser (and any staff account) has a User
    but no Member row, so the Member-only check let a candidate apply with
    that email — and approval would then hijack the account. Emails matching
    ANY existing User must be rejected."""
    from django.contrib.auth import get_user_model

    from cooptation.models import AdminApplication

    User = get_user_model()  # noqa: N806
    User.objects.create_superuser(
        username="bominomla",
        email="admin@example.test",
        password="x",
    )

    payload = _form_payload(active_member, second_active_member, email="admin@example.test")
    response = client.post("/inscription/", payload)
    assert response.status_code == 200
    assert b"correspond" in response.content or b"compte" in response.content
    assert AdminApplication.objects.count() == 0


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


@pytest.mark.django_db
def test_signup_uses_rightmost_xff_token_not_spoofable_leftmost(
    client, active_member, second_active_member
):
    """Regression: X-Forwarded-For is a list where each hop appends what it
    saw as the source. The leftmost token is whatever the original client
    *claimed* (and is therefore spoofable). Behind Railway's edge, the
    rightmost token is what Railway actually saw — that's the one we trust.

    Without this guard, a spammer sending `X-Forwarded-For: 1.1.1.1` would
    have `1.1.1.1` recorded as source_ip and the 24h ip_badge in
    `/admin/cooptation/adminapplication/` would key off the spoofed value.
    """
    from cooptation.models import AdminApplication

    client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member),
        HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.5",
        REMOTE_ADDR="10.0.0.1",
    )
    app = AdminApplication.objects.get()
    assert app.source_ip == "203.0.113.5", (
        "Must take rightmost XFF (Railway's view) — not leftmost (client-claimed)"
    )


@pytest.mark.django_db
def test_signup_accepts_classes_with_section_letters(client, active_member, second_active_member):
    """Real-world classes have parallel sections (4eA, 3eB) — the form must
    accept them, not just the level-only 6e/5e/4e/3e form."""
    from cooptation.models import AdminApplication

    response = client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member, classes="6eA,5eB,4eA,3eC"),
    )
    assert response.status_code == 302
    app = AdminApplication.objects.get()
    assert app.classes == ["6eA", "5eB", "4eA", "3eC"]


@pytest.mark.django_db
def test_signup_accepts_empty_classes(client, active_member, second_active_member):
    """Many alumni don't remember their class sections — the field is optional.
    Empty submission must validate and produce an application with classes=[]."""
    from cooptation.models import AdminApplication

    response = client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member, classes=""),
    )
    assert response.status_code == 302
    app = AdminApplication.objects.get()
    assert app.classes == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad_value",
    [
        "2nde",  # high-school grade, out of CEG range
        "7e",  # level out of range
        "4eAB",  # two-letter section not allowed
        "4",  # bare level — ambiguous (P7.1: short form requires a section letter)
        "xyz",  # not a class
    ],
)
def test_signup_rejects_invalid_class_formats(
    client, active_member, second_active_member, bad_value
):
    from cooptation.models import AdminApplication

    response = client.post(
        "/inscription/",
        _form_payload(active_member, second_active_member, classes=bad_value),
    )
    assert response.status_code == 200  # form re-rendered with error
    assert AdminApplication.objects.count() == 0
    assert b"Classe inconnue" in response.content


@pytest.mark.django_db
def test_admin_new_application_filters_blank_staff_emails(settings, active_member):
    """A co-admin without an email must not land a blank string in the
    Resend 'to' list — that fails the API call on every signup."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from django.contrib.auth import get_user_model

    from alumni.email import FakeResendBackend
    from cooptation.emails import send_admin_new_application
    from cooptation.models import AdminApplication

    User = get_user_model()  # noqa: N806
    User.objects.create_user(username="22790000001", email="", password="x", is_staff=True)
    User.objects.create_user(
        username="staff@example.test", email="staff@example.test", password="x", is_staff=True
    )

    app = AdminApplication.objects.create(
        full_name="X Y",
        years_attended=[1980],
        classes=[],
        city="Niamey",
        country="Niger",
        email="cand@example.test",
    )
    FakeResendBackend.sent_messages.clear()
    send_admin_new_application(app)
    assert len(FakeResendBackend.sent_messages) == 1
    assert FakeResendBackend.sent_messages[0]["to"] == ["staff@example.test"]


@pytest.mark.django_db
def test_signup_email_failure_after_commit_does_not_500(
    client, active_member, second_active_member, settings, monkeypatch
):
    """The application is committed before the email fan-out runs. A Resend
    outage must not turn a recorded submission into a 500 — the candidate
    would resubmit, creating duplicates."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from cooptation import views as cooptation_views
    from cooptation.models import AdminApplication

    def _boom(*args, **kwargs):
        raise RuntimeError("resend down")

    monkeypatch.setattr(cooptation_views.emails, "send_admin_new_application", _boom)

    response = client.post("/inscription/", _form_payload(active_member, second_active_member))
    assert response.status_code == 302
    assert response.url == "/inscription/merci/"
    assert AdminApplication.objects.count() == 1


@pytest.mark.django_db
def test_signup_rate_limit_returns_french_429_not_english_403(client):
    """The 6th POST in an hour must keep the candidate on a French page,
    not Django's bare English '403 Forbidden'."""
    for _ in range(5):
        client.post("/inscription/", {})  # invalid form still consumes the bucket
    response = client.post("/inscription/", {})
    assert response.status_code == 429
    assert b"Trop de demandes" in response.content


@pytest.mark.django_db
def test_signup_rate_limit_buckets_on_real_client_ip_not_shared_proxy(client):
    """Behind Railway's proxy every client shares REMOTE_ADDR. The limiter
    must bucket on the rightmost X-Forwarded-For token so one abuser cannot
    block all signups platform-wide."""
    for _ in range(6):
        blocked = client.post("/inscription/", {}, HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.5")
    assert blocked.status_code == 429

    other = client.post("/inscription/", {}, HTTP_X_FORWARDED_FOR="1.1.1.1, 198.51.100.9")
    assert other.status_code == 200  # different real client, own bucket
