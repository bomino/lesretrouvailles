"""Public + token-gated views for the cooptation flow."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
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


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def signup_view(request):
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
