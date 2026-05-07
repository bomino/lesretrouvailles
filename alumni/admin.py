"""Custom AdminSite locked to superusers only.

Co-admins (is_staff=True, is_superuser=False) use the new /gestion/ console;
they should NOT see the cluttered Django admin UI we're hiding from them.
The default AdminSite.has_permission accepts any active staff user; we
tighten it to require is_superuser. Net effect: only the platform owner
(Bomino) sees /admin/.

Wired in via INSTALLED_APPS — replacing 'django.contrib.admin' with
'alumni.admin.GestionAdminConfig' makes admin.site point at the subclass
without touching every app's admin.register decorator.
"""

from __future__ import annotations

from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


class GestionAdminSite(AdminSite):
    def has_permission(self, request):
        return bool(
            request.user.is_active and request.user.is_authenticated and request.user.is_superuser
        )


class GestionAdminConfig(AdminConfig):
    default_site = "alumni.admin.GestionAdminSite"
