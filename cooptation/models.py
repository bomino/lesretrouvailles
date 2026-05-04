"""Cooptation domain models."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from members.models import VALID_CLASS_PATTERN, VALID_YEARS


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
    classes = ArrayField(models.CharField(max_length=4), size=4, default=list)
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
    questionnaire_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    # Stamped when the cron flips cooptation_outcome to "expired" and emails
    # the candidate the questionnaire link. Used to (a) avoid re-sending the
    # expired email on every cron run and (b) detect candidates who never
    # submit the questionnaire so they don't sit in cooptation_pending forever.
    cooptation_expired_at = models.DateTimeField(null=True, blank=True)

    # P4a: source-of-arrival capture from the public landing page.
    # Stored verbatim (sanitized for control chars + HTML special chars in the
    # signup view); no allowlist so future campaign labels work without code
    # changes. db_index on utm_source so list_filter doesn't sequential-scan.
    utm_source = models.CharField(max_length=80, blank=True, db_index=True)
    utm_campaign = models.CharField(max_length=80, blank=True)
    referrer = models.CharField(max_length=512, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["email"]),
            models.Index(fields=["retention_until"]),
        ]
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.full_name or '<purged>'} ({self.status})"

    def clean(self) -> None:
        """Validate years_attended + classes when an admin edits the
        application via /admin/cooptation/adminapplication/. The public
        signup form validates these too (cooptation/forms.py); this is the
        defense-in-depth path for admin edits, since dropping
        choices=GRADE_CHOICES from the inner CharField removed the only
        field-level guard."""
        super().clean()
        if any(y not in VALID_YEARS for y in self.years_attended):
            raise ValidationError({"years_attended": "Années hors plage 1980-1985."})
        if any(not VALID_CLASS_PATTERN.match(c) for c in self.classes):
            raise ValidationError(
                {"classes": "Classe inconnue. Format attendu : 6e, 6eA, 4eB, 3eC, etc."}
            )

    def purge(self) -> None:
        """Clear all PII fields; keep aggregate state for audit/stats.

        utm_source and utm_campaign are kept — they're aggregate labels
        ("whatsapp", "invitation") with no personal data and real analytical
        value post-purge. referrer is cleared because it can encode group
        membership (e.g., a WhatsApp group invite URL).
        """
        self.full_name = ""
        self.nickname = ""
        self.email = ""
        self.whatsapp = ""
        self.city = ""
        self.country = ""
        self.profession = ""
        self.review_note = ""
        self.source_ip = None
        self.referrer = ""
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
