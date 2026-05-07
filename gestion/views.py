"""Views for the /gestion/ console.

Phase 1 ships only the dashboard — Phase 2+ adds member-management views,
Phase 3 adds magic-link reissue, Phase 4 adds the cooptation queue."""

from __future__ import annotations

from django.shortcuts import render

from cooptation.models import AdminApplication
from members.models import Member

from .decorators import staff_required


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
