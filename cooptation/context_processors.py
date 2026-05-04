"""Template context processors for the cooptation app."""

from __future__ import annotations

from django.utils import timezone

from .models import CooptationRequest


def pending_vouches_count(request) -> dict[str, int]:
    """Number of CooptationRequests awaiting the current user's response.

    Returns 0 for anonymous users and for authenticated users without a
    Member profile (e.g., admins). Used by the nav badge in base.html.

    Cost: one indexed query per authenticated request (parrain_id is the
    auto-indexed FK column). At our scale (low hundreds of members, low
    daily request volume) this is negligible. If profiling later flags
    this as a hot spot, memoize on the request object.
    """
    if not request.user.is_authenticated:
        return {"pending_vouches_count": 0}
    member = getattr(request.user, "member", None)
    if member is None:
        return {"pending_vouches_count": 0}
    count = CooptationRequest.objects.filter(
        parrain=member,
        response="pending",
        expires_at__gt=timezone.now(),
    ).count()
    return {"pending_vouches_count": count}
