"""Admin curation surface for the Mur des souvenirs."""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from alumni.cloudinary import get_client, memory_thumbnail_url

from .forms import MemoryAdminForm
from .models import Memory


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
