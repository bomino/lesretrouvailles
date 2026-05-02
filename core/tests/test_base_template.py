import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_base_template_has_a11y_baseline(client):
    response = client.get(reverse("landing_placeholder"))
    html = response.content.decode("utf-8")

    assert response.status_code == 200
    assert '<html lang="fr">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1' in html
    assert "output.css" in html
    assert "htmx.min.js" in html


@pytest.mark.django_db
def test_base_template_renders_logo_and_whatsapp_link(client):
    """The header must render the brand logo and a WhatsApp affordance
    (DESIGN.md §Logo). The footer must render the founding-date badge."""
    response = client.get(reverse("landing_placeholder"))
    html = response.content.decode("utf-8")

    assert "img/logo.png" in html
    assert "Les Retrouvailles" in html
    assert "Rejoindre le groupe WhatsApp" in html
    assert "1F6B4F" in html  # whatsapp-green
    assert "C9A227" in html  # ceremonial-gold
    assert "1ᵉʳ Septembre 2020" in html or "1er Septembre 2020" in html


@pytest.mark.django_db
def test_base_template_blocks_robots_for_member_pages(client):
    """Default behavior: pages opt-in to indexing. Landing placeholder
    is NOT yet the public landing — it must be noindex by default."""
    response = client.get(reverse("landing_placeholder"))
    html = response.content.decode("utf-8")
    assert '<meta name="robots" content="noindex"' in html
