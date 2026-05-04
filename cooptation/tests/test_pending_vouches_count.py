"""Context processor `pending_vouches_count` exposes the number of pending
cooptation requests for the current user, used by the nav badge."""

from datetime import timedelta

import pytest
from django.test import Client, RequestFactory
from django.utils import timezone

from cooptation.context_processors import pending_vouches_count
from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord


@pytest.mark.django_db
def test_returns_zero_for_anonymous_user():
    from django.contrib.auth.models import AnonymousUser

    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    assert pending_vouches_count(request) == {"pending_vouches_count": 0}


@pytest.mark.django_db
def test_returns_zero_for_authenticated_user_without_member(make_user):
    user = make_user()
    request = RequestFactory().get("/")
    request.user = user
    assert pending_vouches_count(request) == {"pending_vouches_count": 0}


@pytest.mark.django_db
def test_returns_correct_count_for_member_with_pending(make_cooptation_request):
    req1 = make_cooptation_request()
    parrain = req1.parrain
    # Second pending request for same parrain
    make_cooptation_request(parrain=parrain)
    # Already-answered: should NOT count
    answered = make_cooptation_request(parrain=parrain)
    answered.response = "accepted"
    answered.save()
    # Expired: should NOT count
    expired = make_cooptation_request(parrain=parrain)
    expired.expires_at = timezone.now() - timedelta(days=1)
    expired.save()
    # Different parrain entirely: should NOT count (verifies parrain= filter)
    make_cooptation_request()  # auto-generates its own fresh parrain

    request = RequestFactory().get("/")
    request.user = parrain.user
    assert pending_vouches_count(request) == {"pending_vouches_count": 2}


@pytest.mark.django_db
def test_nav_includes_dashboard_link_for_authenticated_member(make_member, make_user):
    user = make_user(password="x")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get("/")
    body = response.content.decode("utf-8")
    assert "/cooptations-a-valider/" in body
    assert "Cooptations" in body


@pytest.mark.django_db
def test_nav_badge_renders_when_pending_count_positive(make_cooptation_request):
    req = make_cooptation_request()
    parrain = req.parrain
    parrain.user.set_password("x")
    parrain.user.save()
    ConsentRecord.objects.create(
        member=parrain, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=parrain.user.username, password="x")
    response = c.get("/")
    body = response.content.decode("utf-8")
    # The numeric badge bubble — search for the count followed by closing </span>
    # right after the bg-tertiary rounded-full pill class.
    assert "rounded-full bg-tertiary" in body
    # The aria-label tells screen readers what the badge means.
    assert "1 en attente" in body


@pytest.mark.django_db
def test_nav_badge_absent_when_pending_count_zero(make_member, make_user):
    user = make_user(password="x")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get("/")
    body = response.content.decode("utf-8")
    # Link is present but the count badge bubble is not.
    assert "/cooptations-a-valider/" in body
    assert "rounded-full bg-tertiary" not in body or "en attente" not in body


@pytest.mark.django_db
def test_mobile_nav_includes_dashboard_link(make_member, make_user):
    """The mobile nav (md:hidden block) should also include the dashboard
    link so phone users have parity with desktop."""
    user = make_user(password="x")
    member = make_member(user=user)
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    c = Client()
    c.login(username=user.username, password="x")
    response = c.get("/")
    body = response.content.decode("utf-8")
    # The mobile nav block has the md:hidden class and contains its own links.
    # Count "/cooptations-a-valider/" — must appear at least twice (desktop + mobile).
    assert body.count("/cooptations-a-valider/") >= 2
