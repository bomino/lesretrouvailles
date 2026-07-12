"""Client-IP resolver for django-ratelimit (wired via RATELIMIT_IP_META_KEY).

Behind Railway's edge proxy, REMOTE_ADDR is the proxy address — every real
client shares it, so IP-keyed throttles collapse into one global bucket
(5 signup POSTs from anyone block ALL signups platform-wide). The rightmost
X-Forwarded-For token is the hop Railway actually observed; the leftmost is
whatever the client claimed. Mirrors the `_client_ip` helpers in
cooptation/views.py and members/views.py.
"""

from __future__ import annotations

import ipaddress

from django.core.exceptions import ImproperlyConfigured


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    token = forwarded.rsplit(",", 1)[-1].strip()
    if token:
        try:
            ipaddress.ip_address(token)
        except ValueError:
            pass  # garbage header — fall back to REMOTE_ADDR
        else:
            return token

    remote_addr = request.META.get("REMOTE_ADDR")
    if not remote_addr:
        # Do NOT invent a constant here: every client would bucket into it and
        # the throttles would silently collapse back into one global bucket —
        # the exact bug this resolver exists to fix. django-ratelimit's own
        # _get_ip raises for the same reason.
        raise ImproperlyConfigured(
            "Cannot determine the client IP: no usable X-Forwarded-For token "
            "and REMOTE_ADDR is empty. Rate limits would collapse into a "
            "single shared bucket."
        )
    return remote_addr
