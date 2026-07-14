import base64

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse

# Paths that bypass the basic-auth gate even when it is on. Used by the Docker
# healthcheck and any future external monitor that cannot send credentials.
BASIC_AUTH_BYPASS_PATHS = ("/health",)

# P4a: SEO crawlers and anonymous visitors must reach these without
# credentials so the public landing is actually indexable. Exact-match set
# is used for short paths to avoid the trap where prefix-matching "/" would
# bypass every URL in the site.
BASIC_AUTH_PUBLIC_EXACT = {"/", "/sitemap.xml", "/robots.txt"}

# Prefix-matched bypasses for paths with sub-routes. "/inscription/" covers
# both the form and its success page; "/static/" covers all assets.
# Paths that are public in the APP (LOGIN_REQUIRED_WHITELIST) must also be
# public on staging, or staging cannot be used to check the pages an
# anonymous member actually lands on. /aide/ and /guide/ were missing (F-28).
BASIC_AUTH_PUBLIC_PREFIXES = (
    "/static/",
    "/inscription/",
    "/retrait/",
    "/aide/",
    "/guide/",
)


class BasicAuthMiddleware:
    """Optional HTTP basic-auth gate, used in staging only.

    Activated by setting BASIC_AUTH_REQUIRED=True plus BASIC_AUTH_USERNAME
    and BASIC_AUTH_PASSWORD. Off by default in dev and prod.

    If BASIC_AUTH_REQUIRED=True but either credential is empty, raises at
    init-time. Empty credentials would let any caller authenticate with
    `Authorization: Basic Og==` (base64 of `:`), defeating the gate.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.required = getattr(settings, "BASIC_AUTH_REQUIRED", False)
        self.username = getattr(settings, "BASIC_AUTH_USERNAME", "")
        self.password = getattr(settings, "BASIC_AUTH_PASSWORD", "")

        if self.required and (not self.username or not self.password):
            raise ImproperlyConfigured(
                "BASIC_AUTH_REQUIRED=True but BASIC_AUTH_USERNAME or "
                "BASIC_AUTH_PASSWORD is empty. Set both before deploying."
            )

    def __call__(self, request):
        if not self.required:
            return self.get_response(request)

        # Healthchecks and similar external probes cannot send credentials.
        if request.path in BASIC_AUTH_BYPASS_PATHS:
            return self.get_response(request)

        # Public-surface bypass — exact match first, then prefix match.
        # The order matters: prefix-matching "/" against any path would
        # bypass everything on the site.
        if request.path in BASIC_AUTH_PUBLIC_EXACT:
            return self.get_response(request)
        if any(request.path.startswith(p) for p in BASIC_AUTH_PUBLIC_PREFIXES):
            return self.get_response(request)

        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Basic "):
            try:
                creds = base64.b64decode(header[6:]).decode("utf-8")
                user, _, pwd = creds.partition(":")
                if user == self.username and pwd == self.password:
                    return self.get_response(request)
            except (ValueError, UnicodeDecodeError):
                pass

        response = HttpResponse("Authentication required", status=401)
        response["WWW-Authenticate"] = 'Basic realm="Staging"'
        return response
