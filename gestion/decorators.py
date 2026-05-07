"""Auth gate for the /gestion/ console.

Co-admins use is_staff to access /gestion/; /admin/ is locked to is_superuser
in alumni/admin.py. The decorator below is intentionally distinct from
django.contrib.admin.views.decorators.staff_member_required — that one
redirects to /admin/login/, which we want hidden from co-admins.
"""

from __future__ import annotations

from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.template.loader import render_to_string


def staff_required(view_func):
    """Allow only active staff users; otherwise redirect (anon) or 403."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            next_path = request.get_full_path()
            return redirect(f"/accounts/login/?next={next_path}")
        if not (user.is_active and user.is_staff):
            html = render_to_string(
                "gestion/403.html",
                {"request": request},
            )
            return HttpResponseForbidden(html)
        return view_func(request, *args, **kwargs)

    return wrapper
