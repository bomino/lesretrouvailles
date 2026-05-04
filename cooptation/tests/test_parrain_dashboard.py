"""Pending-vouches dashboard at /cooptations-a-valider/ — member-only listing
of CooptationRequests still awaiting a response from the current user."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord

URL = "/cooptations-a-valider/"


@pytest.mark.django_db
def test_anonymous_user_redirects_to_login():
    response = Client().get(URL)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_authenticated_user_without_member_sees_empty_state(make_user):
    """Admin or any auth'd user with no Member profile gets an empty list,
    not a 500 — the view defends with getattr(..., 'member', None)."""
    user = make_user(password="x")
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get(URL)
    assert response.status_code == 200
    assert b"aucune cooptation en attente" in response.content


@pytest.mark.django_db
def test_member_with_zero_pending_sees_empty_state(make_member, make_user):
    user = make_user(password="x")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get(URL)
    assert response.status_code == 200
    assert b"aucune cooptation en attente" in response.content


@pytest.mark.django_db
def test_member_with_pending_sees_candidates_ordered_by_urgency(
    make_cooptation_request, make_application
):
    """Two pending requests for the same parrain — both candidates render,
    soonest-to-expire first."""
    req1 = make_cooptation_request(
        application=make_application(full_name="Aïssa Soumana"),
    )
    parrain = req1.parrain
    # Second request for the SAME parrain, expiring sooner (2 days vs 10 days)
    make_cooptation_request(
        application=make_application(full_name="Boubacar Issoufou"),
        parrain=parrain,
        expires_at=timezone.now() + timedelta(days=2),
    )
    # Push req1 expiry further out so Boubacar's request sorts first
    req1.expires_at = timezone.now() + timedelta(days=10)
    req1.save()

    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=parrain.user.username, password="x")

    response = c.get(URL)
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "Aïssa Soumana" in body
    assert "Boubacar Issoufou" in body
    # Order: Boubacar (expires in 2 days) appears before Aïssa (10 days)
    assert body.index("Boubacar Issoufou") < body.index("Aïssa Soumana")


@pytest.mark.django_db
def test_member_does_not_see_another_members_pending(
    make_cooptation_request, make_member, make_user
):
    """Member B is logged in. The pending request belongs to Member A.
    Dashboard for B must not list A's request — full identity isolation."""
    req_for_a = make_cooptation_request()
    candidate_name = req_for_a.application.full_name

    user_b = make_user(password="x")
    member_b = make_member(user=user_b)
    ConsentRecord.objects.create(
        member=member_b, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )

    c = Client()
    c.login(username=user_b.username, password="x")
    response = c.get(URL)
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert candidate_name not in body
    assert "aucune cooptation en attente" in body


@pytest.mark.django_db
@pytest.mark.parametrize("response_value", ["accepted", "refused"])
def test_already_answered_requests_are_hidden(make_cooptation_request, response_value):
    req = make_cooptation_request()
    req.response = response_value
    req.responded_at = timezone.now()
    req.save()
    candidate_name = req.application.full_name

    parrain = req.parrain
    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )

    c = Client()
    c.login(username=parrain.user.username, password="x")
    response = c.get(URL)
    assert candidate_name not in response.content.decode("utf-8")


@pytest.mark.django_db
def test_expired_requests_are_hidden(make_cooptation_request):
    req = make_cooptation_request()
    req.expires_at = timezone.now() - timedelta(hours=1)
    req.save()
    candidate_name = req.application.full_name

    parrain = req.parrain
    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )

    c = Client()
    c.login(username=parrain.user.username, password="x")
    response = c.get(URL)
    assert candidate_name not in response.content.decode("utf-8")


@pytest.mark.django_db
def test_pending_row_links_to_per_token_vouch_page(make_cooptation_request):
    req = make_cooptation_request()
    parrain = req.parrain
    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )

    c = Client()
    c.login(username=parrain.user.username, password="x")
    response = c.get(URL)
    body = response.content.decode("utf-8")
    assert f'href="/cooptation/{req.token}/"' in body
