"""Flash-banner scoping (M1 + L2, 2026-08-01 review).

gestion/base.html rendered its memory-worded flash block on EVERY gestion
page: suspending a member showed the correct "Compte suspendu." banner from
member_detail.html PLUS a second banner containing the raw token
`status_suspended`; approving a cooptation showed raw `approved`; and the
`{{ flash }}` fallback reflected arbitrary ?flash= text into a
trusted-looking status banner (content spoofing — escaped, so no XSS).

The memory copy now lives on the memory pages, member_detail owns its
noop/bad_status branches, and no template echoes the raw token.
"""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_member_suspend_flash_shows_one_correct_banner(client, coadmin_user, make_member):
    client.force_login(coadmin_user)
    member = make_member()
    response = client.get(f"/gestion/membres/{member.slug}/?flash=status_suspended")
    content = response.content.decode()
    assert content.count("Compte suspendu.") == 1
    assert "status_suspended" not in content  # raw token no longer leaks


@pytest.mark.django_db
def test_member_noop_and_bad_status_flashes_still_have_copy(client, coadmin_user, make_member):
    """base.html used to cover these two for the member page; member_detail
    must own them now that the shared block is gone."""
    client.force_login(coadmin_user)
    member = make_member()

    response = client.get(f"/gestion/membres/{member.slug}/?flash=noop")
    assert "Aucune modification." in response.content.decode()

    response = client.get(f"/gestion/membres/{member.slug}/?flash=bad_status")
    assert "Statut invalide." in response.content.decode()


@pytest.mark.django_db
def test_arbitrary_flash_text_is_not_reflected(client, coadmin_user, make_member):
    client.force_login(coadmin_user)
    member = make_member()
    response = client.get(f"/gestion/membres/{member.slug}/?flash=Compte+supprim%C3%A9")
    assert "Compte supprimé" not in response.content.decode()

    response = client.get("/gestion/souvenirs/?flash=Compte+supprim%C3%A9")
    assert "Compte supprimé" not in response.content.decode()


@pytest.mark.django_db
def test_memory_list_keeps_memory_flash_copy(client, coadmin_user):
    client.force_login(coadmin_user)
    for token, copy in [
        ("created", "Photo créée."),
        ("updated", "Photo mise à jour."),
        ("published", "Photo publiée."),
        ("unpublished", "Photo dépubliée."),
        ("noop", "Aucune modification."),
        ("bad_status", "Statut invalide."),
    ]:
        response = client.get(f"/gestion/souvenirs/?flash={token}")
        assert copy in response.content.decode(), token


@pytest.mark.django_db
def test_application_flash_shows_single_banner(client, coadmin_user, make_application):
    client.force_login(coadmin_user)
    app = make_application(status="approved")
    response = client.get(f"/gestion/cooptations/{app.pk}/?flash=approved")
    content = response.content.decode()
    assert content.count("Candidature approuvée.") == 1
    # base.html's fallback used to echo the raw token as a second banner.
    assert 'role="status"' not in content or "approved</div>" not in content
