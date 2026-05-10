"""Views for the /gestion/ console.

Phase 1 ships the dashboard. Phase 2 adds the member directory and
edit/suspend/reactivate flows. Phase 3 adds magic-link reissue. Phase 4
will add the cooptation queue."""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

from django.contrib.postgres.lookups import Unaccent
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import F, Q, Value
from django.db.models.functions import Lower
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from cooptation.models import AdminApplication, CooptationRequest, QuestionnaireResponse
from cooptation.services import (
    _build_password_set_url,
    approve_application,
    reject_application,
)
from members.models import AuditLog, Member
from memoires.models import Memory

from .decorators import staff_required
from .forms import (
    ApplicationRejectForm,
    GestionMemoryForm,
    MemberAdminEditForm,
    MemberUsernameChangeForm,
)

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
STATUS_FILTERS = ("active", "suspended", "all")

# wa.me only resolves digits-only WhatsApp numbers (E.164 without +).
# Used by member_login_link_view to suppress the share button for users
# whose username is an email or admin handle.
WA_ME_USERNAME_RE = re.compile(r"^\d{8,15}$")


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


@staff_required
@require_http_methods(["GET", "POST"])
def member_login_link_view(request, slug):
    """Regenerate a 7-day allauth password-reset URL for the member.

    GET shows a confirmation page (no link generated). POST issues a fresh
    URL, writes an audit row, and renders a display page with the URL,
    a "Copier" button, and a wa.me share button so the operator can DM
    it through WhatsApp without leaving the platform."""
    member = get_object_or_404(
        Member.objects.select_related("user"),
        slug=slug,
    )

    link_url: str | None = None
    wa_me_url: str | None = None

    if request.method == "POST":
        link_url = _build_password_set_url(member.user)
        # wa.me only resolves digits-only WhatsApp numbers. Prefer the explicit
        # member.whatsapp field; fall back to User.username if it happens to
        # match the digits format (legacy path for imported members before the
        # migration ran). Otherwise hide the button rather than send the
        # operator to api.whatsapp.com's "phone number invalid" page.
        wa_target = member.whatsapp or member.user.username
        if WA_ME_USERNAME_RE.fullmatch(wa_target):
            wa_me_url = _build_wa_me_share_url(member, link_url, wa_target)
        AuditLog.objects.create(
            actor=request.user,
            action="gestion.login_link.reissued",
            target_type="members.Member",
            target_id=str(member.pk),
            metadata={
                "target_username": member.user.username,
                "member_full_name": member.full_name,
            },
        )

    return render(
        request,
        "gestion/member_login_link.html",
        {
            "member": member,
            "link_url": link_url,
            "wa_me_url": wa_me_url,
        },
    )


APPLICATION_STATUS_FILTERS = ("awaiting_admin", "pending", "all")


@staff_required
@require_http_methods(["GET"])
def application_list_view(request):
    """Cooptation queue. Default filter: 'awaiting_admin' (the actionable
    set). 'pending' adds applications still in cooptation. 'all' shows
    everything except purged ones."""
    status = request.GET.get("status", "awaiting_admin")
    if status not in APPLICATION_STATUS_FILTERS:
        status = "awaiting_admin"

    qs = AdminApplication.objects.exclude(status="purged")
    if status == "awaiting_admin":
        qs = qs.filter(status="awaiting_admin")
    elif status == "pending":
        qs = qs.filter(status__in=("awaiting_admin", "cooptation_pending"))
    qs = qs.order_by("-submitted_at")

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
        "gestion/application_list.html",
        {
            "page": page,
            "applications": page.object_list,
            "status": status,
        },
    )


@staff_required
@require_http_methods(["GET"])
def application_detail_view(request, pk):
    application = get_object_or_404(AdminApplication, pk=pk)
    cooptation_requests = (
        CooptationRequest.objects.filter(application=application)
        .select_related("parrain", "parrain__user")
        .order_by("expires_at")
    )
    questionnaire_responses = (
        QuestionnaireResponse.objects.filter(application=application)
        .select_related("question")
        .order_by("question__position")
    )
    reject_form = ApplicationRejectForm()
    return render(
        request,
        "gestion/application_detail.html",
        {
            "application": application,
            "cooptation_requests": cooptation_requests,
            "questionnaire_responses": questionnaire_responses,
            "reject_form": reject_form,
        },
    )


@staff_required
@require_http_methods(["POST"])
def application_approve_view(request, pk):
    application = get_object_or_404(AdminApplication, pk=pk)
    approve_application(application, reviewed_by=request.user)
    AuditLog.objects.create(
        actor=request.user,
        action="gestion.application.approved",
        target_type="cooptation.AdminApplication",
        target_id=str(application.pk),
        metadata={
            "candidate_full_name": application.full_name,
            "candidate_email": application.email,
        },
    )
    return HttpResponseRedirect(
        reverse("gestion:application_detail", kwargs={"pk": application.pk}) + "?flash=approved"
    )


@staff_required
@require_http_methods(["POST"])
def application_reject_view(request, pk):
    application = get_object_or_404(AdminApplication, pk=pk)
    form = ApplicationRejectForm(request.POST)
    if not form.is_valid():
        # Re-render the detail page with the error inline so the operator
        # doesn't lose context. Reuse the detail context-builder to keep
        # parrain panels + questionnaire responses visible.
        cooptation_requests = (
            CooptationRequest.objects.filter(application=application)
            .select_related("parrain", "parrain__user")
            .order_by("expires_at")
        )
        questionnaire_responses = (
            QuestionnaireResponse.objects.filter(application=application)
            .select_related("question")
            .order_by("question__position")
        )
        return render(
            request,
            "gestion/application_detail.html",
            {
                "application": application,
                "cooptation_requests": cooptation_requests,
                "questionnaire_responses": questionnaire_responses,
                "reject_form": form,
                "show_reject_form": True,
            },
        )

    reason = form.cleaned_data["reason"]
    reject_application(application, reviewed_by=request.user, note=reason)
    AuditLog.objects.create(
        actor=request.user,
        action="gestion.application.rejected",
        target_type="cooptation.AdminApplication",
        target_id=str(application.pk),
        metadata={
            "candidate_full_name": application.full_name,
            "reviewer_note": reason,
        },
    )
    return HttpResponseRedirect(
        reverse("gestion:application_detail", kwargs={"pk": application.pk}) + "?flash=rejected"
    )


