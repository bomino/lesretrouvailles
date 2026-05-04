from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from .emails import send_admin_ghost_added
from .models import (
    AuditLog,
    ConsentRecord,
    Member,
    NotificationPreference,
    PublicSearchEntry,
    RemovalRequest,
)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "city", "country", "profession", "status", "created_at")
    list_filter = ("status", "country", "city")
    search_fields = ("first_name", "last_name", "nickname")
    readonly_fields = ("slug", "created_at", "updated_at", "photo_uploader")

    fieldsets = (
        (
            "Identité",
            {
                "fields": (
                    "user",
                    "slug",
                    ("first_name", "last_name"),
                    "nickname",
                    ("years_attended", "classes"),
                ),
            },
        ),
        (
            "Localisation et profession",
            {"fields": (("city", "country"), "profession")},
        ),
        (
            "Photo",
            {
                "fields": ("photo_uploader", "photo_public_id"),
                "description": (
                    "Le champ « Photo public id » contient l'identifiant Cloudinary "
                    "(ex. <code>members/&lt;slug&gt;/photo_xyz</code>). "
                    "Utilisez le téléverseur ci-dessus pour le remplir automatiquement."
                ),
            },
        ),
        (
            "Confidentialité",
            {"fields": (("show_email", "show_whatsapp", "show_city"), "status")},
        ),
        ("Métadonnées", {"fields": (("created_at", "updated_at"),)}),
    )

    class Media:
        js = ("js/photo-uploader.js",)

    @admin.display(description="Téléversement Cloudinary")
    def photo_uploader(self, obj):
        """Render a Cloudinary signed-direct-upload widget targeting this member.

        Only on the change form — the add form doesn't have a slug yet, so
        we show a hint instead. After the admin saves a new member, they
        return to the change form and the uploader appears.
        """
        if not obj or not obj.pk:
            return format_html(
                '<p style="color:#666;">'
                "Sauvegardez d'abord le membre, puis revenez sur cette page "
                "pour téléverser une photo."
                "</p>"
            )

        return format_html(
            "<div data-photo-uploader "
            'data-cloud-name="{cloud}" '
            'data-member-slug="{slug}" '
            'data-sign-endpoint="/api/cloudinary/sign/" '
            'style="display:flex; align-items:center; gap:1rem; padding:.5rem 0;">'
            '  <input type="file" accept="image/jpeg,image/png,image/webp" '
            '         style="display:none;">'
            '  <button type="button" data-photo-trigger '
            '          style="padding:.5rem 1rem; border:1px solid #ccc; '
            '                 background:#fff; border-radius:4px; cursor:pointer;">'
            "    📷 Choisir une photo"
            "  </button>"
            '  <img data-photo-preview src="" alt="" '
            '       style="display:none; height:64px; width:64px; '
            "              object-fit:cover; border-radius:50%; "
            '              border:1px solid #ddd;">'
            '  <span data-photo-status style="font-size:.9em;"></span>'
            "</div>",
            cloud=settings.CLOUDINARY_CLOUD_NAME,
            slug=obj.slug,
        )


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

    def has_delete_permission(self, request, obj=None):
        return False


class GhostStatusFilter(admin.SimpleListFilter):
    """Lifecycle status of a PublicSearchEntry, computed from signoff
    count + removed_at + added_at. Lets admins find entries pending
    cosignature, stale ones approaching auto-removal, etc."""

    title = "Statut publication"
    parameter_name = "ghost_status"

    def lookups(self, request, model_admin):
        return [
            ("draft", "Brouillon (0 signatures)"),
            ("pending", "En attente (1 signature)"),
            ("published", "Publiée (2+)"),
            ("stale", "Périmée (>12 mois)"),
            ("removed", "Retirée"),
        ]

    def queryset(self, request, queryset):
        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        value = self.value()
        if value is None:
            return queryset

        if value == "removed":
            return queryset.filter(removed_at__isnull=False)

        qs = queryset.filter(removed_at__isnull=True).annotate(n=Count("added_by_admins"))
        if value == "draft":
            return qs.filter(n=0)
        if value == "pending":
            return qs.filter(n=1)
        if value == "published":
            cutoff = timezone.now() - timedelta(days=365)
            return qs.filter(n__gte=2, added_at__gt=cutoff)
        if value == "stale":
            cutoff = timezone.now() - timedelta(days=365)
            return qs.filter(n__gte=2, added_at__lte=cutoff)
        return queryset


