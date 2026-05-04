"""Forms for the memoires admin."""

from __future__ import annotations

from django import forms

from .models import Memory


class MemoryAdminForm(forms.ModelForm):
    """Admin form for Memory. Adds an `upload` FileField that exists only on
    the form (not on the Memory model). MemoryAdmin.save_model uploads the
    file to Cloudinary via alumni.cloudinary and writes the resulting
    public_id into Memory.photo_public_id."""

    upload = forms.FileField(
        required=False,
        help_text="Choisir une photo. Conservera l'image existante si vide (en édition).",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    class Meta:
        model = Memory
        fields = ("photo_public_id", "caption", "taken_at", "location", "status")
        widgets = {
            "photo_public_id": forms.HiddenInput(),  # populated by save_model after upload
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # photo_public_id is set by save_model after upload; allow blank on the form.
        self.fields["photo_public_id"].required = False

    def clean(self):
        cleaned = super().clean()
        # On create, upload is required. On edit, may be blank (keep existing).
        if not self.instance.pk and not cleaned.get("upload"):
            raise forms.ValidationError("Une photo est obligatoire pour créer une nouvelle entrée.")
        return cleaned
