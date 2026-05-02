"""Forms for the membership app."""

from django import forms
from django.core.exceptions import ValidationError

from .models import Member, NotificationPreference


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            "nickname",
            "city",
            "country",
            "profession",
            "show_email",
            "show_whatsapp",
            "show_city",
            "photo_public_id",
        ]
        widgets = {
            "photo_public_id": forms.HiddenInput(),
        }

    def clean_photo_public_id(self):
        value = (self.cleaned_data.get("photo_public_id") or "").strip()
        if not value:
            return ""
        expected_prefix = f"members/{self.instance.slug}/"
        if not value.startswith(expected_prefix):
            raise ValidationError("Chemin de photo invalide.")
        return value


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "digest_weekly",
            "in_memoriam_alerts",
            "event_alerts",
            "tag_alerts",
            "data_saver",
        ]
