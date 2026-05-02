"""Views for the membership app."""

from __future__ import annotations

import markdown as _markdown
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from alumni.cloudinary import get_client, now_timestamp

from .charters import CHARTER_CURRENT_VERSION, get_charter_text
from .forms import NotificationPreferenceForm, ProfileEditForm
from .models import ConsentRecord, Member


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
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
        member_form = ProfileEditForm(request.POST, instance=member)
        prefs_form = NotificationPreferenceForm(request.POST, instance=member.preferences)
        if member_form.is_valid() and prefs_form.is_valid():
            old_photo_id = member.photo_public_id
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
        {"member_form": member_form, "prefs_form": prefs_form, "member": member},
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

    member = getattr(request.user, "member", None)
    if member is None:
        return JsonResponse({"error": "no member"}, status=400)

    folder = f"members/{member.slug}/"
    timestamp = now_timestamp()
    payload = get_client().sign_upload(folder=folder, timestamp=timestamp)
    return JsonResponse(payload)
