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
    return request.META.get("REMOTE_ADDR", "0.0.0.0")
