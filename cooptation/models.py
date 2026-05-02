"""Cooptation domain models."""

from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from members.models import GRADE_CHOICES


class AdminApplication(models.Model):
    STATUS_CHOICES = [
        ("cooptation_pending", "Cooptation en cours"),
        ("awaiting_admin", "En attente de l'admin"),
        ("approved", "Approuvé"),
        ("rejected", "Rejeté"),
        ("purged", "Purgé"),
    ]
    OUTCOME_CHOICES = [
        ("pending", "En attente"),
        ("all_accepted", "Deux accords"),
        ("mixed", "Un accord, un refus"),
        ("all_refused", "Deux refus"),
        ("expired", "Expiré (J+14)"),
    ]

    # PII — purged on retention expiry
    full_name = models.CharField(max_length=160, blank=True)
    nickname = models.CharField(max_length=60, blank=True)
    years_attended = ArrayField(models.IntegerField(), size=6, default=list)
    classes = ArrayField(
        models.CharField(max_length=4, choices=GRADE_CHOICES), size=4, default=list
    )
    city = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=80, blank=True, default="Niger")
    profession = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)

    # State
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="cooptation_pending")
    cooptation_outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES, default="pending")

    # Audit
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications",
    )
    review_note = models.TextField(blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    retention_until = models.DateTimeField(null=True, blank=True)
    purged_at = models.DateTimeField(null=True, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["email"]),
            models.Index(fields=["retention_until"]),
        ]
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.full_name or '<purged>'} ({self.status})"

    def purge(self) -> None:
        """Clear all PII fields; keep aggregate state for audit/stats."""
        self.full_name = ""
        self.nickname = ""
        self.email = ""
        self.whatsapp = ""
        self.city = ""
        self.country = ""
        self.profession = ""
        self.review_note = ""
        self.source_ip = None
        self.status = "purged"
        self.purged_at = timezone.now()
        self.save()
