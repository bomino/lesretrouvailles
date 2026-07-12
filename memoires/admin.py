"""Admin curation surface for the Mur des souvenirs."""

from __future__ import annotations

import logging

from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html

from alumni.cloudinary import get_client, memory_thumbnail_url

from .forms import MemoryAdminForm
from .models import Memory

logger = logging.getLogger(__name__)


def _delete_photo_on_commit(public_id: str) -> None:
    """Schedule a Cloudinary delete for after the DB delete commits.
    Failures are logged, never raised — a Cloudinary outage must not roll
    back the admin's delete."""
    if not public_id:
        return

    def _do_delete():
        try:
            get_client().delete(public_id)
        except Exception:
            logger.exception("Cloudinary delete failed for %s (orphaned asset)", public_id)

    transaction.on_commit(_do_delete)


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    """Auto-stamps created_by on first save and uploads the file to
    Cloudinary server-side via alumni.cloudinary.get_client().upload_file().
    """

    form = MemoryAdminForm

    list_display = ("thumbnail", "caption_preview", "taken_at", "status", "updated_at")
    list_filter = ("status", "taken_at")
    search_fields = ("caption", "location")
    readonly_fields = ("created_by", "created_at", "updated_at")

    fieldsets = (
        ("Photo", {"fields": ("upload",)}),
        ("Légende", {"fields": ("caption",)}),
        ("Contexte", {"fields": ("taken_at", "location")}),
        ("Publication", {"fields": ("status",)}),
        (
            "Audit (lecture seule)",
            {"fields": ("created_by", "created_at", "updated_at")},
        ),
    )

    @admin.display(description="Aperçu")
    def thumbnail(self, obj):
        if not obj.photo_public_id:
            return ""
        url = memory_thumbnail_url(obj.photo_public_id, size=80)
        return format_html('<img src="{}" width="80" height="80" alt="" />', url)

    @admin.display(description="Légende")
    def caption_preview(self, obj):
        return obj.caption[:60] + ("…" if len(obj.caption) > 60 else "")

    def save_model(self, request, obj, form, change):
        upload = form.cleaned_data.get("upload")
        if upload:
            old_public_id = obj.photo_public_id  # may be empty on create
            client = get_client()
            # Note: this Cloudinary upload happens BEFORE super().save_model().
            # If super().save_model() later raises (DB constraint, network blip),
            # the Cloudinary blob is orphaned with no DB record. Acceptable at
            # P5a scale (10-20 admin-curated photos); revisit if member uploads
            # open up in Phase 2.
            obj.photo_public_id = client.upload_file(upload, folder="memoires")
            if old_public_id and old_public_id != obj.photo_public_id:
                client.delete(old_public_id)
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        """Hard delete is this admin's remaining purpose (every other op moved
        to /gestion/souvenirs/). Drop the Cloudinary asset too, after the DB
        delete commits — otherwise the photo stays permanently fetchable at
        its res.cloudinary.com URL."""
        _delete_photo_on_commit(obj.photo_public_id)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            _delete_photo_on_commit(obj.photo_public_id)
        super().delete_queryset(request, queryset)
