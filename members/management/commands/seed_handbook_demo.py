"""seed_handbook_demo — deterministic dataset for handbook flow scripts.

Builds a small but rich set of fixture objects that the Playwright
handbook flows drive against:

  - 1 co-admin user (`demo_coadmin`)
  - 12 members with realistic Niger-region names spanning all six
    promotion years (1980-1985)
  - 3 published Memory entries
  - 1 published In Memoriam entry (with the family-consent fields
    required by Annexe D §D.5)
  - 1 cooptation application with 2 pending CooptationRequest entries

The command is idempotent (safe to re-run) and additive (does NOT
touch the real super-admin `bominomla` or any non-`demo_*` data).
Use `--reset` to wipe + recreate only the demo objects.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cooptation.models import AdminApplication, CooptationRequest
from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord, Member
from memoires.models import Memory
from memoriam.models import InMemoriamEntry

DEMO_USER_PREFIX = "demo_"
DEMO_COADMIN_USERNAME = "demo_coadmin"
DEMO_PASSWORD = "demo-handbook-pw"  # nosec B105 — local-only handbook fixture

# Fixed dataset. The flow scripts reference some of these by username, so
# changes here can break flows. Every promotion year (1980-1985) appears
# in at least one member's `years_attended`.
DEMO_MEMBERS = [
    # 01 — Zinder, infirmière, two-promo cohort
    {
        "username": "demo_member_01",
        "first": "Aïcha",
        "last": "Moussa",
        "years": [1980, 1981, 1982, 1983],
        "classes": ["6e", "5e", "4e", "3e"],
        "city": "Zinder",
        "profession": "Infirmière",
        "whatsapp": "22790000001",
    },
    {
        "username": "demo_member_02",
        "first": "Boubacar",
        "last": "Issoufou",
        "years": [1980, 1981],
        "classes": ["6e", "5e"],
        "city": "Niamey",
        "profession": "Comptable",
        "whatsapp": "22790000002",
    },
    {
        "username": "demo_member_03",
        "first": "Fatima",
        "last": "Ibrahim",
        "years": [1981, 1982, 1983, 1984],
        "classes": ["6eA", "5eA", "4eA", "3eA"],
        "city": "Maradi",
        "profession": "Enseignante",
        "whatsapp": "22790000003",
    },
    {
        "username": "demo_member_04",
        "first": "Hamadou",
        "last": "Souley",
        "years": [1982, 1983, 1984, 1985],
        "classes": ["6eB", "5eB", "4eB", "3eB"],
        "city": "Niamey",
        "profession": "Médecin",
        "whatsapp": "22790000004",
    },
    {
        "username": "demo_member_05",
        "first": "Mariama",
        "last": "Abdou",
        "years": [1983, 1984, 1985],
        "classes": ["6e", "5e", "4e"],
        "city": "Birni-N'Konni",
        "profession": "Commerçante",
        "whatsapp": "22790000005",
    },
    {
        "username": "demo_member_06",
        "first": "Salif",
        "last": "Garba",
        "years": [1980, 1981, 1982],
        "classes": ["6e", "5e", "4e"],
        "city": "Zinder",
        "profession": "Avocat",
        "whatsapp": "22790000006",
    },
    {
        "username": "demo_member_07",
        "first": "Zeinabou",
        "last": "Yacouba",
        "years": [1981, 1982, 1983, 1984, 1985],
        "classes": ["6eA", "5eA", "4eA", "3eA"],
        "city": "Paris",
        "country": "France",
        "profession": "Ingénieure",
        "whatsapp": "33612345678",
    },
    {
        "username": "demo_member_08",
        "first": "Ousmane",
        "last": "Daouda",
        "years": [1984, 1985],
        "classes": ["6e", "5e"],
        "city": "Tahoua",
        "profession": "Agriculteur",
        "whatsapp": "22790000008",
    },
    {
        "username": "demo_member_09",
        "first": "Habsatou",
        "last": "Maman",
        "years": [1980, 1981, 1982, 1983, 1984],
        "classes": ["6e", "5e", "4e", "3e"],
        "city": "Diffa",
        "profession": "Sage-femme",
        "whatsapp": "22790000009",
    },
    {
        "username": "demo_member_10",
        "first": "Idrissa",
        "last": "Hassane",
        "years": [1982, 1983],
        "classes": ["6eB", "5eB"],
        "city": "Niamey",
        "profession": "Mécanicien",
        "whatsapp": "22790000010",
    },
    {
        "username": "demo_member_11",
        "first": "Rakia",
        "last": "Saïdou",
        "years": [1983, 1984, 1985],
        "classes": ["6e", "5e", "4e"],
        "city": "Agadez",
        "profession": "Couturière",
        "whatsapp": "22790000011",
    },
    {
        "username": "demo_member_12",
        "first": "Yacouba",
        "last": "Adamou",
        "years": [1980, 1981, 1982, 1983],
        "classes": ["6eA", "5eA", "4eA", "3eA"],
        "city": "Tillabéri",
        "profession": "Fonctionnaire",
        "whatsapp": "22790000012",
    },
]

DEMO_MEMORIES = [
    {
        "caption": (
            "Photo de promotion 1983 — la cour du CEG 1 Birni un matin de juin. "
            "Au fond, le bâtiment des classes de 3e et le grand neem qui faisait "
            "de l'ombre pendant les récréations."
        ),
        "taken_at": date(1983, 6, 15),
        "location": "Birni-N'Konni",
        "public_id": "handbook_demo/promo_1983_cour",
    },
    {
        "caption": (
            "Sortie pédagogique au plateau de Tagayet en avril 1981. Les élèves "
            "de 4e et 5e accompagnés de M. Abdou (sciences naturelles)."
        ),
        "taken_at": date(1981, 4, 20),
        "location": "Tagayet",
        "public_id": "handbook_demo/sortie_tagayet_1981",
    },
    {
        "caption": (
            "Cérémonie de remise des diplômes 1985. Dernière promotion complète avant les réformes."
        ),
        "taken_at": date(1985, 7, 10),
        "location": "Birni-N'Konni",
        "public_id": "handbook_demo/diplomes_1985",
    },
]

DEMO_INMEMORIAM = {
    "full_name": "Souleymane Issa",
    "nickname": "Sou",
    "years_attended": [1980, 1981, 1982, 1983],
    "classes": ["6e", "5e", "4e", "3e"],
    "birth_year": 1965,
    "death_year": 2018,
    "tribute": (
        "Souleymane Issa, dit « Sou », nous a quittés en 2018 à Niamey. "
        "Camarade discret, infatigable joueur de babyfoot lors des "
        "récréations, il aura marqué la promotion 1983 par sa générosité. "
        "Sa famille a confirmé le 12 mars 2026 que cette fiche pouvait "
        "être publiée sur Les Retrouvailles."
    ),
    "consent_giver": "Mme Issa Aminatou (épouse)",
    "consent_canal": "phone",
}


class Command(BaseCommand):
    help = "Build the deterministic demo dataset for handbook flow scripts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all demo_* objects before recreating them.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()
        with transaction.atomic():
            coadmin = self._ensure_coadmin()
            members = self._ensure_members()
            self._ensure_memories(coadmin)
            self._ensure_inmemoriam(coadmin)
            self._ensure_cooptation(parrains=[members[0], members[5]])
        self.stdout.write(self.style.SUCCESS("seed_handbook_demo OK"))

    def _reset(self) -> None:
        # Delete in dependency order:
        #   - CooptationRequest references AdminApplication (CASCADE) +
        #     Member (PROTECT) — so requests must die before parrain users.
        #   - Memory.created_by is SET_NULL — survive user deletion as
        #     orphans, so we delete them explicitly.
        #   - InMemoriamEntry.created_by is PROTECT — fiche MUST be
        #     deleted before its created_by user.
        user_model = get_user_model()
        CooptationRequest.objects.filter(
            parrain__user__username__startswith=DEMO_USER_PREFIX,
        ).delete()
        AdminApplication.objects.filter(email__startswith=DEMO_USER_PREFIX).delete()
        Memory.objects.filter(created_by__username=DEMO_COADMIN_USERNAME).delete()
        InMemoriamEntry.objects.filter(
            created_by__username=DEMO_COADMIN_USERNAME,
        ).delete()
        user_model.objects.filter(username__startswith=DEMO_USER_PREFIX).delete()

    def _ensure_coadmin(self):
        user_model = get_user_model()
        coadmin, created = user_model.objects.get_or_create(
            username=DEMO_COADMIN_USERNAME,
            defaults={
                "email": "demo_coadmin@example.test",
                "is_staff": True,
                "is_superuser": False,
            },
        )
        # Always reset password — keeps storage_states bootstrap deterministic.
        coadmin.set_password(DEMO_PASSWORD)
        coadmin.is_staff = True
        coadmin.is_superuser = False
        coadmin.save()
        if created:
            self.stdout.write(f"  Created co-admin: {coadmin.username}")
        return coadmin

    def _ensure_members(self) -> list[Member]:
        user_model = get_user_model()
        members: list[Member] = []
        for spec in DEMO_MEMBERS:
            user, _ = user_model.objects.get_or_create(
                username=spec["username"],
                defaults={"email": f"{spec['username']}@example.test"},
            )
            user.set_password(DEMO_PASSWORD)
            user.save()
            member, _ = Member.objects.update_or_create(
                user=user,
                defaults={
                    "first_name": spec["first"],
                    "last_name": spec["last"],
                    "years_attended": spec["years"],
                    "classes": spec["classes"],
                    "city": spec["city"],
                    "country": spec.get("country", "Niger"),
                    "profession": spec["profession"],
                    "whatsapp": spec["whatsapp"],
                    "status": "active",
                },
            )
            ConsentRecord.objects.get_or_create(
                member=member,
                charter_version=CHARTER_CURRENT_VERSION,
                defaults={"ip_address": "127.0.0.1"},
            )
            members.append(member)
        return members

    def _ensure_memories(self, coadmin) -> None:
        for spec in DEMO_MEMORIES:
            Memory.objects.update_or_create(
                photo_public_id=spec["public_id"],
                defaults={
                    "caption": spec["caption"],
                    "taken_at": spec["taken_at"],
                    "location": spec["location"],
                    "status": "published",
                    "created_by": coadmin,
                },
            )

    def _ensure_inmemoriam(self, coadmin) -> None:
        spec = DEMO_INMEMORIAM
        InMemoriamEntry.objects.update_or_create(
            full_name=spec["full_name"],
            defaults={
                "nickname": spec["nickname"],
                "years_attended": spec["years_attended"],
                "classes": spec["classes"],
                "birth_year": spec["birth_year"],
                "death_year": spec["death_year"],
                "tribute": spec["tribute"],
                "family_consent_giver": spec["consent_giver"],
                "family_consent_date": date(2026, 3, 12),
                "family_consent_canal": spec["consent_canal"],
                "status": "published",
                "published_at": timezone.now(),
                "created_by": coadmin,
            },
        )

    def _ensure_cooptation(self, parrains: list[Member]) -> None:
        # One pending application sponsored by the first two demo members.
        # `email` starts with DEMO_USER_PREFIX so --reset finds it.
        application, _ = AdminApplication.objects.update_or_create(
            email="demo_candidate_halima@example.test",
            defaults={
                "full_name": "Halima Souley",
                "nickname": "Hali",
                "years_attended": [1982, 1983, 1984, 1985],
                "classes": ["6e", "5e", "4e", "3e"],
                "city": "Niamey",
                "country": "Niger",
                "profession": "Pharmacienne",
                "whatsapp": "22790000099",
                "status": "cooptation_pending",
                "cooptation_outcome": "pending",
            },
        )
        for parrain in parrains:
            CooptationRequest.objects.update_or_create(
                application=application,
                parrain=parrain,
                defaults={
                    "expires_at": timezone.now() + timedelta(days=14),
                    "response": "pending",
                },
            )
