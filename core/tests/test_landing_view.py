"""Tests for the public landing view at /."""

from __future__ import annotations

from urllib.parse import quote

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def authed_member(db, client):
    """Logged-in Member with charter consent — verifies the auth branch keeps existing behavior."""
    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="alice@example.test", email="alice@example.test", password="x"
    )
    member = Member.objects.create(
        user=user,
        first_name="Alice",
        last_name="X",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    client.force_login(user)
    return user


@pytest.fixture
def make_admin(db):
    User = get_user_model()  # noqa: N806
    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "username": f"admin{counter['i']}",
            "email": f"admin{counter['i']}@example.test",
            "password": "x",
            "is_staff": True,
            "is_superuser": True,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    return _make


@pytest.mark.django_db
def test_anonymous_landing_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_landing_overrides_noindex(client):
    body = client.get("/").content.decode("utf-8")
    assert '<meta name="robots" content="index, follow"' in body
    assert '<meta name="robots" content="noindex"' not in body


@pytest.mark.django_db
def test_anonymous_landing_shows_public_ctas(client):
    body = client.get("/").content.decode("utf-8")
    assert "Je suis un ancien" in body
    assert "/inscription/" in body
    assert "Partager sur WhatsApp" in body


@pytest.mark.django_db
def test_anonymous_landing_whatsapp_share_url_carries_utm(client):
    body = client.get("/").content.decode("utf-8")
    assert "wa.me" in body
    assert quote("utm_source=whatsapp") in body or "utm_source%3Dwhatsapp" in body
    assert "invitation" in body


@pytest.mark.django_db
def test_authenticated_landing_shows_member_ctas_not_public(client, authed_member):
    body = client.get("/").content.decode("utf-8")
    assert "Parcourir l'annuaire" in body
    assert "Mon profil" in body
    assert "Je suis un ancien" not in body
    assert "Partager sur WhatsApp" not in body
    # Ghost section is a public-discovery surface, not a member feature.
    assert "Nous recherchons aussi" not in body


@pytest.mark.django_db
def test_ghost_section_hidden_when_flag_off(client, settings):
    settings.PUBLIC_GHOST_LIST_ENABLED = False
    body = client.get("/").content.decode("utf-8")
    assert "Nous recherchons aussi" not in body


@pytest.mark.django_db
def test_ghost_section_hidden_when_flag_on_but_no_entries(client, settings):
    """The empty-state copy ('Liste en cours de constitution') was removed —
    it read as 'under construction' and was off-brand. The section now only
    renders when there are actual published entries to show."""
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    body = client.get("/").content.decode("utf-8")
    assert "Nous recherchons aussi" not in body
    assert "Liste en cours de constitution" not in body


@pytest.mark.django_db
def test_ghost_section_hidden_for_authenticated_user_even_with_entries(
    client, authed_member, settings, make_admin
):
    """Even when the flag is on AND entries are published, an authenticated
    member sees no ghost section — it's a recruitment surface for non-members."""
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin(), make_admin())

    body = client.get("/").content.decode("utf-8")
    assert "Nous recherchons aussi" not in body
    assert "Idrissa" not in body
    assert "Retirer mon nom" not in body


@pytest.mark.django_db
def test_ghost_section_renders_published_entries(client, settings, make_admin):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa",
        last_name_initial="S.",
        years_at_ceg=[1980, 1981, 1982, 1983],
        note="Vivait à Maradi.",
    )
    e.added_by_admins.add(make_admin(), make_admin())

    body = client.get("/").content.decode("utf-8")
    assert "Idrissa" in body
    assert "S." in body
    assert "Vivait à Maradi" in body


@pytest.mark.django_db
def test_ghost_section_hides_single_admin_entries(client, settings, make_admin):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="OnlyOneSignoff", last_name_initial="Z.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(make_admin())  # Only one admin → not published

    body = client.get("/").content.decode("utf-8")
    assert "OnlyOneSignoff" not in body


@pytest.mark.django_db
def test_ghost_section_hides_removed_entries(client, settings, make_admin):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from django.utils import timezone

    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="WasPublished",
        last_name_initial="Y.",
        years_at_ceg=[1980],
    )
    e.added_by_admins.add(make_admin(), make_admin(), make_admin())
    e.removed_at = timezone.now()
    e.save()

    body = client.get("/").content.decode("utf-8")
    assert "WasPublished" not in body


@pytest.mark.django_db
def test_anonymous_feature_cards_not_clickable(client):
    """Annuaire/InMemoriam/Cooptation cards should not be <a> tags for anonymous
    visitors — they lead to gated pages and would frustrate a first-time visitor."""
    body = client.get("/").content.decode("utf-8")
    assert "Annuaire" in body
    assert 'href="/annuaire/"' not in body
    assert 'href="/profil/"' not in body


@pytest.mark.django_db
def test_ghost_card_includes_removal_link_when_flag_on(client, settings, make_admin):
    settings.PUBLIC_GHOST_LIST_ENABLED = True
    from members.models import PublicSearchEntry

    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980, 1981]
    )
    e.added_by_admins.add(make_admin(), make_admin())

    body = client.get("/").content.decode("utf-8")
    assert "Retirer mon nom" in body
    assert f"/retrait/{e.removal_token}/" in body


@pytest.mark.django_db
def test_no_removal_link_when_flag_off(client, settings):
    settings.PUBLIC_GHOST_LIST_ENABLED = False
    body = client.get("/").content.decode("utf-8")
    assert "Retirer mon nom" not in body
