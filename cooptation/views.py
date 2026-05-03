"""Public + token-gated views for the cooptation flow."""

from __future__ import annotations

import unicodedata
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from members.models import Member

from . import emails
from .forms import SignupForm
from .models import AdminApplication, CooptationRequest


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


_UTM_FORBIDDEN = str.maketrans("", "", "<>\"'")


def _sanitize_utm(value: str) -> str:
    """Defence-in-depth strip of HTML special chars + control chars, truncated.

    The actual XSS barrier for these values when rendered in the Django admin
    list_filter UI is template auto-escaping — `<` and `&` get escaped to
    entities by `conditional_escape`. This helper just keeps the stored data
    clean so log lines, CSV exports, and future non-Django renderers don't
    have to think about it.
    """
    if not value:
        return ""
    cleaned = value.translate(_UTM_FORBIDDEN)
    cleaned = "".join(c for c in cleaned if c.isprintable())
    return cleaned[:80]


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def signup_view(request):
    # Stash UTM on every GET so a visitor arriving at /inscription/?utm_source=…
    # has it preserved through the form-render → form-submit hop. Sanitization
    # happens here (not at write time) so what's in the session is already safe.
    if request.method == "GET":
        for key in ("utm_source", "utm_campaign"):
            raw = request.GET.get(key)
            if raw:
                request.session[f"signup_{key}"] = _sanitize_utm(raw)

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("website_url"):
                return HttpResponseRedirect("/inscription/merci/")

            with transaction.atomic():
                app = AdminApplication.objects.create(
                    full_name=form.cleaned_data["full_name"],
                    nickname=form.cleaned_data["nickname"],
                    years_attended=form.cleaned_data["years_attended"],
                    classes=form.cleaned_data["classes"],
                    city=form.cleaned_data["city"],
                    country=form.cleaned_data["country"],
                    profession=form.cleaned_data["profession"],
                    email=form.cleaned_data["email"],
                    whatsapp=form.cleaned_data["whatsapp"],
                    source_ip=_client_ip(request),
                    utm_source=request.session.pop("signup_utm_source", ""),
                    utm_campaign=request.session.pop("signup_utm_campaign", ""),
                    referrer=request.META.get("HTTP_REFERER", "")[:512],
                )
                p1 = Member.objects.get(
                    user__email=form.cleaned_data["parrain1_email"], status="active"
                )
                p2 = Member.objects.get(
                    user__email=form.cleaned_data["parrain2_email"], status="active"
                )
                expires = timezone.now() + timedelta(days=14)
                req1 = CooptationRequest.objects.create(
                    application=app, parrain=p1, expires_at=expires
                )
                req2 = CooptationRequest.objects.create(
                    application=app, parrain=p2, expires_at=expires
                )

            emails.send_application_received(app)
            emails.send_cooptation_requests_sent(app, parrain_emails=[p1.user.email, p2.user.email])
            emails.send_parrain_invitation(req1)
            emails.send_parrain_invitation(req2)
            emails.send_admin_new_application(app)

            return HttpResponseRedirect("/inscription/merci/")
    else:
        form = SignupForm()
    return render(request, "cooptation/signup.html", {"form": form})


@require_http_methods(["GET"])
def signup_success_view(request):
    return render(request, "cooptation/signup_success.html")


def _resolve_outcome(application: AdminApplication) -> str:
    """Compute cooptation_outcome from current responses."""
    requests = list(application.cooptation_requests.all())
    responses = [r.response for r in requests]
    if any(r == "pending" for r in responses):
        return "pending"
    accepted = sum(1 for r in responses if r == "accepted")
    refused = sum(1 for r in responses if r == "refused")
    if accepted == len(responses):
        return "all_accepted"
    if refused == len(responses):
        return "all_refused"
    return "mixed"


@login_required
@require_http_methods(["GET", "POST"])
def parrain_vouch_view(request, token: str):
    cooptation_request = get_object_or_404(CooptationRequest, token=token)

    member = getattr(request.user, "member", None)
    if member is None or member.pk != cooptation_request.parrain_id:
        raise PermissionDenied("Cette invitation ne vous est pas adressée.")

    if cooptation_request.response != "pending":
        return render(
            request,
            "cooptation/parrain_vouch_done.html",
            {"request_obj": cooptation_request},
            status=410,
        )

    if cooptation_request.expires_at <= timezone.now():
        return render(
            request,
            "cooptation/parrain_vouch_expired.html",
            {"request_obj": cooptation_request},
            status=410,
        )

    if request.method == "POST":
        from .forms import ParrainVouchForm

        form = ParrainVouchForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                cooptation_request.response = form.cleaned_data["response"]
                cooptation_request.comment = form.cleaned_data["comment"]
                cooptation_request.responded_at = timezone.now()
                cooptation_request.save()

                if cooptation_request.response == "accepted":
                    emails.send_cooptation_accepted(cooptation_request)
                else:
                    emails.send_cooptation_refused(cooptation_request)

                outcome = _resolve_outcome(cooptation_request.application)
                if outcome != "pending":
                    app = cooptation_request.application
                    app.cooptation_outcome = outcome
                    app.status = "awaiting_admin"
                    app.save()

            return HttpResponseRedirect(f"/cooptation/{token}/")
    else:
        from .forms import ParrainVouchForm

        form = ParrainVouchForm()

    return render(
        request,
        "cooptation/parrain_vouch.html",
        {
            "form": form,
            "request_obj": cooptation_request,
            "application": cooptation_request.application,
        },
    )


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _grade_closed(answer: str, keys: list[str]) -> bool:
    haystack = _strip_accents(answer.lower())
    return any(_strip_accents(key.lower()) in haystack for key in keys if key)


@require_http_methods(["GET", "POST"])
def questionnaire_view(request, token: str):
    try:
        application = AdminApplication.objects.get(questionnaire_token=token)
    except AdminApplication.DoesNotExist:
        return render(request, "cooptation/questionnaire_done.html", {"unknown": True}, status=410)

    if application.questionnaire_responses.exists():
        return render(request, "cooptation/questionnaire_done.html", {"unknown": False}, status=410)

    from .models import KnowledgeQuestion, QuestionnaireResponse

    questions = list(KnowledgeQuestion.objects.filter(is_active=True))

    if request.method == "POST":
        with transaction.atomic():
            for q in questions:
                answer = (request.POST.get(f"q{q.position}") or "").strip()
                grade = _grade_closed(answer, q.answer_keys) if q.kind == "closed" else None
                QuestionnaireResponse.objects.create(
                    application=application, question=q, candidate_answer=answer, auto_grade=grade
                )
            application.status = "awaiting_admin"
            application.save()
        return HttpResponseRedirect(f"/questionnaire/{token}/")

    return render(
        request,
        "cooptation/questionnaire.html",
        {"questions": questions, "application": application},
    )
