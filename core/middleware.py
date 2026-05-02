import base64

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse

# Paths that bypass the basic-auth gate even when it is on. Used by the Docker
# healthcheck and any future external monitor that cannot send credentials.
BASIC_AUTH_BYPASS_PATHS = ("/health",)


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
