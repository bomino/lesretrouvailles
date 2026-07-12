"""French error pages + prod logging config (pre-launch review batch).

Every uncaught 404/403/500/CSRF failure used to render Django's bare
English defaults — for a French-speaking 55-65 audience, with no
navigation back. 500.html and 403_csrf.html are rendered by Django
WITHOUT a request (no context processors), so they must be standalone.
"""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_404_renders_french_branded_page(client):
    """/retrait/<bad token>/ is public (whitelisted) and 404s via
    get_object_or_404 — a WhatsApp-forwarded link with a typo lands here."""
    response = client.get("/retrait/deadbeef-nonexistent/")
    assert response.status_code == 404
    body = response.content.decode("utf-8")
    assert "Page introuvable" in body


@pytest.mark.django_db
def test_403_renders_french_page_for_permission_denied(make_user, make_member):
    """A parrain-vouch link opened by the wrong logged-in member raises
    PermissionDenied — the framework fallback must be French."""
    from datetime import timedelta

    from django.utils import timezone

    from cooptation.models import AdminApplication, CooptationRequest

    parrain = make_member()
    app = AdminApplication.objects.create(
        full_name="X Y",
        years_attended=[1980],
        classes=[],
        city="Niamey",
        country="Niger",
        email="c@example.test",
    )
    req = CooptationRequest.objects.create(
        application=app,
        parrain=parrain,
        expires_at=timezone.now() + timedelta(days=14),
    )

    wrong_user = make_user()
    make_member(user=wrong_user)
    client = Client()
    client.force_login(wrong_user)
    response = client.get(f"/cooptation/{req.token}/")
    assert response.status_code == 403
    assert "Accès refusé" in response.content.decode("utf-8")


def test_500_template_is_standalone_and_french():
    """Django's default server_error renders 500.html with an EMPTY context
    (no request, no context processors) — the template must not extend
    base.html or reference any variable."""
    from django.template import loader

    template = loader.get_template("500.html")
    body = template.render({})  # no request on purpose
    assert "Erreur" in body
    assert "base.html" not in str(getattr(template, "origin", ""))


@pytest.mark.django_db
def test_csrf_failure_renders_french_page(db):
    """Long-lived tabs on old Android phones make CSRF failure a
    high-probability event for this audience."""
    client = Client(enforce_csrf_checks=True)
    response = client.post("/inscription/", {})
    assert response.status_code == 403
    body = response.content.decode("utf-8")
    assert "session a expiré" in body or "Session expirée" in body


@pytest.mark.django_db
def test_gestion_403_page_carries_csrf_token_for_logout(make_user, make_member):
    """staff_required used to render gestion/403.html without a request
    context: the logout form's {% csrf_token %} rendered empty, so
    'Se déconnecter' from the 403 page failed with a second CSRF error."""
    user = make_user()
    make_member(user=user)  # authenticated non-staff
    client = Client()
    client.force_login(user)
    client.post("/charte/", {"next": "/"})  # sign the charter to pass consent gate
    response = client.get("/gestion/")
    assert response.status_code == 403
    assert 'name="csrfmiddlewaretoken"' in response.content.decode("utf-8")


def test_logging_config_reaches_console_regardless_of_debug(settings):
    """With no LOGGING dict, django.request ERROR records are discarded
    under DEBUG=False (console handler has RequireDebugTrue; mail_admins
    no-ops on empty ADMINS) — prod 500 tracebacks never reached Railway."""
    logging_conf = settings.LOGGING
    assert logging_conf, "LOGGING must be configured"
    console = logging_conf["handlers"]["console"]
    assert "filters" not in console or "require_debug_true" not in str(console.get("filters"))
    assert "console" in logging_conf["loggers"]["django"]["handlers"]
    assert "console" in logging_conf["root"]["handlers"]


def test_standalone_error_templates_do_not_leak_developer_comments():
    """Django's {# #} comment does NOT span lines: a multi-line one renders its
    own text into the page. In 500.html / 403_csrf.html the comment sits before
    <html>, so the browser hoists it into the body — a user who just hit a 500
    would read developer notes. Use {% comment %} for anything multi-line."""
    from django.template.loader import render_to_string

    for template in ("500.html", "403_csrf.html"):
        html = render_to_string(template, {})
        assert "{#" not in html, f"{template} renders a raw hash-comment"
        assert "ON PURPOSE" not in html, f"{template} leaks its developer comment"
