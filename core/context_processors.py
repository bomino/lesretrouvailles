"""Site-wide template context processors."""

from django.conf import settings


def site(_request):
    return {
        "CLOUDFLARE_ANALYTICS_TOKEN": getattr(settings, "CLOUDFLARE_ANALYTICS_TOKEN", ""),
    }
