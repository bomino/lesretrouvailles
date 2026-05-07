"""Forms for the cooptation app."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from members.models import VALID_CLASS_PATTERN, VALID_YEARS, Member


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
        required=False,
        label="Classes (séparées par virgule, optionnel)",
        help_text=(
            "Ex. 6e, 6eA, 6a, 4b (avec ou sans 'e', lettre de section optionnelle). "
            "Laissez vide si vous ne vous souvenez pas."
        ),
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
        if any(not VALID_CLASS_PATTERN.match(c) for c in items):
            raise ValidationError("Classe inconnue. Format attendu : 6e, 6eA, 6a, 4b, etc.")
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
        if email and Member.objects.filter(user__email=email).exists():
            # Any Member (incl. suspended/deleted) blocks reuse — without this,
            # approve_application's `update_or_create` would silently overwrite
            # the existing Member's profile. Generic message avoids leaking
            # whether the email is on file.
            raise ValidationError(
                "Cet email correspond déjà à un compte. Connectez-vous ou utilisez un autre email."
            )
        if p1 and p2 and p1 == p2:
            raise ValidationError("Veuillez nommer deux parrains différents.")
        if p1 and not Member.objects.filter(user__email=p1, status="active").exists():
            raise ValidationError(f"Email parrain inconnu ou inactif : {p1}")
        if p2 and not Member.objects.filter(user__email=p2, status="active").exists():
            raise ValidationError(f"Email parrain inconnu ou inactif : {p2}")
        return data


class ParrainVouchForm(forms.Form):
    response = forms.ChoiceField(
        choices=[("accepted", "J'accepte de coopter"), ("refused", "Je refuse")],
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Commentaire (optionnel)",
    )
