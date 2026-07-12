"""Admin curation surface for In Memoriam fiches and nominations."""

from __future__ import annotations

import logging

from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from alumni.cloudinary import get_client

from .forms import InMemoriamEntryAdminForm
from .models import InMemoriamEntry, InMemoriamNomination

logger = logging.getLogger(__name__)


@admin.register(InMemoriamEntry)
class InMemoriamEntryAdmin(admin.ModelAdmin):
    form = InMemoriamEntryAdminForm

    list_display = ("full_name", "years_attended", "status", "published_at", "created_by")
    list_filter = ("status",)
    search_fields = ("full_name", "nickname")
    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
        "published_at",
        "approved_content_version",
    )

    fieldsets = (
        ("Identité", {"fields": ("full_name", "nickname", "years_attended", "classes")}),
        ("Dates (optionnel)", {"fields": ("birth_year", "death_year")}),
        ("Photo", {"fields": ("upload",)}),
        ("Hommage (markdown)", {"fields": ("tribute",)}),
        (
            "Consentement famille (Annexe D §D.5)",
            {"fields": ("family_consent_giver", "family_consent_date", "family_consent_canal")},
        ),
        ("Publication", {"fields": ("status",)}),
        (
            "Audit (lecture seule)",
            {
                "fields": (
                    "approved_content_version",
                    "created_by",
                    "created_at",
                    "updated_at",
                    "published_at",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        # 1. Detect transitions before mutating.
        if change:
            db_obj = type(obj).objects.get(pk=obj.pk)
        else:
            db_obj = None
        was_unpublished = (db_obj is None) or (db_obj.published_at is None)
        text_changed = bool(
            change
            and any(
                getattr(obj, f) != getattr(db_obj, f) for f in ("full_name", "nickname", "tribute")
            )
        )

        # 2. Upload + replace photo.
        upload = form.cleaned_data.get("upload")
        if upload:
            client = get_client()
            old_public_id = obj.photo_public_id  # may be empty
            obj.photo_public_id = client.upload_file(upload, folder="memoriam")
            if old_public_id and old_public_id != obj.photo_public_id:
                client.delete(old_public_id)

        # 3. Bump approved_content_version on text change.
        if text_changed:
            obj.approved_content_version = (db_obj.approved_content_version or 1) + 1

        # 4. Set published_at on first publish + flag email.
        should_fire_publish_email = False
        if obj.status == "published" and was_unpublished:
            obj.published_at = timezone.now()
            should_fire_publish_email = True

        # 5. Autostamp created_by on new.
        if not change:
            obj.created_by = request.user

        # 6. Persist.
        super().save_model(request, obj, form, change)

        # 7. Post-commit: fire publish email to opted-in active members.
        # on_commit because ModelAdmin wraps this in a transaction — sending
        # inside it risks emailing about a publish that then rolls back.
        # Email-less members (~80% of the audience) are excluded up front.
        if should_fire_publish_email:
            transaction.on_commit(lambda: self._send_publish_emails(obj))

    def delete_model(self, request, obj):
        """The detail page promises families the fiche can be withdrawn on
        request. Deleting the DB row used to leave the deceased's photo
        permanently fetchable at its res.cloudinary.com URL."""
        self._delete_photo_on_commit(obj.photo_public_id)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._delete_photo_on_commit(obj.photo_public_id)
        super().delete_queryset(request, queryset)

    @staticmethod
    def _delete_photo_on_commit(public_id: str) -> None:
        if not public_id:
            return

        def _do_delete():
            try:
                get_client().delete(public_id)
            except Exception:
                logger.exception("Cloudinary delete failed for %s (orphaned asset)", public_id)

        transaction.on_commit(_do_delete)

    @staticmethod
    def _send_publish_emails(obj):
        from members.models import Member

        from .emails import send_fiche_published_to_member

        recipients = (
            Member.objects.filter(
                status="active",
                preferences__in_memoriam_alerts=True,
            )
            .exclude(user__email="")
            .select_related("user")
        )
        for member in recipients:
            try:
                send_fiche_published_to_member(member, obj)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "memoriam: failed to send publish email to %s: %s",
                    member.user.email,
                    e,
                )


@admin.register(InMemoriamNomination)
class InMemoriamNominationAdmin(admin.ModelAdmin):
    """Read-mostly: nominations come from the public form. Admin only edits
    status/admin_note/linked_entry; the nominator's content is immutable."""

    list_display = ("proposed_name", "nominator", "status", "submitted_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("proposed_name", "nominator__first_name", "nominator__last_name")
    readonly_fields = (
        "nominator",
        "submitted_at",
        "proposed_name",
        "proposed_nickname",
        "proposed_years",
        "personal_memory",
        "family_contact_hint",
        "reviewed_by",
        "reviewed_at",
    )
    fields = (
        "nominator",
        "submitted_at",
        "proposed_name",
        "proposed_nickname",
        "proposed_years",
        "personal_memory",
        "family_contact_hint",
        "status",
        "admin_note",
        "linked_entry",
        "reviewed_by",
        "reviewed_at",
    )

    def has_add_permission(self, request):
        # Nominations only come from the public form (/in-memoriam/nominer/).
        return False

    def save_model(self, request, obj, form, change):
        if change and obj.status != "pending":
            if not obj.reviewed_by:
                obj.reviewed_by = request.user
            if not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
