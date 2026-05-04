import re

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_base_template_has_a11y_baseline(client):
    response = client.get(reverse("landing"))
    html = response.content.decode("utf-8")
    # Normalize whitespace so formatter wrapping doesn't break substring checks.
    normalized = re.sub(r"\s+", " ", html)

    assert response.status_code == 200
    assert '<html lang="fr">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1' in normalized
    assert "output.css" in html
    assert "htmx.min.js" in html


@pytest.mark.django_db
def test_base_template_renders_logo_and_whatsapp_link(client):
    """The header must render the brand logo and a WhatsApp affordance
    (DESIGN.md §Logo). The footer must render the founding-date badge."""
    response = client.get(reverse("landing"))
    html = response.content.decode("utf-8")

    assert "img/logo.png" in html
    assert "Les Retrouvailles" in html
    assert "Rejoindre le groupe WhatsApp" in html
    # Brand tokens are referenced. Accept inline-hex (legacy) OR Tailwind
    # utility class (current); both satisfy the design contract that the
    # WhatsApp affordance and the founding-date badge use brand colors.
    assert "1F6B4F" in html or "whatsapp-green" in html  # whatsapp-green
    assert "C9A227" in html or "ceremonial-gold" in html  # ceremonial-gold
    assert "1ᵉʳ Septembre 2020" in html or "1er Septembre 2020" in html


@pytest.mark.django_db
def test_base_template_blocks_robots_for_member_pages(client):
    """Default behavior: member-facing pages are noindex. The login page
    inherits the base template default and must carry noindex."""
    response = client.get(reverse("account_login"))
    html = response.content.decode("utf-8")
    assert '<meta name="robots" content="noindex"' in html


@pytest.mark.django_db
def test_nav_includes_souvenirs_link_for_authenticated_member(client):
    """Authenticated members see a 'Souvenirs' link in the auth nav
    pointing to /souvenirs/. Anonymous visitors see no auth nav at all,
    so no negative case is needed."""
    from django.contrib.auth import get_user_model

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="navtest@example.test",
        email="navtest@example.test",
        password="x",
    )
    member = Member.objects.create(
        user=user,
        first_name="Nav",
        last_name="Test",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    client.force_login(user)

    response = client.get(reverse("landing"))
    body = response.content.decode("utf-8")
    # Link must appear at least twice (desktop + mobile nav blocks)
    assert body.count("/souvenirs/") >= 2
    assert "Souvenirs" in body
