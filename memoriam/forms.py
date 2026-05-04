"""Forms for the memoriam admin and the public nomination view."""

from __future__ import annotations

from django import forms
from django.contrib.postgres.forms import SimpleArrayField

from .models import InMemoriamEntry, InMemoriamNomination


class InMemoriamEntryAdminForm(forms.ModelForm):
    """Admin form for InMemoriamEntry. The `upload` FileField is form-only;
    save_model uploads the file to Cloudinary and writes photo_public_id."""

    upload = forms.FileField(
        required=False,
        help_text="Choisir une photo. Conservera l'image existante si vide.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

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

    class Meta:
        model = InMemoriamNomination
        fields = (
            "proposed_name",
            "proposed_nickname",
            "proposed_years",
            "personal_memory",
            "family_contact_hint",
        )
        widgets = {
            "personal_memory": forms.Textarea(attrs={"rows": 5}),
            "family_contact_hint": forms.Textarea(attrs={"rows": 3}),
        }
