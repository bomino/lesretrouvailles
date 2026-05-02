import base64

from django.conf import settings
from django.http import HttpResponse


class BasicAuthMiddleware:
    """Optional HTTP basic-auth gate, used in staging only.

    Activated by setting BASIC_AUTH_REQUIRED=True plus BASIC_AUTH_USERNAME
    and BASIC_AUTH_PASSWORD. Off by default in dev and prod.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.required = getattr(settings, "BASIC_AUTH_REQUIRED", False)
        self.username = getattr(settings, "BASIC_AUTH_USERNAME", "")
        self.password = getattr(settings, "BASIC_AUTH_PASSWORD", "")

    def __call__(self, request):
        if not self.required:
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
