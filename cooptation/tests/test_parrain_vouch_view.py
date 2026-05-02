from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.fixture
def parrain_client(make_cooptation_request):
    """A logged-in client whose user IS the parrain on the request."""
    req = make_cooptation_request()
    parrain = req.parrain
    user = parrain.user
    user.set_password("x")
    user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    c.request_obj = req  # avoid clashing with django request attribute
    return c


@pytest.mark.django_db
def test_vouch_get_renders_form_for_correct_parrain(parrain_client):
    response = parrain_client.get(f"/cooptation/{parrain_client.request_obj.token}/")
    assert response.status_code == 200
    assert parrain_client.request_obj.application.full_name.encode() in response.content


@pytest.mark.django_db
def test_vouch_unauthenticated_redirects_to_login(make_cooptation_request):
    req = make_cooptation_request()
    response = Client().get(f"/cooptation/{req.token}/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_vouch_403_for_wrong_user(make_cooptation_request, make_member, make_user):
    """A logged-in member who isn't the named parrain gets 403."""
    req = make_cooptation_request()
    other_user = make_user(password="other")
    make_member(user=other_user)
    ConsentRecord.objects.create(
        member=other_user.member,
        charter_version=CHARTER_CURRENT_VERSION,
        ip_address="127.0.0.1",
    )
    c = Client()
    c.login(username=other_user.username, password="other")
    response = c.get(f"/cooptation/{req.token}/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_vouch_410_when_expired(parrain_client):
    parrain_client.request_obj.expires_at = timezone.now() - timedelta(days=1)
    parrain_client.request_obj.save()
    response = parrain_client.get(f"/cooptation/{parrain_client.request_obj.token}/")
    assert response.status_code == 410
    assert b"expir" in response.content.lower()


@pytest.mark.django_db
def test_vouch_410_when_already_responded(parrain_client):
    parrain_client.request_obj.response = "accepted"
    parrain_client.request_obj.responded_at = timezone.now()
    parrain_client.request_obj.save()
    response = parrain_client.get(f"/cooptation/{parrain_client.request_obj.token}/")
    assert response.status_code == 410


@pytest.mark.django_db
def test_vouch_post_accept_transitions_request(parrain_client, settings):
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    response = parrain_client.post(
        f"/cooptation/{parrain_client.request_obj.token}/",
        {"response": "accepted", "comment": "Je le connais bien."},
    )
    assert response.status_code == 302
    parrain_client.request_obj.refresh_from_db()
    assert parrain_client.request_obj.response == "accepted"
    assert parrain_client.request_obj.responded_at is not None
    assert parrain_client.request_obj.comment == "Je le connais bien."
    # Email to candidate
    assert any("coopt" in (m.get("subject") or "").lower() for m in FakeResendBackend.sent_messages)


@pytest.mark.django_db
def test_vouch_eager_transition_to_awaiting_admin_when_all_responded(
    make_cooptation_request, settings
):
    """Both parrains accept → application transitions to awaiting_admin
    immediately in the second view's POST, NOT waiting for cron."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"

    req1 = make_cooptation_request()
    app = req1.application
    req2 = make_cooptation_request(application=app)

    # Bring both parrains in as logged-in
    for req in [req1, req2]:
        req.parrain.user.set_password("x")
        req.parrain.user.save()
        ConsentRecord.objects.create(
            member=req.parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
        )

    for req in [req1, req2]:
        c = Client()
        c.login(username=req.parrain.user.username, password="x")
        c.post(f"/cooptation/{req.token}/", {"response": "accepted", "comment": ""})

    app.refresh_from_db()
    assert app.status == "awaiting_admin"
    assert app.cooptation_outcome == "all_accepted"
