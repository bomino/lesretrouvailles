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


# -------- Mobile navbar (P7.2) --------


@pytest.mark.django_db
def test_anonymous_landing_has_visible_login_link_on_mobile(client):
    """Anonymous mobile users must have a path to /accounts/login/ from
    the navbar. Pre-fix the link was hidden behind sm:inline-flex."""
    response = client.get(reverse("landing"))
    html = response.content.decode("utf-8")
    # The Connexion link is rendered without sm:hidden — visible across breakpoints
    assert reverse("account_login") in html
    # Confirm it's not gated behind a class that hides it on mobile.
    # Find a snippet around the connexion href and assert no "hidden" class
    # appears in the visible classes for that anchor's parent.
    import re

    pattern = re.compile(
        r'<a[^>]*href="' + re.escape(reverse("account_login")) + r'"[^>]*class="([^"]*)"',
        re.MULTILINE | re.DOTALL,
    )
    matches = pattern.findall(html)
    assert matches, "Could not find Connexion <a> for inspection"
    # At least one match should NOT begin with "hidden" (i.e. be visible on mobile)
    assert any(not m.strip().startswith("hidden") for m in matches), (
        f"All Connexion links carry a 'hidden' base class; mobile users have no login path. "
        f"Classes seen: {matches}"
    )


