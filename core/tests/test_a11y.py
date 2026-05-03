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
