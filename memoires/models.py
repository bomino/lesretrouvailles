"""Domain models for the memoires (Mur des souvenirs) app."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F


class Memory(models.Model):
    """A single curated photo on the Mur des souvenirs.

    Phase 1: admin-curated only (10-20 seed photos). Phase 2 will open
    uploads to members and add tags + droit-à-l'image workflow.
    """

    STATUS_CHOICES = [
        ("draft", "Brouillon"),
        ("published", "Publiée"),
    ]

    photo_public_id = models.CharField(
        max_length=200,
        help_text="Cloudinary public_id (auto-rempli par l'upload admin).",
    )
    caption = models.TextField(help_text="Description visible aux membres.")
    taken_at = models.DateField(
        null=True,
        blank=True,
        help_text="Date approximative — laisser vide si inconnue.",
    )
    location = models.CharField(
        max_length=120,
        blank=True,
        help_text="Lieu (ex. : Birni, Niamey, Paris).",
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memories_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Newest era first; NULL taken_at falls after dated entries.
        # F().desc(nulls_last=True) is required — Postgres default for
        # DESC is NULLS FIRST, so we must be explicit.
        ordering = [F("taken_at").desc(nulls_last=True), "-created_at"]
        indexes = [
            models.Index(fields=["status", "-taken_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.caption[:40]} ({self.taken_at or '—'})"
