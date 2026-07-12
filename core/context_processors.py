"""Site-wide template context processors."""

from django.conf import settings


def site(_request):
    return {
        "CLOUDFLARE_ANALYTICS_TOKEN": getattr(settings, "CLOUDFLARE_ANALYTICS_TOKEN", ""),
        # Empty until the operator sets WHATSAPP_GROUP_URL; templates hide the
        # "Groupe WhatsApp" links while it is blank rather than link nowhere.
        "whatsapp_group_url": getattr(settings, "WHATSAPP_GROUP_URL", ""),
    }
