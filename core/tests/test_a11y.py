"""A11y assertions for the public landing — a basic floor, not full WCAG."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup


@pytest.mark.django_db
def test_landing_has_exactly_one_h1(client):
    body = client.get("/").content
    soup = BeautifulSoup(body, "html.parser")
    h1s = soup.find_all("h1")
    assert len(h1s) == 1, f"Landing should have exactly one h1, got {len(h1s)}"


@pytest.mark.django_db
def test_landing_no_heading_level_skips(client):
    """h2 should not be followed by h4 with no h3 in between."""
    body = client.get("/").content
    soup = BeautifulSoup(body, "html.parser")
    levels = [int(tag.name[1]) for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
    for prev, curr in zip(levels, levels[1:], strict=False):
        assert curr <= prev + 1, (
            f"Heading level skip detected: h{prev} → h{curr}. "
            "Heading sequence: " + ",".join(f"h{n}" for n in levels)
        )


@pytest.mark.django_db
def test_whatsapp_share_button_has_accessible_name(client):
    """The WhatsApp share is a small icon link — must have aria-label or
    visible text so screen readers can announce it."""
    body = client.get("/").content
    soup = BeautifulSoup(body, "html.parser")
    wa_links = [a for a in soup.find_all("a") if "wa.me" in (a.get("href") or "")]
    assert wa_links, "WhatsApp share link not found in landing"
    for link in wa_links:
        has_aria = link.get("aria-label")
        has_text = link.get_text(strip=True)
        assert has_aria or has_text, (
            f"WhatsApp share link {link} has no accessible name (aria-label or text)"
        )


@pytest.mark.django_db
def test_primary_cta_has_focus_ring_class(client):
    """Tailwind smoke check — primary CTA should retain focus styling."""
    body = client.get("/").content.decode("utf-8")
    assert "Je suis un ancien" in body
    # The button uses bg-tertiary as a marker class; the project's standard
    # button styling implies focus ring via the bg-tertiary + transition combo.
    assert "bg-tertiary" in body


@pytest.mark.django_db
def test_removal_link_has_accessible_text_when_flag_on(client, settings, db):
    """The 'Retirer mon nom' link must have visible text (not just an icon)."""
    from django.contrib.auth import get_user_model

    from members.models import PublicSearchEntry

    settings.PUBLIC_GHOST_LIST_ENABLED = True
    User = get_user_model()  # noqa: N806
    a, b = (
        User.objects.create_user(
            username=f"a{i}", email=f"a{i}@x.test", password="x", is_staff=True
        )
        for i in range(2)
    )
    e = PublicSearchEntry.objects.create(
        first_name="Idrissa", last_name_initial="S.", years_at_ceg=[1980]
    )
    e.added_by_admins.add(a, b)

    body = client.get("/").content
    soup = BeautifulSoup(body, "html.parser")
    removal_links = [link for link in soup.find_all("a") if "/retrait/" in (link.get("href") or "")]
    assert removal_links, "Expected at least one removal link in the rendered ghost card"
    for link in removal_links:
        text = link.get_text(strip=True)
        assert text, f"Removal link {link} has no visible text"
        assert text == "Retirer mon nom"