def _build_wa_me_share_url(member, link_url: str, wa_number: str) -> str:
    """Build a wa.me deep link with the magic-link reissue Template 3
    (docs/runbooks/onboarding.md:114-121) pre-filled in the WhatsApp
    composer. The operator clicks → WhatsApp opens with the message
    drafted to the member's number → press Send.

    `wa_number` is the digits-only target (already validated by the caller)
    — usually member.whatsapp; for legacy imported rows pre-migration we
    fall back to member.user.username."""
    message = (
        f"Salut {member.first_name},\n"
        "Voici ton nouveau lien de connexion (valable 7 jours) :\n"
        "\n"
        f"{link_url}\n"
        "\n"
        "Choisis ton nouveau mot de passe en suivant le lien."
    )
    return f"https://wa.me/{wa_number}?text={quote(message)}"


def _redirect_to_detail(member, flash: str, changed: list | None = None):
    url = reverse("gestion:member_detail", kwargs={"slug": member.slug})
    sep = "&" if "?" in url else "?"
    parts = [f"flash={flash}"]
    if changed:
        parts.append("changed=" + ",".join(changed))
    return HttpResponseRedirect(f"{url}{sep}{'&'.join(parts)}")


PAGE_SIZE_MEMORY = 12  # photo grid — distinct from PAGE_SIZE = 20 for text-heavy lists

MEMORY_STATUS_FILTERS = ("all", "published", "draft")


@staff_required
@require_http_methods(["GET"])
def memory_list_view(request):
    """Grid of memories with status filter, q search, pagination."""
    status = request.GET.get("status", "all")
    if status not in MEMORY_STATUS_FILTERS:
        status = "all"

    qs = Memory.objects.all()
    if status != "all":
        qs = qs.filter(status=status)

    q = (request.GET.get("q") or "").strip()[:80]
    if q:
        needle = Lower(Unaccent(Value(q)))
        qs = qs.annotate(
            caption_lc=Lower(Unaccent(F("caption"))),
            location_lc=Lower(Unaccent(F("location"))),
        ).filter(Q(caption_lc__contains=needle) | Q(location_lc__contains=needle))

    # Curation-recency-first ordering: gestion admins want to see what was
    # just uploaded (-created_at), THEN by photo era (taken_at DESC NULLS LAST).
    # This deliberately diverges from Memory.Meta.ordering — the public
    # /souvenirs/ gallery keeps the era-first storytelling order; /gestion/
    # curation uses recency-first per spec §G locked decisions.
    qs = qs.order_by("-created_at", F("taken_at").desc(nulls_last=True))

    paginator = Paginator(qs, PAGE_SIZE_MEMORY)
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
        "gestion/memory_list.html",
        {
            "page": page,
            "memories": page.object_list,
            "q": q,
            "status": status,
            "filter_chips": [
                ("all", "Toutes"),
                ("published", "Publiées"),
                ("draft", "Brouillons"),
            ],
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def memory_create_view(request):
    """Create a new Memory. Upload goes through Cloudinary first; DB write +
    AuditLog are atomic. Redirects to list with ?flash=created on success."""
    from django.db import transaction

    from alumni.cloudinary import get_client

    if request.method == "POST":
        form = GestionMemoryForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["upload"]
            client = get_client()
            try:
                new_public_id = client.upload_file(upload, folder="memoires")
            except Exception as exc:  # noqa: BLE001
                form.add_error(
                    "upload",
                    "Échec du téléversement. Vérifiez votre connexion et réessayez.",
                )
                logger.warning(
                    "memory_create_view: Cloudinary upload failed: %s", exc, exc_info=True
                )
            else:
                if not new_public_id:
                    raise RuntimeError("Cloudinary returned empty public_id; refusing to write")
                with transaction.atomic():
                    memory = Memory.objects.create(
                        photo_public_id=new_public_id,
                        caption=form.cleaned_data["caption"],
                        taken_at=form.cleaned_data["taken_at"] or None,
                        location=form.cleaned_data["location"] or "",
                        status=form.cleaned_data["status"],
                        created_by=request.user,
                    )
                    AuditLog.objects.create(
                        actor=request.user,
                        action="memoires.memory.created",
                        target_type="memoires.Memory",
                        target_id=str(memory.pk),
                        metadata={
                            "caption_preview": memory.caption[:60],
                            "location": memory.location,
                            "taken_at": memory.taken_at.isoformat() if memory.taken_at else None,
                            "public_id": memory.photo_public_id,
                            "initial_status": memory.status,
                        },
                    )
                return HttpResponseRedirect("/gestion/souvenirs/?flash=created")
    else:
        form = GestionMemoryForm()

    return render(
        request,
        "gestion/memory_edit.html",
        {
            "form": form,
            "memory": None,  # signals create mode to the template
        },
    )


@staff_required
def memory_edit_view(request, pk):
    """Stub — fleshed out in Task 6 (memory_edit_view)."""
    return HttpResponse(status=501)


@staff_required
def memory_status_view(request, pk):
    """Stub — fleshed out in Task 7 (memory_status_view)."""
    return HttpResponse(status=501)
