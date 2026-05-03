"""Domain models for the membership app."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models

GRADE_CHOICES = [
    ("6e", "6e"),
    ("5e", "5e"),
    ("4e", "4e"),
    ("3e", "3e"),
]
VALID_GRADES = {key for key, _ in GRADE_CHOICES}

STATUS_CHOICES = [
    ("active", "Actif"),
    ("suspended", "Suspendu"),
    ("deleted", "Supprimé"),
]

VALID_YEARS = range(1980, 1986)


def default_years() -> list[int]:
    return []


def default_classes() -> list[str]:
    return []


class Member(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member",
    )
    slug = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    nickname = models.CharField(max_length=60, blank=True)

    years_attended = ArrayField(
        models.IntegerField(),
        size=6,
        default=default_years,
    )
    classes = ArrayField(
        models.CharField(max_length=4, choices=GRADE_CHOICES),
        size=4,
        default=default_classes,
    )

    city = models.CharField(max_length=80)
    country = models.CharField(max_length=80, default="Niger")
    profession = models.CharField(max_length=120, blank=True)

    photo_public_id = models.CharField(max_length=200, blank=True)

    show_email = models.BooleanField(default=True)
    show_whatsapp = models.BooleanField(default=True)
    show_city = models.BooleanField(default=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["country"]),
        ]

    def __str__(self) -> str:
        return self.full_name

    def save(self, *args, **kwargs):
        if self.city:
            self.city = self.city.strip().title()
        if self.country:
            self.country = self.country.strip().title()
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self) -> None:
        super().clean()
        if any(y not in VALID_YEARS for y in self.years_attended):
            raise ValidationError({"years_attended": "Années hors plage 1980-1985."})
        if any(c not in VALID_GRADES for c in self.classes):
            raise ValidationError({"classes": "Classe inconnue."})


class NotificationPreference(models.Model):
    member = models.OneToOneField(
        Member,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    digest_weekly = models.BooleanField(default=False)
    in_memoriam_alerts = models.BooleanField(default=True)
    event_alerts = models.BooleanField(default=False)
    tag_alerts = models.BooleanField(default=True)
    data_saver = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Preferences for {self.member.full_name}"


class ConsentRecord(models.Model):
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="consents",
    )
    charter_version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()

    class Meta:
        indexes = [models.Index(fields=["member", "charter_version"])]
        ordering = ["-accepted_at"]

    def __str__(self) -> str:
        return f"{self.member.full_name} → charter v{self.charter_version}"


class PublicSearchEntry(models.Model):
    """A name on the public 'Nous recherchons aussi…' list.

    Strict minimum-PII shape (master spec § 6.5): first name + last initial
    + years only. The model has no email/city/profession fields by design.

    Publication is gated by added_by_admins.count() >= 2 — there is no
    'is_published' boolean a single admin can toggle. Removal is signaled
    by setting removed_at; removed entries never publish even if they have
    many admin signoffs.
    """

    first_name = models.CharField(max_length=60)
    last_name_initial = models.CharField(max_length=10)
    years_at_ceg = ArrayField(models.IntegerField(), size=6)
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optionnel — courte ligne d'introduction visible publiquement.",
    )

    added_by_admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="ghost_entries_signed",
        blank=True,
    )
    added_at = models.DateTimeField(auto_now_add=True)

    # Reserved for P4b's public removal flow.
    removal_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["last_name_initial", "first_name"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(last_name_initial__regex=r"^[A-Za-zÀ-ÿ.]{1,2}$"),
                name="initial_must_be_one_or_two_chars",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.first_name} {self.last_name_initial} ({', '.join(map(str, self.years_at_ceg))})"
        )

    @property
    def is_published(self) -> bool:
        """True if 2+ admins have signed and the entry has not been removed.

        Issues a SELECT COUNT(*) query each call. For bulk rendering (e.g.,
        the public landing's ghost list), prefer the annotated queryset:
            qs.annotate(n=Count("added_by_admins")).filter(n__gte=2)
        """
        return self.removed_at is None and self.added_by_admins.count() >= 2

    @property
    def first_year(self) -> int | None:
        """Smallest year in years_at_ceg, regardless of input order.

        The template renders "first_year-last_year" for the public ghost
        card. Using min/max instead of |first/|last guards against admins
        entering [1982, 1980] which would otherwise display as "1982-1980".
        """
        return min(self.years_at_ceg) if self.years_at_ceg else None

    @property
    def last_year(self) -> int | None:
        return max(self.years_at_ceg) if self.years_at_ceg else None
