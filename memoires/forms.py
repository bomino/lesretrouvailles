"""Forms for the memoires admin."""

from __future__ import annotations

from django import forms

from .models import Memory


class MemoryAdminForm(forms.ModelForm):
    """Admin form for Memory. The `upload` FileField is form-only (not on
    the model). MemoryAdmin.save_model uploads the file to Cloudinary via
    alumni.cloudinary and writes the resulting public_id directly into
    Memory.photo_public_id — bypassing the form entirely. This eliminates
    the tamper-able POST vector that an exposed photo_public_id field
    would create."""

    ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
    MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8 MB — mirrors GestionMemoryForm

    upload = forms.FileField(
        required=False,
        help_text="Choisir une photo (JPEG, PNG ou WebP, ≤ 8 Mo). "
        "Conservera l'image existante si vide (en édition).",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    class Meta:
        model = Memory
        fields = ("caption", "taken_at", "location", "status")

    def clean_upload(self):
        # The accept attr above is client-side only; without these guards a
        # fat-fingered 40 MB file went straight to Cloudinary.
        upload = self.cleaned_data.get("upload")
        if not upload:
            return upload
        if upload.size == 0:
            raise forms.ValidationError("Le fichier est vide.")
        if upload.size > self.MAX_UPLOAD_SIZE:
            raise forms.ValidationError("Photo trop volumineuse : 8 Mo maximum.")
        if upload.content_type not in self.ALLOWED_MIME_TYPES:
            raise forms.ValidationError("Format non pris en charge. Utilisez JPEG, PNG ou WebP.")
        return upload

    def clean(self):
        cleaned = super().clean()
        # On create, upload is required. On edit, may be blank (keep existing).
        if not self.instance.pk and not cleaned.get("upload"):
            raise forms.ValidationError("Une photo est obligatoire pour créer une nouvelle entrée.")
        return cleaned
