"""Auth gate for the /gestion/ console.

Co-admins use is_staff to access /gestion/; /admin/ is locked to is_superuser
in alumni/admin.py. The decorator below is intentionally distinct from
django.contrib.admin.views.decorators.staff_member_required — that one
redirects to /admin/login/, which we want hidden from co-admins.
"""

from __future__ import annotations

from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import redirect, render


def staff_required(view_func):
    """Allow only active staff users; otherwise redirect (anon) or 403."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            qs = urlencode({"next": request.get_full_path()})
            return redirect(f"/accounts/login/?{qs}")
        if not (user.is_active and user.is_staff):
            # render() (not render_to_string with request-as-variable) so the
            # full RequestContext applies: without it the csrf token in
            # base.html's logout form rendered empty and logging out from
            # the 403 page failed with a second CSRF error.
            return render(request, "gestion/403.html", status=403)
        return view_func(request, *args, **kwargs)

    return wrapper
