import time

from django.contrib import admin, messages
from django.contrib.messages.api import MessageFailure
from django.utils.html import format_html

from . import services
from .emails import send_application_approved
from .models import AdminApplication, CooptationRequest, KnowledgeQuestion, QuestionnaireResponse


class CooptationRequestInline(admin.TabularInline):
    model = CooptationRequest
    extra = 0
    readonly_fields = (
        "parrain",
        "response",
        "responded_at",
        "comment",
        "expires_at",
        "reminder_sent_at",
    )
    can_delete = False


class QuestionnaireResponseInline(admin.TabularInline):
    model = QuestionnaireResponse
    extra = 0
    readonly_fields = ("question", "candidate_answer", "auto_grade", "submitted_at")
    can_delete = False


@admin.register(AdminApplication)
class AdminApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "city",
        "status",
        "cooptation_outcome",
        "submitted_at",
        "ip_badge",
    )
    list_filter = ("status", "cooptation_outcome", "country", "utm_source", "utm_campaign")
    search_fields = ("full_name", "email", "nickname")
    # `status` is read-only on purpose: a free select let an operator set
    # rejected/purged by hand, skipping reject_application (no rejected_at /
    # retention_until, so the 180-day purge never matched) or purge() (PII
    # kept under a "purged" label). Every transition goes through an action.
    readonly_fields = (
        "status",
        "submitted_at",
        "reviewed_by",
        "rejected_at",
        "retention_until",
        "purged_at",
        "source_ip",
        "questionnaire_token",
    )
    inlines = [CooptationRequestInline, QuestionnaireResponseInline]
    actions = ["approve_action", "reject_action", "requeue_action", "resend_password_link_action"]

    def get_queryset(self, request):
        """Annotate the 24h same-IP count once for the whole changelist —
        ip_badge used to fire one COUNT query per rendered row."""
        from datetime import timedelta

        from django.db.models import Count, OuterRef, Subquery
        from django.utils import timezone

        recent_qs = (
            AdminApplication.objects.filter(
                source_ip=OuterRef("source_ip"),
                submitted_at__gte=timezone.now() - timedelta(hours=24),
            )
            .values("source_ip")
            .annotate(n=Count("pk"))
            .values("n")
        )
        return super().get_queryset(request).annotate(recent_ip_count=Subquery(recent_qs))

    @admin.display(description="IP")
    def ip_badge(self, obj):
        if not obj.source_ip:
            return ""
        recent = getattr(obj, "recent_ip_count", None) or 0
        if recent >= 3:
            return format_html(
                '<span title="{} demandes en 24h">🚩 {}</span>', recent, obj.source_ip
            )
        return obj.source_ip

    def message_user(
        self, request, message, level=messages.INFO, extra_tags="", fail_silently=False
    ):
        try:
            super().message_user(
                request, message, level=level, extra_tags=extra_tags, fail_silently=fail_silently
            )
        except (TypeError, MessageFailure):
            # Plumbing-only tolerance: CLI/smoke callers pass bare fake
            # request objects (not HttpRequest → TypeError) or requests
            # without the messages middleware (→ MessageFailure). The old
            # blanket `except Exception` also discarded real per-row
            # warnings, letting an admin believe a bulk approve fully
            # succeeded when rows were refused. Anything else propagates.
            pass

    @admin.action(description="Approuver les candidatures sélectionnées")
    def approve_action(self, request, queryset):
        from members.models import AuditLog

        approved = 0
        for app in queryset:
            try:
                services.approve_application(app, reviewed_by=request.user)
            except services.ApprovalError as exc:
                self.message_user(
                    request, f"Candidature {app.pk} non approuvée : {exc}", messages.WARNING
                )
            else:
                approved += 1
                # The /gestion/ path writes gestion.application.approved; this
                # bulk path wrote nothing — the only trace was mutable row
                # state (reviewed_by), thinner than the audit conventions.
                AuditLog.objects.create(
                    actor=request.user,
                    action="cooptation.application.approved",
                    target_type="cooptation.AdminApplication",
                    target_id=str(app.pk),
                    metadata={
                        "candidate_full_name": app.full_name,
                        "candidate_email": app.email,
                    },
                )
        self.message_user(request, f"{approved} candidature(s) approuvée(s).", messages.SUCCESS)

    @admin.action(description="Rejeter les candidatures sélectionnées")
    def reject_action(self, request, queryset):
        # The changelist action POST carries no reason field — no admin UI
        # ever supplied one, so a request.POST.get("reason") read here was
        # dead code implying a per-rejection-reason feature that doesn't
        # exist. This bulk action is explicitly generic; reasoned rejections
        # go through /gestion/ (ApplicationRejectForm), whose note reaches
        # the candidate's rejection email.
        reason = "Demande non éligible"
        from members.models import AuditLog

        rejected = 0
        for app in queryset:
            try:
                services.reject_application(app, reviewed_by=request.user, note=reason)
            except services.ApplicationStateError as exc:
                self.message_user(
                    request, f"Candidature {app.pk} non rejetée : {exc}", messages.WARNING
                )
            else:
                rejected += 1
                AuditLog.objects.create(
                    actor=request.user,
                    action="cooptation.application.rejected",
                    target_type="cooptation.AdminApplication",
                    target_id=str(app.pk),
                    metadata={
                        "candidate_full_name": app.full_name,
                        "candidate_email": app.email,
                        "note": reason,
                    },
                )
        self.message_user(request, f"{rejected} candidature(s) rejetée(s).", messages.WARNING)

    @admin.action(description="Remettre en file de revue (cooptation bloquée)")
    def requeue_action(self, request, queryset):
        """The one non-terminal transition an operator may force: a stalled
        cooptation_pending application back into the admin queue. Replaces
        the old hand-edit of `status` now that the field is read-only."""
        moved = queryset.filter(status="cooptation_pending").update(status="awaiting_admin")
        refused = queryset.count() - moved
        if refused:
            self.message_user(
                request,
                f"{refused} candidature(s) ignorée(s) : seules celles en « Cooptation en cours »"
                " peuvent être remises en file.",
                messages.WARNING,
            )
        self.message_user(
            request, f"{moved} candidature(s) remise(s) en file de revue.", messages.SUCCESS
        )

    @admin.action(description="Renvoyer le lien de mot de passe (candidats déjà approuvés)")
    def resend_password_link_action(self, request, queryset):
        sent = 0
        for app in queryset.filter(status="approved"):
            from django.contrib.auth import get_user_model

            User = get_user_model()  # noqa: N806
            # approve_application creates the account with username=email;
            # the email field is mutable and NOT unique. Username is the
            # stable key — matching on email alone silently skipped users
            # whose address was later corrected, or picked an arbitrary
            # account among shared-email duplicates.
            user = (
                User.objects.filter(username=app.email).first()
                or User.objects.filter(email=app.email).order_by("pk").first()
            )
            if not user:
                continue
            from .services import _build_password_set_url

            send_application_approved(app, password_set_url=_build_password_set_url(user))
            sent += 1
            # Same Resend pacing as the other bulk senders (429 risk).
            time.sleep(0.5)
        self.message_user(request, f"{sent} email(s) renvoyé(s).", messages.SUCCESS)


@admin.register(CooptationRequest)
class CooptationRequestAdmin(admin.ModelAdmin):
    list_display = ("application", "parrain", "response", "responded_at", "expires_at")
    list_filter = ("response",)
    list_select_related = ("application", "parrain")
    readonly_fields = (
        "application",
        "parrain",
        "token",
        "expires_at",
        "reminder_sent_at",
        "response",
        "responded_at",
        "comment",
    )


@admin.register(KnowledgeQuestion)
class KnowledgeQuestionAdmin(admin.ModelAdmin):
    list_display = ("position", "kind", "text", "is_active")
    list_filter = ("kind", "is_active")


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(admin.ModelAdmin):
    list_display = ("application", "question", "auto_grade", "submitted_at")
    list_select_related = ("application", "question")
    readonly_fields = ("application", "question", "candidate_answer", "auto_grade", "submitted_at")
    list_filter = ("auto_grade",)
