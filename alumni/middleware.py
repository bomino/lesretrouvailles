"""Project-wide middlewares: login + consent gating."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseRedirect


class LoginRequiredMiddleware:
    """Redirect anonymous users to login for any non-whitelisted path."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.whitelist = list(getattr(settings, "LOGIN_REQUIRED_WHITELIST", []))

    def __call__(self, request):
        if request.user.is_authenticated:
            return self.get_response(request)

        if self._is_whitelisted(request.path):
            return self.get_response(request)

        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
        next_path = request.get_full_path()
        return HttpResponseRedirect(f"{login_url}?next={next_path}")

    def _is_whitelisted(self, path: str) -> bool:
        for entry in self.whitelist:
            # Exact match: "/" matches "/" but not "/admin/"
            if path == entry:
                return True
            # Prefix match: "/accounts/" matches "/accounts/login/"
            if entry.endswith("/") and entry != "/" and path.startswith(entry):
                return True
        return False


class ConsentRequiredMiddleware:
    """Block authenticated users until they accept the current charter version."""

    SKIP_PREFIXES = ("/charte/", "/accounts/logout/", "/cooptation/")
    SESSION_KEY = "consent_ok_for"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if any(request.path.startswith(p) for p in self.SKIP_PREFIXES):
            return self.get_response(request)

        from members.charters import CHARTER_CURRENT_VERSION

        cached = request.session.get(self.SESSION_KEY)
        if cached == CHARTER_CURRENT_VERSION:
            return self.get_response(request)

        member = getattr(request.user, "member", None)
        if member is None:
            # Authenticated user without a Member row (anomaly during P2 dev).
            # Don't loop them; let the view handle it.
            return self.get_response(request)

        from members.models import ConsentRecord

        has_consent = ConsentRecord.objects.filter(
            member=member,
            charter_version=CHARTER_CURRENT_VERSION,
        ).exists()

        if has_consent:
            request.session[self.SESSION_KEY] = CHARTER_CURRENT_VERSION
            return self.get_response(request)

        from urllib.parse import urlencode

        qs = urlencode({"next": request.get_full_path()})
        return HttpResponseRedirect(f"/charte/?{qs}")
