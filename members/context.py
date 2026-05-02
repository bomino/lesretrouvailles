"""Context processor exposing the active member's preferences to templates."""

from __future__ import annotations


def member_preferences(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"member_prefs": None}
    member = getattr(request.user, "member", None)
    if member is None:
        return {"member_prefs": None}
    prefs = getattr(member, "preferences", None)
    return {"member_prefs": prefs}
