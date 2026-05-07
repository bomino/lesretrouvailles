"""Forms for the /gestion/ console."""

from __future__ import annotations

from django import forms
from django.contrib.postgres.forms import SimpleArrayField

from members.models import VALID_CLASS_PATTERN, VALID_YEARS, AuditLog, Member


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
