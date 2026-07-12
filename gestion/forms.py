"""Forms for the /gestion/ console."""

from __future__ import annotations

import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.postgres.forms import SimpleArrayField

from members.models import VALID_CLASS_PATTERN, VALID_YEARS, AuditLog, Member
from memoires.models import Memory

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
    # Override the form field's max_length so a pasted "+227 90 00 01 23"
    # (16 chars with spaces and +) reaches clean_whatsapp before being
    # rejected by Django's CharField max-length validator. clean_whatsapp
    # strips to digits and Member.clean enforces the canonical 8-15 digits.
    whatsapp = forms.CharField(
        max_length=30,
        required=False,
        label="Numéro WhatsApp",
        help_text=(
            "Numéro avec code pays, ex. <code>22790000123</code> (Niger) "
            "ou <code>15551234567</code> (USA). Vous pouvez coller depuis "
            "WhatsApp avec « + » et espaces — ils seront supprimés "
            "automatiquement. Laissez vide si le membre n'a pas WhatsApp."
        ),
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
            "whatsapp",
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

    def clean_email(self):
        """ACCOUNT_LOGIN_METHODS includes 'email': two Users sharing an email
        makes email+password login ambiguous for both, and approval / RGPD
        purge paths assume uniqueness. Mirrors clean_new_username's
        collision check."""
        email = (self.cleaned_data.get("email") or "").strip()
        if email:
            collision = (
                get_user_model()
                .objects.filter(email__iexact=email)
                .exclude(pk=self.instance.user_id)
                .exists()
            )
            if collision:
                raise forms.ValidationError("Cet email est déjà utilisé par un autre compte.")
        return email

    def clean_whatsapp(self):
        """Strip everything except digits so admins can paste 'WhatsApp-flavored'
        formats like '+1 555-123-4567' or '+227 90 00 01 23'. The length check
        (8-15 digits) still fires via Member.clean(), so a US local number
        '5551234567' (10 digits, no country code) would pass length but
        wa.me would 404 — operators are still responsible for including the
        country code, just not for stripping punctuation."""
        raw = self.cleaned_data.get("whatsapp") or ""
        return re.sub(r"\D", "", raw)

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
        max_length=30,
        help_text=(
            "Numéro avec code pays, ex. 22790000123. Vous pouvez coller avec "
            "« + », espaces ou tirets — ils seront supprimés automatiquement."
        ),
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
        # Strip non-digits silently so operators can paste WhatsApp-flavored
        # values like '+22790000123' or '+1 555-123-4567'. The 8-15 digit
        # length check still fires below, so a US local number missing the
        # country code is still rejected.
        raw = self.cleaned_data.get("new_username") or ""
        value = re.sub(r"\D", "", raw)
        if not USERNAME_DIGITS_RE.fullmatch(value):
            raise forms.ValidationError(
                "Format invalide : entre 8 et 15 chiffres après suppression "
                "des espaces et symboles. N'oubliez pas le code pays.",
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


class GestionMemoryForm(forms.ModelForm):
    """Memory create/edit form for /gestion/souvenirs/.

    Lifted from memoires.forms.MemoryAdminForm + hardened with the
    upload size/MIME guards the admin form doesn't enforce. Tailwind-
    styled inputs to fit the /gestion/ visual language.
    """

    ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
    MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8 MB

    upload = forms.FileField(
        required=False,
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "class": "block w-full text-base min-h-tap",
            }
        ),
        help_text="Choisir une photo (JPEG, PNG ou WebP, ≤ 8 Mo). "
        "Laisser vide pour conserver l'image existante.",
    )

    class Meta:
        model = Memory
        fields = ("caption", "taken_at", "location", "status")
        widgets = {
            "caption": forms.Textarea(attrs={"rows": 4}),
            "taken_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "block w-full rounded-lg border border-secondary/20 bg-white "
            "px-3 py-2.5 text-base shadow-sm focus:border-tertiary "
            "focus:outline-none focus:ring-2 focus:ring-tertiary/30 min-h-tap"
        )
        for name, field in self.fields.items():
            if name == "upload":
                continue
            field.widget.attrs.setdefault("class", input_class)

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if not upload:
            return upload  # may be empty on edit; whole-form clean re-checks create case
        if upload.size == 0:
            raise forms.ValidationError("Le fichier est vide.")
        if upload.size > self.MAX_UPLOAD_SIZE:
            raise forms.ValidationError("Photo trop volumineuse : 8 Mo maximum.")
        if upload.content_type not in self.ALLOWED_MIME_TYPES:
            raise forms.ValidationError("Format non pris en charge. Utilisez JPEG, PNG ou WebP.")
        return upload

    def clean(self):
        cleaned = super().clean()
        # On CREATE, upload is required.
        if not self.instance.pk and not cleaned.get("upload"):
            raise forms.ValidationError("Une photo est obligatoire pour créer une nouvelle entrée.")
        return cleaned
