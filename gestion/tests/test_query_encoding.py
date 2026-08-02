"""T7 (2026-08-01 review tail): search terms were interpolated into
pagination/filter hrefs as {{ q }} — HTML-escaped but not URL-encoded, so a
query containing &, #, + or % silently truncated or mangled when the operator
clicked page 2 or a filter chip, showing wrong results with no error."""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_memory_list_filter_chips_urlencode_the_query(client, coadmin_user):
    client.force_login(coadmin_user)
    response = client.get("/gestion/souvenirs/", {"q": "a&b"})
    assert "q=a%26b" in response.content.decode()


@pytest.mark.django_db
def test_member_list_pagination_urlencodes_the_query(client, coadmin_user, make_member):
    client.force_login(coadmin_user)
    for _ in range(30):
        make_member(profession="R&D")
    response = client.get("/gestion/membres/", {"q": "R&D"})
    content = response.content.decode()
    assert "page=2" in content, "test needs enough matches to paginate"
    assert "q=R%26D" in content
