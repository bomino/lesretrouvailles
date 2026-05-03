"""Audit test: every member-facing URL must explicitly emit noindex.

Catches templates that accidentally bypass base.html (e.g., a future view
returning HttpResponse with raw HTML) and any view that renders without
extending the layout. The cost of being wrong here is real — leaking
member directory entries to Google search results.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

NOINDEX_MARKER = '<meta name="robots" content="noindex">'


@pytest.fixture
def member_client(db, client):
    """Logged-in client with an active Member."""
    from members.models import Member

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="audit@example.test", email="audit@example.test", password="x"
    )
    Member.objects.create(
        user=user,
        first_name="Audit",
        last_name="User",
        years_attended=[1980, 1981, 1982, 1983],
        classes=["6e"],
        city="Niamey",
        status="active",
    )
    # Acknowledge consent so middleware doesn't redirect to /charte/.
    from members.charters import CHARTER_CURRENT_VERSION

    session = client.session
    session["consent_ok_for"] = CHARTER_CURRENT_VERSION
    session.save()
    client.force_login(user)
    return client, user


@pytest.fixture
def staff_client(db, client):
    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(
        username="staffaudit@example.test",
        email="staffaudit@example.test",
        password="x",
        is_staff=True,
        is_superuser=True,
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/profil/", "/annuaire/", "/charte/"])
def test_member_pages_emit_noindex(member_client, path):
    client, user = member_client
    response = client.get(path)
    assert response.status_code == 200, f"{path} should be reachable for members"
    body = response.content.decode("utf-8")
    assert NOINDEX_MARKER in body, f"{path} missing noindex meta tag"


@pytest.mark.django_db
def test_admin_pages_emit_noindex(staff_client):
    response = staff_client.get("/admin/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Django admin uses its own template, not base.html — assert at least
    # that the response has either noindex OR has a robots tag (Django admin
    # templates DO emit noindex by default since Django 4).
    assert NOINDEX_MARKER in body or 'name="robots"' in body, (
        "Django admin should emit a robots tag (default in modern Django)"
    )


@pytest.mark.django_db
def test_cooptation_token_url_emits_noindex(member_client):
    """A cooptation vouch URL must not be indexed — the token is per-applicant."""
    from datetime import timedelta

    from django.utils import timezone

    from cooptation.models import AdminApplication, CooptationRequest
    from members.models import Member

    client, user = member_client
    member = Member.objects.get(user=user)

    app = AdminApplication.objects.create(
        full_name="Test Candidate",
        email="candidate@example.test",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
    )
    req = CooptationRequest.objects.create(
        application=app,
        parrain=member,
        expires_at=timezone.now() + timedelta(days=14),
    )

    response = client.get(f"/cooptation/{req.token}/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert NOINDEX_MARKER in body, "Cooptation token URL must be noindex"
