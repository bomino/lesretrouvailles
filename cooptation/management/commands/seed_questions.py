"""Seed the 3 default knowledge questions. Idempotent (uses get_or_create on position)."""

from django.core.management.base import BaseCommand

from cooptation.models import KnowledgeQuestion

DEFAULT_QUESTIONS = [
    {
        "position": 1,
        "kind": "closed",
        "text": "Cite un professeur du CEG 1 entre 1980 et 1985.",
        "answer_keys": [],
    },
    {
        "position": 2,
        "kind": "closed",
        "text": "Comment s'appelait la principale autorité du CEG 1 dans ces années ?",
        "answer_keys": [],
    },
    {
        "position": 3,
        "kind": "open",
        "text": "Décris en quelques phrases un souvenir précis de ta scolarité au CEG 1.",
        "answer_keys": [],
    },
]


class Command(BaseCommand):
    help = (
        "Seed the default knowledge questions. Admins must populate answer_keys "
        "via Django admin before launch."
    )

    def handle(self, *args, **opts):
        for entry in DEFAULT_QUESTIONS:
            KnowledgeQuestion.objects.get_or_create(
                position=entry["position"],
                defaults={
                    "kind": entry["kind"],
                    "text": entry["text"],
                    "answer_keys": entry["answer_keys"],
                    "is_active": True,
                },
            )
        self.stdout.write(self.style.SUCCESS("3 questions seeded (or already present)."))
