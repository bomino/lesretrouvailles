"""Privileged accounts must not carry the member-friendly 90-day session.

Review M5: SESSION_COOKIE_AGE is 90 days with SESSION_SAVE_EVERY_REQUEST, which
is right for a 60-year-old member who checks the directory monthly. It is wrong
for a co-admin or the super-admin, whose session can issue login links for any
member and administer accounts. A stolen laptop stays authorized for a quarter.
"""

from __future__ import annotations

import pytest
from django.test import Client

from alumni.sessions import STAFF_SESSION_AGE


@pytest.mark.django_db
def test_staff_login_gets_a_short_session(make_user):
    user = make_user(username="coadmin", password="pw-secret-1", is_staff=True)
    client = Client()
    assert client.login(username=user.username, password="pw-secret-1")

    expiry = client.session.get_expiry_age()
    assert expiry <= STAFF_SESSION_AGE, "a co-admin must not inherit the 90-day session"
    assert STAFF_SESSION_AGE <= 60 * 60 * 24, "privileged sessions should be <= 1 day"


@pytest.mark.django_db
def test_member_login_keeps_the_long_session(make_user, settings):
    user = make_user(username="22790000123", password="pw-secret-1")
    client = Client()
    assert client.login(username=user.username, password="pw-secret-1")

    expiry = client.session.get_expiry_age()
    assert expiry > STAFF_SESSION_AGE, "ordinary members keep the 90-day sliding session"