@admin.register(PublicSearchEntry)
class PublicSearchEntryAdmin(admin.ModelAdmin):
    """Governance UI for the public ghost list.

    Two co-signers required for publication — admins add themselves to
    `added_by_admins` to vouch. Until 2 distinct admins have signed off,
    the entry stays invisible publicly.
    """

    list_display = (
        "first_name",
        "last_name_initial",
        "years_at_ceg",
        "signoff_count",
        "retrait_at",
    )
    list_filter = (GhostStatusFilter, "removed_at")
    search_fields = ("first_name", "last_name_initial", "note")
    filter_horizontal = ("added_by_admins",)
    readonly_fields = ("added_at", "removal_token", "removed_at", "removed_reason")

    fieldsets = (
        (
            "Données publiques (RGPD : strict minimum)",
            {
                "fields": ("first_name", "last_name_initial", "years_at_ceg", "note"),
                "description": (
                    "Seuls ces champs apparaissent sur la page publique. "
                    "Pas d'email, pas de ville, pas de profession (master spec § 6.5)."
                ),
            },
        ),
        (
            "Cosignataires (optionnel)",
            {
                "fields": ("added_by_admins",),
                "description": (
                    "Vous êtes ajouté·e automatiquement à l'enregistrement. "
                    "D'autres admins peuvent ajouter leur nom pour étoffer la "
                    "trace d'audit, mais ce n'est plus requis pour la publication."
                ),
            },
        ),
        (
            "Audit (lecture seule)",
            {"fields": ("added_at", "removal_token", "removed_at", "removed_reason")},
        ),
    )

    def save_model(self, request, obj, form, change):
        """P4d: stash whether this is a create so save_related can act on it."""
        obj._is_new = not change
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """P4d: after M2M is saved from the form, auto-add the creating admin
        and fire the admin_ghost_added FYI email to other staff. Gated on
        _is_new so it only fires on create, not on subsequent edits."""
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if getattr(obj, "_is_new", False):
            obj.added_by_admins.add(request.user)
            send_admin_ghost_added(obj, added_by=request.user)

    @admin.display(description="Signatures")
    def signoff_count(self, obj):
        return obj.added_by_admins.count()

    @admin.display(description="Retiré le")
    def retrait_at(self, obj):
        return obj.removed_at


@admin.register(RemovalRequest)
class RemovalRequestAdmin(admin.ModelAdmin):
    """Public removal requests. Read-only on body fields; deletion of a
    pending request fires the ghost.removal.cancelled audit hook."""

    list_display = (
        "entry",
        "requester_email",
        "status",
        "requested_at",
        "expires_at",
    )
    list_filter = ("status",)
    search_fields = ("requester_email", "entry__first_name", "entry__last_name_initial")
    readonly_fields = (
        "entry",
        "requester_email",
        "reason",
        "confirm_token",
        "requester_ip",
        "requested_at",
        "confirmed_at",
        "expires_at",
    )

    def has_add_permission(self, request):
        return False  # always created by the public flow


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Append-only governance log. No add/change/delete from admin."""

    list_display = (
        "created_at",
        "actor",
        "action",
        "target_type",
        "target_id",
    )
    list_filter = ("action", "target_type")
    search_fields = ("action", "target_type", "target_id")
    readonly_fields = (
        "actor",
        "action",
        "target_type",
        "target_id",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
