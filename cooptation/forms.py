"""Forms for the cooptation app."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from members.models import GRADE_CHOICES, VALID_YEARS, Member


class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=160, label="Nom complet")
    nickname = forms.CharField(max_length=60, required=False, label="Surnom")
    years_attended = forms.CharField(
        max_length=80,
        label="Années au CEG 1 (séparées par virgule)",
        help_text="Ex. 1980,1981,1982,1983",
    )
    classes = forms.CharField(
        max_length=40,
        label="Classes (séparées par virgule)",
        help_text="Parmi : 6e, 5e, 4e, 3e",
    )
    city = forms.CharField(max_length=80, label="Ville actuelle")
    country = forms.CharField(max_length=80, initial="Niger", label="Pays")
    profession = forms.CharField(max_length=120, required=False, label="Profession")
    email = forms.EmailField(label="Votre email")
    whatsapp = forms.CharField(max_length=30, required=False, label="WhatsApp (optionnel)")
    parrain1_email = forms.EmailField(label="Email du parrain n°1")
    parrain2_email = forms.EmailField(label="Email du parrain n°2")
    website_url = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2"
            " text-base shadow-sm focus:border-tertiary focus:outline-none"
            " focus:ring-2 focus:ring-tertiary/30"
        )
        for name, field in self.fields.items():
            if name == "website_url":
                continue
            field.widget.attrs.setdefault("class", input_class)

    def clean_years_attended(self):
        raw = self.cleaned_data["years_attended"]
        try:
            years = [int(p.strip()) for p in raw.split(",") if p.strip()]
        except ValueError as exc:
            raise ValidationError("Format invalide (entiers séparés par virgules).") from exc
        if any(y not in VALID_YEARS for y in years):
            raise ValidationError("Années hors plage 1980-1985.")
        return years

    def clean_classes(self):
        raw = self.cleaned_data["classes"]
        items = [p.strip() for p in raw.split(",") if p.strip()]
        valid = {key for key, _ in GRADE_CHOICES}
        if any(c not in valid for c in items):
            raise ValidationError("Classe inconnue. Utilisez 6e, 5e, 4e, ou 3e.")
        return items

    def clean(self):
        data = super().clean()
        email = data.get("email")
        p1 = data.get("parrain1_email")
        p2 = data.get("parrain2_email")
        if email and p1 and email == p1:
            raise ValidationError("Vous ne pouvez pas vous parrainer (parrain n°1).")
        if email and p2 and email == p2:
            raise ValidationError("Vous ne pouvez pas vous parrainer (parrain n°2).")
        if p1 and p2 and p1 == p2:
            raise ValidationError("Veuillez nommer deux parrains différents.")
        if p1 and not Member.objects.filter(user__email=p1, status="active").exists():
            raise ValidationError(f"Email parrain inconnu ou inactif : {p1}")
        if p2 and not Member.objects.filter(user__email=p2, status="active").exists():
            raise ValidationError(f"Email parrain inconnu ou inactif : {p2}")
        return data