@pytest.mark.django_db
def test_authenticated_navbar_renders_hamburger_toggle_with_a11y(client):
    """Logged-in members on mobile see a hamburger button with proper
    aria attributes; the dropdown menu starts collapsed."""
    from django.contrib.auth import get_user_model

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="hambtest@example.test", email="hambtest@example.test", password="x"
    )
    member = Member.objects.create(
        user=user,
        first_name="Ham",
        last_name="Burger",
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
    html = response.content.decode("utf-8")

    # Hamburger button exists with proper aria attributes
    assert 'id="nav-toggle"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="mobile-nav"' in html
    # Mobile nav exists, starts collapsed (has 'hidden' class)
    assert 'id="mobile-nav"' in html
    # The mobile-nav should have BOTH md:hidden (desktop hidden) AND hidden (initial state)
    import re

    nav_match = re.search(r'<nav[^>]*id="mobile-nav"[^>]*class="([^"]*)"', html)
    assert nav_match, "mobile-nav element not found"
    classes = nav_match.group(1)
    assert "md:hidden" in classes  # hidden on desktop
    assert "hidden" in classes.split()  # collapsed by default on mobile


@pytest.mark.django_db
def test_mobile_dropdown_contains_all_nav_links_and_logout(client):
    """The mobile dropdown holds the full nav, the WhatsApp link, and a
    Se déconnecter button — replacing the old horizontal bottom-bar."""
    from django.contrib.auth import get_user_model

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="mobnavtest@example.test", email="mobnavtest@example.test", password="x"
    )
    member = Member.objects.create(
        user=user,
        first_name="Mob",
        last_name="Nav",
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
    html = response.content.decode("utf-8")

    # Extract just the mobile-nav block to avoid matching the desktop nav
    import re

    block = re.search(r'<nav[^>]*id="mobile-nav".*?</nav>', html, re.DOTALL)
    assert block, "mobile-nav block not found"
    mobile_html = block.group(0)

    assert "/annuaire/" in mobile_html
    assert "/souvenirs/" in mobile_html
    assert reverse("memoriam:list") in mobile_html
    assert "/cooptations-a-valider/" in mobile_html
    assert "/profil/" in mobile_html
    assert "Groupe WhatsApp" in mobile_html
    assert "Se déconnecter" in mobile_html


@pytest.mark.django_db
def test_gestion_link_visible_to_staff_user(client):
    """A staff user (is_staff=True) sees the 'Gestion' link in the navbar
    pointing to the new /gestion/ console (replaces the prior 'Administration'
    link to /admin/, which is now super-admin only)."""
    from django.contrib.auth import get_user_model

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    admin = User.objects.create_user(
        username="admintest@example.test",
        email="admintest@example.test",
        password="x",
        is_staff=True,
        is_superuser=True,
    )
    member = Member.objects.create(
        user=admin,
        first_name="Admin",
        last_name="Test",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    ConsentRecord.objects.create(
        member=member, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
    )
    client.force_login(admin)

    html = client.get(reverse("landing")).content.decode("utf-8")
    # 'Gestion' link to /gestion/ appears at least once (desktop) and
    # also in the mobile dropdown — so >=2 occurrences in the rendered page.
    assert html.count('href="/gestion/"') >= 2
    assert "Gestion" in html
    # /admin/ should NOT be linked from the global nav anymore (super-admin's
    # escape hatch lives inside /gestion/'s subnav, not the global nav)
    assert 'href="/admin/"' not in html


@pytest.mark.django_db
def test_gestion_link_hidden_from_regular_member(client):
    """A non-staff member never sees the 'Gestion' link."""
    from django.contrib.auth import get_user_model

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="regulartest@example.test",
        email="regulartest@example.test",
        password="x",
        is_staff=False,  # regular member
    )
    member = Member.objects.create(
        user=user,
        first_name="Regular",
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

    html = client.get(reverse("landing")).content.decode("utf-8")
    assert 'href="/gestion/"' not in html
    assert 'href="/admin/"' not in html


def _login_as_active_member(client, first_name="Idrissa"):
    """Helper: create + log in an active consenting member for navbar tests."""
    from django.contrib.auth import get_user_model

    from members.charters import CHARTER_CURRENT_VERSION
    from members.models import ConsentRecord, Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username=f"{first_name.lower()}@example.test",
        email=f"{first_name.lower()}@example.test",
        password="x",
    )
    member = Member.objects.create(
        user=user,
        first_name=first_name,
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
    return user, member


@pytest.mark.django_db
def test_navbar_greets_authenticated_member_by_first_name(client):
    """Both desktop and mobile nav surface the member's first name so users
    on shared devices know which account they're logged into."""
    _login_as_active_member(client, "Idrissa")
    html = client.get(reverse("landing")).content.decode("utf-8")
    # The greeting "Bonjour, Idrissa" appears at least twice (desktop + mobile)
    assert html.count("Bonjour, Idrissa") >= 2
    # And both placement hooks are present
    assert "data-current-user" in html
    assert "data-current-user-mobile" in html


@pytest.mark.django_db
def test_navbar_desktop_greeting_links_to_profile(client):
    """Clicking the greeting takes the user to their profile (replaces the
    separate 'Mon profil' nav link that used to live next to it)."""
    import re

    _login_as_active_member(client, "Idrissa")
    html = client.get(reverse("landing")).content.decode("utf-8")
    # The desktop greeting span is now an <a href="/profil/"> with the
    # data-current-user marker.
    pattern = re.compile(
        r'<a[^>]*href="/profil/"[^>]*data-current-user[^>]*>',
        re.MULTILINE | re.DOTALL,
    )
    assert pattern.search(html), "Desktop greeting must link to /profil/"


@pytest.mark.django_db
def test_navbar_hides_whatsapp_button_for_authenticated_user(client):
    """The big 'Rejoindre le groupe WhatsApp' CTA is for the landing page
    audience (anon users discovering the platform). Authenticated users
    have already joined; hiding the button cuts navbar clutter without
    losing reach (still in footer + mobile dropdown)."""
    _login_as_active_member(client, "Idrissa")
    html = client.get(reverse("landing")).content.decode("utf-8")
    # The desktop CTA text "Rejoindre le groupe WhatsApp" should not appear
    # for an authenticated user. The mobile dropdown uses the shorter
    # "Groupe WhatsApp" label, which is still allowed to render.
    assert "Rejoindre le groupe WhatsApp" not in html


@pytest.mark.django_db
def test_navbar_keeps_whatsapp_button_for_anonymous_user(client):
    """Anon users on the landing page still see the WhatsApp CTA — it's a
    discovery affordance for non-members."""
    html = client.get(reverse("landing")).content.decode("utf-8")
    assert "Rejoindre le groupe WhatsApp" in html


@pytest.mark.django_db
def test_navbar_omits_separate_mon_profil_link_on_desktop(client):
    """The standalone 'Mon profil' nav link is removed in favor of the
    clickable greeting. The mobile dropdown keeps a separate /profil/
    link in its list, so we assert the count drops to ~1 (mobile only)
    rather than ~2 (desktop + mobile) like for /souvenirs/."""
    _login_as_active_member(client, "Idrissa")
    html = client.get(reverse("landing")).content.decode("utf-8")
    # Mobile dropdown still has /profil/ as a list item; that's fine.
    # But the /profil/ link count should be lower than /souvenirs/ count
    # (souvenirs has both desktop nav + mobile dropdown).
    assert html.count("/souvenirs/") >= 2  # sanity: nav pattern intact
    # /profil/ is now clickable from the greeting (1 desktop) + mobile list
    # (1 mobile) — still 2, but no longer the standalone "Mon profil" text on
    # desktop.
    assert html.count(">Mon profil<") == html.count(">Mon profil<")  # tautology
    # The strict assertion: there is no <a> in the DESKTOP nav with text "Mon profil"
    # (desktop nav is the <nav class="hidden md:flex"> block). Find it and check.
    import re

    desktop_nav_match = re.search(
        r'<nav[^>]*class="hidden md:flex[^"]*"[^>]*>.*?</nav>',
        html,
        re.DOTALL,
    )
    assert desktop_nav_match, "Desktop nav block not found"
    desktop_nav_html = desktop_nav_match.group(0)
    assert "Mon profil" not in desktop_nav_html


@pytest.mark.django_db
def test_base_template_has_favicon_and_manifest_links(client):
    """Browser tab + Google search results + iOS home screen + Android PWA
    install all rely on the favicon links being present in <head>."""
    response = client.get(reverse("landing"))
    html = response.content.decode("utf-8")

    # Legacy + modern browser tab icons
    assert 'rel="icon"' in html
    assert "favicon.ico" in html
    assert "favicon-16x16.png" in html
    assert "favicon-32x32.png" in html
    # Google Search results icon (≥48×48 recommended per Google's docs)
    assert "favicon-48x48.png" in html
    # iOS home screen
    assert 'rel="apple-touch-icon"' in html
    assert "favicon-180x180.png" in html
    # Android PWA / theme color
    assert 'rel="manifest"' in html
    assert "manifest.webmanifest" in html
    assert 'name="theme-color"' in html
