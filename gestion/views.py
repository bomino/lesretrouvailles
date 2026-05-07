"""Views for the /gestion/ console.

Phase 1 ships the dashboard. Phase 2 adds the member directory and
edit/suspend/reactivate flows. Phase 3 will add magic-link reissue.
Phase 4 will add the cooptation queue."""

from __future__ import annotations

from django.contrib.postgres.lookups import Unaccent
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import F, Q, Value
from django.db.models.functions import Lower
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from cooptation.models import AdminApplication
from members.models import AuditLog, Member

from .decorators import staff_required
from .forms import MemberAdminEditForm, MemberUsernameChangeForm

PAGE_SIZE = 20
STATUS_FILTERS = ("active", "suspended", "all")


@staff_required
def dashboard_view(request):
    """Landing page — KPI tiles + nav to the section pages."""
    kpis = {
        "active_members": Member.objects.filter(status="active").count(),
        "suspended_members": Member.objects.filter(status="suspended").count(),
        "pending_cooptations": AdminApplication.objects.filter(
            status__in=("cooptation_pending", "awaiting_admin")
        ).count(),
    }
    return render(request, "gestion/dashboard.html", {"kpis": kpis})


@staff_required
@require_http_methods(["GET"])
def member_list_view(request):
    """Searchable member directory. Filter by status, search by name/phone/city."""
    status = request.GET.get("status", "active")
    if status not in STATUS_FILTERS:
        status = "active"

    qs = Member.objects.select_related("user").exclude(status="deleted")
    if status != "all":
        qs = qs.filter(status=status)

    q = (request.GET.get("q") or "").strip()[:80]
    if q:
        needle = Lower(Unaccent(Value(q)))
        qs = qs.annotate(
            first_lc=Lower(Unaccent(F("first_name"))),
            last_lc=Lower(Unaccent(F("last_name"))),
            nick_lc=Lower(Unaccent(F("nickname"))),
            city_lc=Lower(Unaccent(F("city"))),
        ).filter(
            Q(first_lc__contains=needle)
            | Q(last_lc__contains=needle)
            | Q(nick_lc__contains=needle)
            | Q(city_lc__contains=needle)
            | Q(user__username__icontains=q)
            | Q(user__email__icontains=q)
        )

    qs = qs.order_by("last_name", "first_name")

    paginator = Paginator(qs, PAGE_SIZE)
    raw_page = request.GET.get("page", "1")
    try:
        page_number = max(1, int(raw_page))
    except (TypeError, ValueError):
        page_number = 1
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.page(paginator.num_pages or 1)

    return render(
        request,
        "gestion/member_list.html",
        {
            "page": page,
            "members": page.object_list,
            "q": q,
            "status": status,
        },
    )


@staff_required
@require_http_methods(["GET"])
def member_detail_view(request, slug):
    member = get_object_or_404(
        Member.objects.select_related("user"),
        slug=slug,
    )
    return render(request, "gestion/member_detail.html", {"member": member})


@staff_required
@require_http_methods(["GET", "POST"])
def member_edit_view(request, slug):
    member = get_object_or_404(
        Member.objects.select_related("user"),
        slug=slug,
    )

    if request.method == "POST":
        form = MemberAdminEditForm(request.POST, instance=member)
        if form.is_valid():
            changed = form.save_with_audit(actor=request.user)
            return _redirect_to_detail(member, flash="updated", changed=changed)
    else:
        form = MemberAdminEditForm(instance=member)

    return render(
        request,
        "gestion/member_edit.html",
        {"member": member, "form": form},
    )


@staff_required
@require_http_methods(["POST"])
def member_status_view(request, slug):
    member = get_object_or_404(Member, slug=slug)
    target = request.POST.get("target_status", "").strip()

    if target not in ("active", "suspended"):
        return _redirect_to_detail(member, flash="bad_status")

    if member.status == target:
        return _redirect_to_detail(member, flash="noop")

    member.status = target
    member.save(update_fields=["status", "updated_at"])

    action = "gestion.member.suspended" if target == "suspended" else "gestion.member.reactivated"
    AuditLog.objects.create(
        actor=request.user,
        action=action,
        target_type="members.Member",
        target_id=str(member.pk),
        metadata={
            "member_full_name": member.full_name,
            "previous_status": "active" if target == "suspended" else "suspended",
        },
    )

    return _redirect_to_detail(member, flash=f"status_{target}")


@staff_required
@require_http_methods(["GET", "POST"])
def member_username_view(request, slug):
    """Confirm-the-old-number flow for changing User.username."""
    member = get_object_or_404(
        Member.objects.select_related("user"),
        slug=slug,
    )

    if request.method == "POST":
        form = MemberUsernameChangeForm(request.POST, member=member)
        if form.is_valid():
            form.save_with_audit(actor=request.user)
            return _redirect_to_detail(member, flash="username_changed")
    else:
        form = MemberUsernameChangeForm(member=member)

    return render(
        request,
        "gestion/member_username.html",
        {"member": member, "form": form},
    )


def _redirect_to_detail(member, flash: str, changed: list | None = None):
    url = reverse("gestion:member_detail", kwargs={"slug": member.slug})
    sep = "&" if "?" in url else "?"
    parts = [f"flash={flash}"]
    if changed:
        parts.append("changed=" + ",".join(changed))
    return HttpResponseRedirect(f"{url}{sep}{'&'.join(parts)}")
