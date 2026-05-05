"""The landing 'In Memoriam' card must link, not be a dead <article>."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_anonymous_landing_card_links_to_login_with_next(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # The anchor href must include both the login URL and the next-target.
    assert "/accounts/login/?next=/in-memoriam/" in body


@pytest.mark.django_db
def test_authenticated_landing_card_links_directly(authed_member_client):
    client, _ = authed_member_client
    resp = client.get("/")
    body = resp.content.decode()
    assert 'href="/in-memoriam/"' in body
