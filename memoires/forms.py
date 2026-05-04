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

    upload = forms.FileField(
        required=False,
        help_text="Choisir une photo. Conservera l'image existante si vide (en édition).",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    class Meta:
        model = Memory
        fields = ("caption", "taken_at", "location", "status")

    def clean(self):
        cleaned = super().clean()
        # On create, upload is required. On edit, may be blank (keep existing).
        if not self.instance.pk and not cleaned.get("upload"):
            raise forms.ValidationError("Une photo est obligatoire pour créer une nouvelle entrée.")
        return cleaned
