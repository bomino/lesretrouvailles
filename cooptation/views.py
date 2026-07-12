"""Public + token-gated views for the cooptation flow."""

from __future__ import annotations

import logging
import unicodedata
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from members.models import Member

from . import emails
from .forms import SignupForm
from .models import AdminApplication, CooptationRequest

logger = logging.getLogger(__name__)


def _client_ip(request) -> str:
    """Return the rightmost (= last trusted hop) IP from X-Forwarded-For.

    XFF is a list where each proxy appends what *it* saw as the source. The
    leftmost token is what the original client claimed and is therefore
    attacker-controlled. Behind Railway's edge, the rightmost token is the IP
    Railway actually observed — that's the value worth recording on
    AdminApplication.source_ip and the 24h ip_badge admin filter.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[-1].strip()
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
@ratelimit(key="ip", rate="5/h", method="POST", block=False)
def signup_view(request):
    # block=False: a limited candidate gets a French 429 with their typed
    # form re-rendered, not django-ratelimit's bare English 403.
    #
    # An UNBOUND form seeded with the POST data: a bound form would run full
    # validation the moment the template touches field.errors (two parrain
    # lookups + the User-email check — DB work the throttle exists to
    # prevent), and it would show validation errors next to the rate-limit
    # banner, leaving the candidate unable to tell which problem to fix.
    if request.method == "POST" and getattr(request, "limited", False):
        return render(
            request,
            "cooptation/signup.html",
            {"form": SignupForm(initial=request.POST.dict()), "rate_limited": True},
            status=429,
        )
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

            # .filter().first(), not .get(): User.email is not unique and a
            # shared family email would raise MultipleObjectsReturned — a 500
            # for the candidate on a submission the form already validated.
            p1 = (
                Member.objects.filter(
                    user__email=form.cleaned_data["parrain1_email"], status="active"
                )
                .select_related("user")
                .first()
            )
            p2 = (
                Member.objects.filter(
                    user__email=form.cleaned_data["parrain2_email"], status="active"
                )
                .select_related("user")
                .first()
            )
            if p1 is None or p2 is None:
                form.add_error(
                    None,
                    "Parrain inconnu ou inactif. Vérifiez les deux adresses email : "
                    "chaque parrain doit être un membre actif.",
                )
                return render(request, "cooptation/signup.html", {"form": form})

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
                expires = timezone.now() + timedelta(days=14)
                req1 = CooptationRequest.objects.create(
                    application=app, parrain=p1, expires_at=expires
                )
                req2 = CooptationRequest.objects.create(
                    application=app, parrain=p2, expires_at=expires
                )

            # The application is committed; the fan-out below is best-effort.
            # A Resend outage must not 500 a recorded submission — the
            # candidate would resubmit, creating duplicates.
            for send in (
                lambda: emails.send_application_received(app),
                lambda: emails.send_cooptation_requests_sent(
                    app, parrain_emails=[p1.user.email, p2.user.email]
                ),
                lambda: emails.send_parrain_invitation(req1),
                lambda: emails.send_parrain_invitation(req2),
                lambda: emails.send_admin_new_application(app),
            ):
                try:
                    send()
                except Exception:
                    logger.exception("signup: post-commit email failed for application %s", app.pk)

            return HttpResponseRedirect("/inscription/merci/")
    else:
        form = SignupForm()
    return render(request, "cooptation/signup.html", {"form": form})


@require_http_methods(["GET"])
def signup_success_view(request):
    return render(request, "cooptation/signup_success.html")


@login_required
@require_http_methods(["GET"])
def parrain_dashboard_view(request):
    """Member-only listing of CooptationRequests awaiting the current user's
    response. Mirrors the per-token /cooptation/<token>/ page but as an index
    so parrains don't have to dig through email to find pending requests.

    Filters: response='pending' AND expires_at > now AND parrain == me.
    Already-answered or expired requests are hidden — clicking them would
    just hit the 410 page on parrain_vouch_view.
    """
    member = getattr(request.user, "member", None)
    pending = []
    if member is not None:
        pending = list(
            CooptationRequest.objects.filter(
                parrain=member,
                response="pending",
                expires_at__gt=timezone.now(),
            )
            .select_related("application")
            .order_by("expires_at")
        )
    return render(request, "cooptation/parrain_dashboard.html", {"pending": pending})


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

    # The questionnaire exists solely for candidates whose cooptation expired
    # and whose application is still in the review pipeline. Without this gate,
    # an old emailed link could flip a rejected/approved/purged application
    # back to awaiting_admin — silently reversing the admin's decision and
    # escaping the 180-day retention purge (which filters status='rejected').
    #
    # awaiting_admin is deliberately allowed: _sweep_stale_questionnaires
    # moves the application there 7 days after the questionnaire email, and a
    # candidate who answers on day 8 must still be able to — telling them
    # "vos réponses ont déjà été soumises" when they never submitted, and
    # closing their only remaining path in, is not what this gate is for.
    if (
        application.status not in ("cooptation_pending", "awaiting_admin")
        or application.cooptation_outcome != "expired"
    ):
        return render(request, "cooptation/questionnaire_done.html", {"unknown": False}, status=410)

    if application.questionnaire_responses.exists():
        return render(request, "cooptation/questionnaire_done.html", {"unknown": False}, status=410)

    from .models import KnowledgeQuestion, QuestionnaireResponse

    questions = list(KnowledgeQuestion.objects.filter(is_active=True))

    if request.method == "POST":
        try:
            with transaction.atomic():
                for q in questions:
                    answer = (request.POST.get(f"q{q.position}") or "").strip()
                    grade = _grade_closed(answer, q.answer_keys) if q.kind == "closed" else None
                    QuestionnaireResponse.objects.create(
                        application=application,
                        question=q,
                        candidate_answer=answer,
                        auto_grade=grade,
                    )
                application.status = "awaiting_admin"
                application.save()
        except IntegrityError:
            # Double-click race: the second POST passed the exists() check
            # before the first committed, then hit unique_together. The
            # answers WERE saved — show the done page, not a 500.
            pass
        return HttpResponseRedirect(f"/questionnaire/{token}/")

    return render(
        request,
        "cooptation/questionnaire.html",
        {"questions": questions, "application": application},
    )
