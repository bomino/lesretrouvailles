"""Phase 0 — /admin/ is locked to superusers; RGPD purge gated to superuser.

Co-admins promoted to is_staff need to use the new /gestion/ console; they
should NOT be able to wander into the cluttered /admin/ UI we're trying to
hide. And the existing rgpd_purge_action on MemberAdmin must not be exposed
to staff who aren't superusers — it's irreversible.
"""

from __future__ import annotations

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def staff_only_user(db):
    """is_staff=True, is_superuser=False — a co-admin."""
    return User.objects.create_user(
        username="22790000901",
        email="coadmin@example.test",
        password="x",
        is_staff=True,
        is_superuser=False,
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_user(
        username="22790000900",
        email="bomino@example.test",
        password="x",
        is_staff=True,
        is_superuser=True,
    )


# ---------- /admin/ access ----------


@pytest.mark.django_db
def test_admin_redirects_non_superuser_staff(client, staff_only_user):
    """A staff-but-not-superuser hitting /admin/ must be redirected away —
    they don't get to see the admin UI even though is_staff=True."""
    client.force_login(staff_only_user)
    response = client.get("/admin/", follow=False)
    assert response.status_code == 302
    # Django's AdminSite redirects to its own login page when has_permission
    # is False; the URL contains /admin/login/ with a next= param.
    assert "/admin/login/" in response.url


@pytest.mark.django_db
def test_admin_allows_superuser(client, superuser):
    """Bomino (is_superuser=True) keeps full /admin/ access."""
    client.force_login(superuser)
    response = client.get("/admin/", follow=False)
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_index_blocks_non_superuser_staff(client, staff_only_user):
    """The /admin/ index page (the dashboard with all the model links) must
    not render for staff-non-superuser, even if they manage to land there.
    Following redirects, they land on Django's admin login form whose page
    title is "Connexion | Site d'administration de Django"."""
    client.force_login(staff_only_user)
    response = client.get("/admin/", follow=True)
    # The admin index has a "Site administration" / "Administration de site"
    # heading; the login page does not. We assert the login form is what
    # rendered, not the dashboard.
    assert b'name="username"' in response.content
    assert b'name="password"' in response.content


@pytest.mark.django_db
def test_admin_member_changelist_blocks_non_superuser_staff(client, staff_only_user):
    """Even a deep-link into a specific admin model must be denied."""
    client.force_login(staff_only_user)
    response = client.get("/admin/members/member/", follow=False)
    assert response.status_code == 302
    assert "/admin/login/" in response.url


# ---------- RGPD purge gate ----------


@pytest.mark.django_db
def test_rgpd_purge_action_hidden_from_non_superuser_staff(rf, staff_only_user):
    """The MemberAdmin.actions tuple includes rgpd_purge_action; get_actions
    must remove it for staff-non-superuser."""
    from members.admin import MemberAdmin
    from members.models import Member

    request = rf.get("/admin/members/member/")
    request.user = staff_only_user
    member_admin = MemberAdmin(Member, admin.site)
    actions = member_admin.get_actions(request)
    assert "rgpd_purge_action" not in actions


@pytest.mark.django_db
def test_rgpd_purge_action_visible_to_superuser(rf, superuser):
    """Bomino still sees the action and can invoke it."""
    from members.admin import MemberAdmin
    from members.models import Member

    request = rf.get("/admin/members/member/")
    request.user = superuser
    member_admin = MemberAdmin(Member, admin.site)
    actions = member_admin.get_actions(request)
    assert "rgpd_purge_action" in actions
