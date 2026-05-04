"""Context processor `pending_vouches_count` exposes the number of pending
cooptation requests for the current user, used by the nav badge."""

from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.utils import timezone

from cooptation.context_processors import pending_vouches_count


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

    request = RequestFactory().get("/")
    request.user = parrain.user
    assert pending_vouches_count(request) == {"pending_vouches_count": 2}
