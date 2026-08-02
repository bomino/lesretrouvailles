"""Forms for the memoriam admin and the public nomination view."""

from __future__ import annotations

from django import forms
from django.contrib.postgres.forms import SimpleArrayField

from members.models import VALID_YEARS

from .models import InMemoriamEntry, InMemoriamNomination


class InMemoriamEntryAdminForm(forms.ModelForm):
    """Admin form for InMemoriamEntry. The `upload` FileField is form-only;
    save_model uploads the file to Cloudinary and writes photo_public_id."""

    ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
    MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8 MB — mirrors GestionMemoryForm

    upload = forms.FileField(
        required=False,
        help_text="Choisir une photo (JPEG, PNG ou WebP, ≤ 8 Mo). "
        "Conservera l'image existante si vide.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

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

    # SimpleArrayField is the Django admin-friendly widget for ArrayField:
    # comma-separated strings in the form, list in the model.
    years_attended = SimpleArrayField(
        forms.IntegerField(),
        required=False,
        help_text="Années séparées par virgules (ex. : 1980,1981,1982).",
    )
    classes = SimpleArrayField(
        forms.CharField(),
        required=False,
        help_text="Classes séparées par virgules (ex. : 6e,5e,4eA).",
    )

    class Meta:
        model = InMemoriamEntry
        fields = (
            "full_name",
            "nickname",
            "years_attended",
            "classes",
            "birth_year",
            "death_year",
            "tribute",
            "family_consent_giver",
            "family_consent_date",
            "family_consent_canal",
            "status",
        )

    def clean(self):
        cleaned = super().clean()
        # Defer the model-level clean() to enforce per-status rules.
        instance = self.instance
        for field in self.Meta.fields:
            if field in cleaned:
                setattr(instance, field, cleaned[field])
        instance.full_clean(exclude=("created_by",))
        return cleaned


class NominationForm(forms.ModelForm):
    proposed_years = SimpleArrayField(
        forms.IntegerField(),
        required=False,
        help_text="Années au CEG, séparées par virgules (ex. : 1980,1981).",
    )

    def clean_proposed_years(self):
        """InMemoriamEntry.clean() validates years against VALID_YEARS but
        this member-facing form applied no equivalent check — any integer
        (negative, 99999) flowed verbatim into the admin-alert email and the
        nomination admin."""
        years = self.cleaned_data.get("proposed_years") or []
        bad = [y for y in years if y not in VALID_YEARS]
        if bad:
            raise forms.ValidationError(
                f"Années hors plage 1980-1985 : {', '.join(str(y) for y in bad)}."
            )
        return years

    class Meta:
        model = InMemoriamNomination
        fields = (
            "proposed_name",
            "proposed_nickname",
            "proposed_years",
            "personal_memory",
            "family_contact_hint",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2.5 "
            "text-base shadow-sm focus:border-tertiary focus:outline-none focus:ring-2 "
            "focus:ring-tertiary/30"
        )
        for name, field in self.fields.items():
            if name in ("personal_memory", "family_contact_hint"):
                field.widget = forms.Textarea(attrs={"rows": 5 if name == "personal_memory" else 3})
            field.widget.attrs.setdefault("class", input_class)
