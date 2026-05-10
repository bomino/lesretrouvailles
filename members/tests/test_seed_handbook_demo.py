"""Tests for the seed_handbook_demo management command.

The command builds a deterministic dataset that the Playwright handbook
flows drive against. It must be:
  - Idempotent (running twice produces the same end state).
  - Additive next to seed_members fixtures (does not touch bominomla).
  - Tagged so --reset can wipe only what it created.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from cooptation.models import AdminApplication, CooptationRequest
from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord, Member
from memoires.models import Memory
from memoriam.models import InMemoriamEntry

pytestmark = pytest.mark.django_db


# Number of demo objects the command must produce. Pinned so a future
# refactor can't silently shrink the dataset (which would leave handbook
# flows depending on records that no longer exist).
EXPECTED_DEMO_MEMBERS = 12
EXPECTED_PUBLISHED_MEMORIES = 3
EXPECTED_PUBLISHED_INMEMORIAM = 1
EXPECTED_COOPTATION_REQUESTS = 2


def _demo_member_count() -> int:
    user_model = get_user_model()
    return user_model.objects.filter(username__startswith="demo_member_").count()


def _demo_coadmin_count() -> int:
    user_model = get_user_model()
    return user_model.objects.filter(username="demo_coadmin").count()


class TestSeedHandbookDemo:
    def test_command_creates_expected_dataset(self):
        call_command("seed_handbook_demo")

        assert _demo_member_count() == EXPECTED_DEMO_MEMBERS
        assert _demo_coadmin_count() == 1
        assert Member.objects.filter(user__username__startswith="demo_member_").count() == (
            EXPECTED_DEMO_MEMBERS
        )
        assert Memory.objects.filter(status="published").count() >= (EXPECTED_PUBLISHED_MEMORIES)
        assert InMemoriamEntry.objects.filter(status="published").count() >= (
            EXPECTED_PUBLISHED_INMEMORIAM
        )
        assert AdminApplication.objects.count() >= 1
        assert CooptationRequest.objects.count() >= EXPECTED_COOPTATION_REQUESTS

    def test_command_is_idempotent(self):
        call_command("seed_handbook_demo")
        first_member_count = _demo_member_count()
        first_memory_count = Memory.objects.count()

        call_command("seed_handbook_demo")

        assert _demo_member_count() == first_member_count
        assert Memory.objects.count() == first_memory_count

    def test_reset_flag_recreates_dataset(self):
        call_command("seed_handbook_demo")
        before = _demo_member_count()

        call_command("seed_handbook_demo", "--reset")

        # Same count, fresh objects (we don't assert PKs because that
        # would be over-specifying — the contract is "deterministic
        # dataset," not "stable PKs across resets").
        assert _demo_member_count() == before

    def test_demo_members_span_all_promotion_years(self):
        call_command("seed_handbook_demo")

        years_seen: set[int] = set()
        for member in Member.objects.filter(user__username__startswith="demo_member_"):
            years_seen.update(member.years_attended)

        # The audience covers promotions 1980-1985 (six years). Every year
        # must show up at least once so the directory-search flow can
        # exercise year filters meaningfully.
        assert years_seen == {1980, 1981, 1982, 1983, 1984, 1985}

    def test_demo_members_have_charter_consent(self):
        # Without a ConsentRecord at the current charter version,
        # ConsentRequiredMiddleware redirects every URL to /charte/, which
        # breaks every handbook flow that depends on a logged-in member
        # actually landing on the page they navigated to.
        call_command("seed_handbook_demo")

        members = Member.objects.filter(user__username__startswith="demo_member_")
        assert members.count() == EXPECTED_DEMO_MEMBERS
        for member in members:
            assert ConsentRecord.objects.filter(
                member=member,
                charter_version=CHARTER_CURRENT_VERSION,
            ).exists(), f"missing consent for {member.user.username}"

    def test_command_does_not_touch_bominomla(self):
        user_model = get_user_model()
        user_model.objects.create_superuser(
            username="bominomla",
            email="bomino@example.test",
            password="real-password",
        )

        call_command("seed_handbook_demo")
        call_command("seed_handbook_demo", "--reset")

        bomino = user_model.objects.get(username="bominomla")
        # Real bominomla survives both calls; --reset only nukes demo_*.
        assert bomino.is_superuser
        assert bomino.check_password("real-password")
