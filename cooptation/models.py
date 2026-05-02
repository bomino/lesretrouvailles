"""Cooptation domain models."""

from __future__ import annotations

import secrets

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


def _make_token() -> str:
    return secrets.token_urlsafe(32)


class CooptationRequest(models.Model):
    RESPONSE_CHOICES = [
        ("pending", "En attente"),
        ("accepted", "Accordée"),
        ("refused", "Refusée"),
    ]

    application = models.ForeignKey(
        AdminApplication,
        on_delete=models.CASCADE,
        related_name="cooptation_requests",
    )
    parrain = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        related_name="cooptation_requests",
    )
    token = models.CharField(max_length=64, unique=True, default=_make_token)
    expires_at = models.DateTimeField()
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    response = models.CharField(max_length=16, choices=RESPONSE_CHOICES, default="pending")
    responded_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["application", "response"]),
            models.Index(fields=["expires_at", "response"]),
        ]
        ordering = ["expires_at"]

    def __str__(self) -> str:
        return f"{self.parrain} → {self.application} ({self.response})"


class KnowledgeQuestion(models.Model):
    KIND_CHOICES = [
        ("closed", "Réponse courte"),
        ("open", "Réponse libre"),
    ]
    position = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    text = models.CharField(max_length=500)
    answer_keys = ArrayField(
        models.CharField(max_length=80),
        default=list,
        blank=True,
        help_text="Clés de réponse acceptées (insensible à accents/casse).",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]

    def __str__(self) -> str:
        return f"Q{self.position}: {self.text[:40]}"


class QuestionnaireResponse(models.Model):
    application = models.ForeignKey(
        AdminApplication,
        on_delete=models.CASCADE,
        related_name="questionnaire_responses",
    )
    question = models.ForeignKey(KnowledgeQuestion, on_delete=models.PROTECT)
    candidate_answer = models.TextField()
    auto_grade = models.BooleanField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("application", "question")]
        ordering = ["question__position"]

    def __str__(self) -> str:
        return f"Q{self.question.position} → {self.application}"
