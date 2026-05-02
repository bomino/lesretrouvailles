"""Template tag rendering a member avatar (photo or deterministic initials)."""

from __future__ import annotations

import hashlib

from django import template
from django.template.loader import render_to_string

from alumni.cloudinary import member_thumbnail_url

register = template.Library()


def initials_for_member(member) -> str:
    first = (member.first_name or "")[:1]
    last = (member.last_name or "")[:1]
    return f"{first}{last}".upper()


def avatar_hue_for_slug(slug: str) -> int:
    digest = hashlib.md5(str(slug).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 360


@register.simple_tag(takes_context=True)
def member_avatar(context, member, size: int = 240, force_initials: bool = False) -> str:
    # Honor viewer's data-saver preference (spec §10) — exposed by the
    # members.context.member_preferences context processor.
    prefs = context.get("member_prefs")
    data_saver = bool(prefs and prefs.data_saver)
    use_image = bool(member.photo_public_id) and not force_initials and not data_saver
    return render_to_string(
        "members/_avatar.html",
        {
            "member": member,
            "size": size,
            "use_image": use_image,
            "image_url": member_thumbnail_url(member.photo_public_id, size=size)
            if use_image
            else "",
            "initials": initials_for_member(member),
            "hue": avatar_hue_for_slug(str(member.slug)),
        },
    )
