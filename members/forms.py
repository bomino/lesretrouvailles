"""Forms for the membership app."""

from django import forms

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
        ]


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
