"""Template tags that build Cloudinary URLs for Memory photos."""

from __future__ import annotations

from django import template

from alumni.cloudinary import memory_full_url, memory_thumbnail_url

register = template.Library()


@register.simple_tag
def memory_thumb(public_id: str, size: int = 400) -> str:
    return memory_thumbnail_url(public_id, size=size)


@register.simple_tag
def memory_full(public_id: str, max_width: int = 1200) -> str:
    return memory_full_url(public_id, max_width=max_width)
