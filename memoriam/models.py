"""Domain models for the In Memoriam (P5b) app."""

from __future__ import annotations

import re

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import Truncator

from members.models import VALID_CLASS_PATTERN

VALID_YEARS = range(1980, 1986)  # 1980-1985 inclusive

CANAL_CHOICES = [
    ("email", "Email"),
    ("whatsapp", "WhatsApp"),
    ("phone", "Téléphone"),
    ("in_person", "En personne"),
]

STATUS_CHOICES = [
    ("draft", "Brouillon"),
    ("published", "Publiée"),
    ("archived", "Archivée"),
]

# Markdown tokens we strip from teaser previews. Bold/italic/code/heading/
# blockquote/link brackets — fast and dependency-free; the detail-page
# render uses the real markdown lib.
_MD_TOKENS = re.compile(r"[*_`#>\[\]]+")


class InMemoriamEntryQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status="published")


class InMemoriamEntry(models.Model):
    """An admin-curated fiche honoring a deceased CEG 1 Birni alum.

    Family consent (Annexe D §D.5) is mandatory before publication;
    consent_giver/date/canal fields are required at the model level when
    status == 'published' so an admin shortcut can't bypass the rule.
    """

    STATUS_CHOICES = STATUS_CHOICES

    full_name = models.CharField(max_length=200)
    nickname = models.CharField(max_length=80, blank=True)
    years_attended = ArrayField(
        models.IntegerField(),
        size=6,
        default=list,
        blank=True,
    )
    classes = ArrayField(
        models.CharField(max_length=8),
        size=8,
        default=list,
        blank=True,
    )
    birth_year = models.IntegerField(null=True, blank=True)
    death_year = models.IntegerField(null=True, blank=True)

    photo_public_id = models.CharField(max_length=200, blank=True)
    tribute = models.TextField()

    family_consent_giver = models.CharField(max_length=200, blank=True)
    family_consent_date = models.DateField(null=True, blank=True)
    family_consent_canal = models.CharField(
        max_length=16,
        choices=CANAL_CHOICES,
        blank=True,
    )
    approved_content_version = models.IntegerField(default=1)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="memoriam_entries_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")

    objects = InMemoriamEntryQuerySet.as_manager()

    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["status", "full_name"])]
        verbose_name = "Fiche In Memoriam"
        verbose_name_plural = "Fiches In Memoriam"

    def __str__(self) -> str:
        return self.full_name

    def get_absolute_url(self) -> str:
        return reverse("memoriam:detail", args=[self.pk])

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        bad_years = [y for y in self.years_attended if y not in VALID_YEARS]
        if bad_years:
            errors["years_attended"] = (
                f"Années invalides : {bad_years}. Plage autorisée : 1980-1985."
            )

        bad_classes = [c for c in self.classes if not VALID_CLASS_PATTERN.match(c)]
        if bad_classes:
            errors["classes"] = (
                f"Classes invalides : {bad_classes}. Format attendu : 6e, 6eA, 5eB, etc."
            )

        if self.birth_year and self.death_year and self.birth_year >= self.death_year:
            errors["death_year"] = "L'année de décès doit être postérieure à la naissance."

        if self.death_year and self.years_attended:
            max_year = max(self.years_attended)
            if self.death_year < max_year:
                errors["death_year"] = (
                    f"L'année de décès ({self.death_year}) ne peut être antérieure "
                    f"à la dernière année au CEG ({max_year})."
                )

        if self.status == "published":
            for f in ("family_consent_giver", "family_consent_date", "family_consent_canal"):
                if not getattr(self, f):
                    errors[f] = "Champ requis pour publier (Annexe D §D.5)."

        if errors:
            raise ValidationError(errors)

    @property
    def tribute_teaser(self) -> str:
        plain = _MD_TOKENS.sub("", self.tribute or "")
        return Truncator(plain).chars(120, html=False, truncate="…")


NOMINATION_STATUS_CHOICES = [
    ("pending", "À examiner"),
    ("accepted", "Acceptée"),
    ("declined", "Refusée"),
    ("duplicate", "Doublon"),
]


class InMemoriamNomination(models.Model):
    """A member-submitted nomination for an In Memoriam fiche.

    Annexe D §D.1 prohibits members from creating fiches directly. This
    model captures their proposal so an admin can run the consent process
    offline and then create the fiche.
    """

    STATUS_CHOICES = NOMINATION_STATUS_CHOICES

    nominator = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        related_name="memoriam_nominations",
    )
    proposed_name = models.CharField(max_length=200)
    proposed_nickname = models.CharField(max_length=80, blank=True)
    proposed_years = ArrayField(
        models.IntegerField(),
        size=6,
        default=list,
        blank=True,
    )
    personal_memory = models.TextField()
    family_contact_hint = models.TextField(blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="pending",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memoriam_nominations_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)
    linked_entry = models.ForeignKey(
        InMemoriamEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nominations",
    )

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Nomination In Memoriam"
        verbose_name_plural = "Nominations In Memoriam"

    def __str__(self) -> str:
        return f"{self.proposed_name} (par {self.nominator})"
