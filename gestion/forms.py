"""Forms for the /gestion/ console."""

from __future__ import annotations

import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.postgres.forms import SimpleArrayField

from members.models import VALID_CLASS_PATTERN, VALID_YEARS, AuditLog, Member

User = get_user_model()

USERNAME_DIGITS_RE = re.compile(r"^\d{8,15}$")


class MemberAdminEditForm(forms.ModelForm):
    """Admin-side edit form. Wider field set than ProfileEditForm because
    admins can correct identity fields (name, years, classes) that members
    can't self-edit. Username/email changes have their own dedicated flows
    (Phase 2 username confirmation; email change inline)."""

    years_attended = SimpleArrayField(
        forms.IntegerField(),
        required=False,
        help_text="Années séparées par virgules (ex. : 1980,1981,1982).",
    )
    classes = SimpleArrayField(
        forms.CharField(),
        required=False,
        help_text="Classes séparées par virgules (ex. : 6e, 6eA, 6a). Optionnel.",
    )
    email = forms.EmailField(
        required=False,
        label="Email",
        help_text="Email du membre. Vide si le membre n'en a pas.",
    )

    class Meta:
        model = Member
        fields = [
            "first_name",
            "last_name",
            "nickname",
            "years_attended",
            "classes",
            "city",
            "country",
            "profession",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["email"].initial = self.instance.user.email
        input_class = (
            "block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2"
            " text-base shadow-sm focus:border-tertiary focus:outline-none"
            " focus:ring-2 focus:ring-tertiary/30"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", input_class)

    def clean_years_attended(self):
        years = self.cleaned_data.get("years_attended") or []
        bad = [y for y in years if y not in VALID_YEARS]
        if bad:
            raise forms.ValidationError(f"Années hors plage 1980-1985 : {bad}.")
        return years

    def clean_classes(self):
        classes = self.cleaned_data.get("classes") or []
        bad = [c for c in classes if not VALID_CLASS_PATTERN.match(c)]
        if bad:
            raise forms.ValidationError(
                f"Classes invalides : {bad}. Format attendu : 6e, 6eA, 6a, etc."
            )
        return classes

    def save_with_audit(self, *, actor) -> list[str]:
        """Persist + write a single AuditLog row listing the changed fields.
        Returns the list of changed field names so the redirect can flash
        a precise success message."""
        changed = list(self.changed_data)

        # Email lives on User, not Member — handle it separately
        new_email = self.cleaned_data.get("email", "")
        old_email = self.instance.user.email
        email_changed = new_email != old_email

        member = super().save()

        if email_changed:
            member.user.email = new_email
            member.user.save(update_fields=["email"])
            if "email" not in changed:
                changed.append("email")

        if changed:
            AuditLog.objects.create(
                actor=actor,
                action="gestion.member.edited",
                target_type="members.Member",
                target_id=str(member.pk),
                metadata={
                    "changed_fields": changed,
                    "member_full_name": member.full_name,
                },
            )
        return changed


class MemberUsernameChangeForm(forms.Form):
    """Confirm-the-old-number gate for changing a member's WhatsApp digits.

    Wrong number = locked-out member, so we require the operator to type
    the current username verbatim before accepting the change. Pure
    Form (not ModelForm) because we touch User.username, not Member."""

    confirm_current = forms.CharField(
        label="Identifiant actuel (à retaper pour confirmer)",
        max_length=15,
        help_text="Tapez les chiffres du numéro WhatsApp actuel pour confirmer.",
    )
    new_username = forms.CharField(
        label="Nouveau numéro WhatsApp",
        max_length=15,
        help_text="Chiffres uniquement, sans espaces ni « + ». Entre 8 et 15 chiffres.",
    )

    def __init__(self, *args, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member
        input_class = (
            "block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2"
            " text-base shadow-sm focus:border-tertiary focus:outline-none"
            " focus:ring-2 focus:ring-tertiary/30"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", input_class)

    def clean_confirm_current(self):
        value = (self.cleaned_data.get("confirm_current") or "").strip()
        if value != self.member.user.username:
            raise forms.ValidationError(
                "L'identifiant actuel saisi ne correspond pas. Vérifiez avec le membre.",
            )
        return value

    def clean_new_username(self):
        value = (self.cleaned_data.get("new_username") or "").strip()
        if not USERNAME_DIGITS_RE.fullmatch(value):
            raise forms.ValidationError(
                "Format invalide : chiffres uniquement, entre 8 et 15 chiffres "
                "(sans espaces, sans « + »).",
            )
        if value == self.member.user.username:
            raise forms.ValidationError(
                "Le nouveau numéro est identique au numéro actuel.",
            )
        if User.objects.filter(username=value).exists():
            raise forms.ValidationError(
                f"Le numéro {value} est déjà utilisé par un autre compte.",
            )
        return value

    def save_with_audit(self, *, actor) -> str:
        new_username = self.cleaned_data["new_username"]
        old_username = self.member.user.username
        self.member.user.username = new_username
        self.member.user.save(update_fields=["username"])
        AuditLog.objects.create(
            actor=actor,
            action="gestion.member.username_changed",
            target_type="members.Member",
            target_id=str(self.member.pk),
            metadata={
                "old_username": old_username,
                "new_username": new_username,
                "member_full_name": self.member.full_name,
            },
        )
        return new_username


class ApplicationRejectForm(forms.Form):
    """Required reason for rejecting a cooptation application. Free text
    matches the existing /admin/ action's behavior. The reason ends up in
    the rejection email to the candidate (cooptation.emails.send_application_rejected)
    so phrasing matters."""

    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        min_length=5,
        max_length=500,
        label="Motif de refus",
        help_text=(
            "Visible par le candidat dans l'email qu'il recevra. Restez factuel et bienveillant."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].widget.attrs.setdefault(
            "class",
            "block w-full rounded-lg border border-secondary/20 bg-white px-3 py-2"
            " text-base shadow-sm focus:border-tertiary focus:outline-none"
            " focus:ring-2 focus:ring-tertiary/30",
        )
