"""Views for the membership app."""

from __future__ import annotations

import markdown as _markdown
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.core.validators import validate_email
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django_ratelimit.core import is_ratelimited
from django_ratelimit.decorators import ratelimit

from alumni.cloudinary import get_client, now_timestamp

from .charters import CHARTER_CURRENT_VERSION, get_charter_text
from .forms import NotificationPreferenceForm, ProfileEditForm
from .models import AuditLog, ConsentRecord, Member
from .search import search_members

# Hardcoded suggestion chips rendered in the empty-state when /annuaire/
# returns zero results post-fallback. Tuneable; a future enhancement
# could derive these from top-N city/year counts in real data.
DIRECTORY_EMPTY_STATE_SUGGESTIONS: list[tuple[str, str]] = [
    ("Niamey", "/annuaire/?city=Niamey"),
    ("Zinder", "/annuaire/?city=Zinder"),
    ("Promotion 1983", "/annuaire/?year=1983"),
    ("Tous les membres", "/annuaire/"),
]


def _client_ip(request) -> str:
    """Return the rightmost (= last trusted hop) IP from X-Forwarded-For.

    XFF is a list where each proxy appends what *it* saw as the source. The
    leftmost token is what the client claimed and is attacker-controlled.
    Behind Railway's edge, the rightmost token is the IP Railway actually
    observed — that's the value worth recording on ConsentRecord.ip_address.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


@require_http_methods(["GET", "POST"])
def charter_view(request):
    if request.method == "POST":
        member = getattr(request.user, "member", None)
        if member is not None:
            ConsentRecord.objects.create(
                member=member,
                charter_version=CHARTER_CURRENT_VERSION,
                ip_address=_client_ip(request),
            )
            request.session["consent_ok_for"] = CHARTER_CURRENT_VERSION
        next_url = request.GET.get("next") or request.POST.get("next") or "/"
        if not url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = "/"
        return HttpResponseRedirect(next_url)

    body_html = _markdown.markdown(
        get_charter_text(CHARTER_CURRENT_VERSION),
        extensions=["extra"],
    )
    return render(
        request,
        "members/charter.html",
        {
            "charter_html": body_html,
            "charter_version": CHARTER_CURRENT_VERSION,
            "next": request.GET.get("next", "/"),
        },
    )


def profile_detail_view(request, slug):
    member = get_object_or_404(Member, slug=slug)
    if member.status == "deleted":
        raise Http404
    if member.status == "suspended" and not request.user.is_staff:
        raise Http404
    return render(
        request,
        "members/profile_detail.html",
        {
            "target": member,
            "is_self": getattr(request.user, "member", None) == member,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    member = getattr(request.user, "member", None)
    if member is None:
        raise Http404

    if request.method == "POST":
        old_photo_id = member.photo_public_id
        member_form = ProfileEditForm(request.POST, instance=member)
        prefs_form = NotificationPreferenceForm(request.POST, instance=member.preferences)
        if member_form.is_valid() and prefs_form.is_valid():
            new_photo_id = member_form.cleaned_data.get("photo_public_id", "")
            member_form.save()
            prefs_form.save()
            if old_photo_id and old_photo_id != new_photo_id:
                get_client().delete(old_photo_id)
            messages.success(request, "Profil mis à jour.")
            return HttpResponseRedirect("/profil/")
        # Form invalid — if the failure is photo_public_id, return 400 (security signal).
        if "photo_public_id" in member_form.errors:
            return JsonResponse({"error": "invalid photo path"}, status=400)
    else:
        member_form = ProfileEditForm(instance=member)
        prefs_form = NotificationPreferenceForm(instance=member.preferences)

    return render(
        request,
        "members/profile_edit.html",
        {
            "member_form": member_form,
            "prefs_form": prefs_form,
            "member": member,
            "cloudinary_cloud_name": settings.CLOUDINARY_CLOUD_NAME,
        },
    )


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def cloudinary_sign_view(request):
    if getattr(request, "limited", False):
        return JsonResponse(
            {"error": "rate limit exceeded"},
            status=429,
            headers={"Retry-After": "60"},
        )

    # Staff can upload on behalf of any member by passing member_slug.
    # Regular members always upload to their own folder; the slug field is
    # ignored if the requester is not staff.
    target_slug = (request.POST.get("member_slug") or "").strip()
    if target_slug and request.user.is_staff:
        try:
            target = Member.objects.get(slug=target_slug)
        except (Member.DoesNotExist, ValueError):
            return JsonResponse({"error": "unknown member"}, status=400)
        folder = f"members/{target.slug}/"
    else:
        member = getattr(request.user, "member", None)
        if member is None:
            return JsonResponse({"error": "no member"}, status=400)
        folder = f"members/{member.slug}/"

    timestamp = now_timestamp()
    payload = get_client().sign_upload(folder=folder, timestamp=timestamp)
    return JsonResponse(payload)


@login_required
@require_http_methods(["GET"])
def directory_view(request):
    qs = Member.objects.filter(status="active")

    q = (request.GET.get("q") or "").strip()[:80]
    year_raw = request.GET.get("year")
    city = (request.GET.get("city") or "").strip()
    profession = (request.GET.get("profession") or "").strip()

    if q:
        qs = search_members(qs, q)

    if year_raw:
        try:
            year = int(year_raw)
            if year in range(1980, 1986):
                qs = qs.filter(years_attended__contains=[year])
        except (TypeError, ValueError):
            pass

    if city:
        # show_city=False must actually hide the city: filtering over all
        # members let anyone probe ~6 plausible cities and infer exactly
        # what the privacy toggle promised to hide.
        qs = qs.filter(city__iexact=city, show_city=True)

    if profession:
        qs = qs.filter(profession__icontains=profession)

    # Preserve last_name/first_name ordering UNLESS the search already
    # ranked by trigram similarity (search_members applies its own order
    # in that branch and we don't want to clobber it). Capture the result
    # so the template knows whether to render alphabetical letter section
    # headers (yes when we ordered alphabetically; no when trigram ranked
    # by similarity — the section headers would be misleading there).
    is_alphabetical = not bool(qs.query.order_by)
    if is_alphabetical:
        qs = qs.order_by("last_name", "first_name")

    paginator = Paginator(qs, 20)
    raw_page = request.GET.get("page", "1")
    try:
        page_number = max(1, int(raw_page))
    except (TypeError, ValueError):
        page_number = 1
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(paginator.num_pages or 1)

    # Letter groups for the current page — only meaningful when the result
    # is alphabetically sorted. Each group is {"letter": str, "members": [...]}
    # in document order, with letters derived from last_name's first
    # character (uppercased, accent-stripped via a lightweight map). Members
    # without a last_name fall under "—".
    letter_groups: list[dict] = []
    if is_alphabetical:
        current: dict | None = None
        for member in page.object_list:
            letter = (member.last_name[:1] or "—").upper()
            # Strip common French accents from grouping letter so "Émile"
            # groups under "E" (visual + sort consistency).
            letter = {
                "À": "A",
                "Â": "A",
                "Ä": "A",
                "É": "E",
                "È": "E",
                "Ê": "E",
                "Ë": "E",
                "Î": "I",
                "Ï": "I",
                "Ô": "O",
                "Ö": "O",
                "Ù": "U",
                "Û": "U",
                "Ü": "U",
                "Ç": "C",
            }.get(letter, letter)
            if current is None or current["letter"] != letter:
                current = {"letter": letter, "members": []}
                letter_groups.append(current)
            current["members"].append(member)

    # Active-filter chips: each chip carries a label and a removal URL
    # (the current querystring with that one filter dropped). Empty chips
    # are skipped so the chip strip only shows what's actually applied.
    def _qs_without(*keys_to_drop: str) -> str:
        """Return the current GET querystring with the listed keys removed.
        Used for the chip remove (×) links."""
        params = request.GET.copy()
        for k in keys_to_drop:
            params.pop(k, None)
        params.pop("page", None)  # always reset pagination on filter change
        return params.urlencode()

    # Querystring for the paginator links: every current filter, URL-encoded,
    # minus `page`. The template used to hand-roll '&{{k}}={{v}}', which
    # HTML-escapes instead of URL-encoding — a value like 'M&M' rendered as
    # '&q=M&amp;M' and the browser decoded it into a truncated filter plus a
    # bogus extra param.
    page_qs = _qs_without()

    active_filters: list[dict] = []
    if q:
        active_filters.append({"label": q, "remove_qs": _qs_without("q"), "kind": "q"})
    if year_raw:
        try:
            year_int = int(year_raw)
            if year_int in range(1980, 1986):
                active_filters.append(
                    {
                        "label": f"Promotion {year_int}",
                        "remove_qs": _qs_without("year"),
                        "kind": "year",
                    }
                )
        except (TypeError, ValueError):
            pass
    if city:
        active_filters.append({"label": city, "remove_qs": _qs_without("city"), "kind": "city"})
    if profession:
        active_filters.append(
            {
                "label": profession,
                "remove_qs": _qs_without("profession"),
                "kind": "profession",
            }
        )

    # Total active members in the platform — used in the "X sur Y membres"
    # display when filters are applied. Single COUNT(*), negligible cost.
    total_active_count = Member.objects.filter(status="active").count()

    # Promotion-year quick-pick chips. Six years (1980-1985) is small enough
    # that a horizontal chip row beats a dropdown for tactile mobile UX.
    # The "Toutes" chip clears the year filter; subsequent chips set it.
    # Each chip carries an `is_active` flag so the template can highlight
    # the selected one. Year filter resets pagination on change.
    def _qs_with_year(year_value: str | int | None) -> str:
        params = request.GET.copy()
        params.pop("page", None)
        if year_value is None or year_value == "":
            params.pop("year", None)
        else:
            params["year"] = str(year_value)
        return params.urlencode()

    selected_year = ""
    if year_raw:
        try:
            yr = int(year_raw)
            if yr in range(1980, 1986):
                selected_year = str(yr)
        except (TypeError, ValueError):
            pass

    promotion_chips: list[dict] = [
        {"label": "Toutes", "qs": _qs_with_year(None), "is_active": selected_year == ""}
    ]
    for yr in range(1980, 1986):
        promotion_chips.append(
            {
                "label": str(yr),
                "qs": _qs_with_year(yr),
                "is_active": selected_year == str(yr),
            }
        )

    # "Ma promotion" — for logged-in members with a Member profile, surface
    # a dedicated chip that filters to their first year of attendance. The
    # most common interpretation of "ma promo" in French school contexts.
    my_promotion_year: int | None = None
    if request.user.is_authenticated:
        member_obj = getattr(request.user, "member", None)
        if member_obj and member_obj.years_attended:
            my_promotion_year = min(member_obj.years_attended)

    # Log empty-result queries with a meaningful filter so a future bot
    # decision is data-driven. Only fire when the user actually searched
    # (q or any facet) — empty filters returning zero just means there
    # are no active members yet. The 30/h cap is consumed only by actual
    # log-write attempts (a view-level decorator counted every directory
    # browse, silently dropping legitimate rows) — it exists so an
    # authenticated abuser can't flood the audit table with arbitrary
    # `q` values containing other members' names.
    if (
        paginator.count == 0
        and (q or year_raw or city or profession)
        and not is_ratelimited(
            request,
            group="directory.no_results",
            key="user",
            rate="30/h",
            method="GET",
            increment=True,
        )
    ):
        AuditLog.objects.create(
            actor=request.user,
            action="directory.query.no_results",
            target_type="members.Directory",
            target_id="-",
            metadata={
                "q": q,
                "year": year_raw or "",
                "city": city,
                "profession": profession,
                "actor_username": request.user.username,
            },
        )

    template = (
        "members/directory_list_partial.html"
        if request.headers.get("Hx-Request")
        else "members/directory.html"
    )
    return render(
        request,
        template,
        {
            "page": page,
            "page_qs": page_qs,
            "members": page.object_list,
            "letter_groups": letter_groups,
            "is_alphabetical": is_alphabetical,
            "active_filters": active_filters,
            "promotion_chips": promotion_chips,
            "my_promotion_year": my_promotion_year,
            "my_promotion_qs": (_qs_with_year(my_promotion_year) if my_promotion_year else ""),
            "total_count": paginator.count,
            "total_active_count": total_active_count,
            "empty_state_suggestions": (
                DIRECTORY_EMPTY_STATE_SUGGESTIONS if paginator.count == 0 else []
            ),
        },
    )


from . import emails as members_emails  # noqa: E402
from .models import RemovalRequest  # noqa: E402


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="5/h", method="POST", block=False)
def removal_request_form_view(request, entry_token: str):
    from .models import PublicSearchEntry

    entry = get_object_or_404(PublicSearchEntry, removal_token=entry_token)

    if getattr(request, "limited", False):
        # A bodiless 429 renders as a blank page — give the requester
        # French copy and keep them on the form.
        response = render(
            request,
            "members/removal_request_form.html",
            {"entry": entry, "error": "Trop de demandes — merci de réessayer dans une heure."},
            status=429,
        )
        response["Retry-After"] = "3600"
        return response

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()[:254]
        reason = (request.POST.get("reason") or "").strip()[:200]
        if not email:
            return render(
                request,
                "members/removal_request_form.html",
                {"entry": entry, "error": "Email requis."},
                status=400,
            )
        try:
            validate_email(email)
        except ValidationError:
            # A malformed address used to be persisted, then crash the
            # confirmation send — a 500 after the rows were committed.
            return render(
                request,
                "members/removal_request_form.html",
                {"entry": entry, "error": "Adresse email invalide."},
                status=400,
            )

        rreq = RemovalRequest.objects.create(
            entry=entry,
            requester_email=email,
            reason=reason,
            requester_ip=_client_ip(request),
        )

        from .models import AuditLog

        AuditLog.objects.create(
            actor=None,
            action="ghost.removal.requested",
            target_type="members.RemovalRequest",
            target_id=str(rreq.pk),
            metadata={
                "entry_pk": entry.pk,
                "requester_email": email,
                "reason": reason,
            },
        )
        members_emails.send_removal_confirmation_pending(rreq)
        return HttpResponseRedirect("/retrait/merci/")

    return render(request, "members/removal_request_form.html", {"entry": entry})


@require_http_methods(["GET"])
def removal_request_done_view(request):
    return render(request, "members/removal_request_done.html")


@require_http_methods(["GET"])
def removal_confirm_view(request, confirm_token: str):
    from .models import AuditLog, RemovalRequest

    try:
        rreq = RemovalRequest.objects.select_related("entry").get(confirm_token=confirm_token)
    except RemovalRequest.DoesNotExist:
        return render(request, "members/removal_expired_or_invalid.html", status=200)

    now = timezone.now()

    if rreq.status == "expired":
        return render(request, "members/removal_expired_or_invalid.html", status=200)

    if rreq.status == "confirmed":
        # Idempotent: clicking again shows success without re-running side effects
        return render(
            request,
            "members/removal_confirmed.html",
            {"entry": rreq.entry, "request": rreq},
        )

    # status == "pending_confirmation"
    if rreq.expires_at <= now:
        rreq.status = "expired"
        rreq.save(update_fields=["status"])
        return render(request, "members/removal_expired_or_invalid.html", status=200)

    # Execute the removal — set entry.removed_at, write 2 AuditLog entries,
    # send 2 emails, mark request as confirmed.
    entry = rreq.entry
    entry.removed_at = now
    entry.removed_reason = (rreq.reason or "Retrait demandé par la personne concernée")[:200]
    entry.save(update_fields=["removed_at", "removed_reason"])

    rreq.status = "confirmed"
    rreq.confirmed_at = now
    rreq.save(update_fields=["status", "confirmed_at"])

    AuditLog.objects.create(
        actor=None,
        action="ghost.removal.confirmed",
        target_type="members.RemovalRequest",
        target_id=str(rreq.pk),
        metadata={"requester_email": rreq.requester_email},
    )
    AuditLog.objects.create(
        actor=None,
        action="ghost.removal.executed",
        target_type="members.PublicSearchEntry",
        target_id=str(entry.pk),
        metadata={
            "removal_request_id": rreq.pk,
            "reason_at_request": rreq.reason,
        },
    )

    members_emails.send_removal_completed(rreq)
    members_emails.send_admin_removal_notification(rreq)

    return render(
        request,
        "members/removal_confirmed.html",
        {"entry": entry, "request": rreq},
    )


@require_http_methods(["GET"])
def removal_expired_view(request):
    return render(request, "members/removal_expired_or_invalid.html")
