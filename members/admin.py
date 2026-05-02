from django.contrib import admin

from .models import ConsentRecord, Member, NotificationPreference


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "city", "country", "profession", "status", "created_at")
    list_filter = ("status", "country", "city")
    search_fields = ("first_name", "last_name", "nickname")
    readonly_fields = ("slug", "created_at", "updated_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "digest_weekly",
        "in_memoriam_alerts",
        "event_alerts",
        "tag_alerts",
        "data_saver",
    )
    list_filter = ("digest_weekly", "in_memoriam_alerts", "event_alerts", "tag_alerts")


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("member", "charter_version", "accepted_at", "ip_address")
    list_filter = ("charter_version",)
    search_fields = ("member__first_name", "member__last_name")
    readonly_fields = ("member", "charter_version", "accepted_at", "ip_address")

    def has_add_permission(self, request):
        return False
