from django.contrib import admin, messages
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
    list_filter = ("status", "cooptation_outcome", "country")
    search_fields = ("full_name", "email", "nickname")
    readonly_fields = (
        "submitted_at",
        "reviewed_by",
        "rejected_at",
        "retention_until",
        "purged_at",
        "source_ip",
        "questionnaire_token",
    )
    inlines = [CooptationRequestInline, QuestionnaireResponseInline]
    actions = ["approve_action", "reject_action", "resend_password_link_action"]

    @admin.display(description="IP")
    def ip_badge(self, obj):
        if not obj.source_ip:
            return ""
        from datetime import timedelta

        from django.utils import timezone

        recent = AdminApplication.objects.filter(
            source_ip=obj.source_ip,
            submitted_at__gte=timezone.now() - timedelta(hours=24),
        ).count()
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
        except (TypeError, Exception):
            pass

    @admin.action(description="Approuver les candidatures sélectionnées")
    def approve_action(self, request, queryset):
        for app in queryset:
            services.approve_application(app, reviewed_by=request.user)
        self.message_user(
            request, f"{queryset.count()} candidature(s) approuvée(s).", messages.SUCCESS
        )

    @admin.action(description="Rejeter les candidatures sélectionnées")
    def reject_action(self, request, queryset):
        reason = (request.POST.get("reason") or "Demande non éligible").strip()
        for app in queryset:
            services.reject_application(app, reviewed_by=request.user, note=reason)
        self.message_user(
            request, f"{queryset.count()} candidature(s) rejetée(s).", messages.WARNING
        )

    @admin.action(description="Renvoyer le lien de mot de passe (candidats déjà approuvés)")
    def resend_password_link_action(self, request, queryset):
        sent = 0
        for app in queryset.filter(status="approved"):
            from django.contrib.auth import get_user_model

            User = get_user_model()  # noqa: N806
            user = User.objects.filter(email=app.email).first()
            if not user:
                continue
            from .services import _build_password_set_url

            send_application_approved(app, password_set_url=_build_password_set_url(user))
            sent += 1
        self.message_user(request, f"{sent} email(s) renvoyé(s).", messages.SUCCESS)


@admin.register(CooptationRequest)
class CooptationRequestAdmin(admin.ModelAdmin):
    list_display = ("application", "parrain", "response", "responded_at", "expires_at")
    list_filter = ("response",)
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
    readonly_fields = ("application", "question", "candidate_answer", "auto_grade", "submitted_at")
    list_filter = ("auto_grade",)
