"""F-22 — the gestion console searched the whole query as ONE substring, so an
operator typing a full name ("Alpha Bravo") got zero results, while the same
query works in the member-facing Annuaire. The two searches had drifted apart.

Synthetic names only — the real roster never enters the repo (public GitHub).
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from members.models import Member
from members.search import search_members_staff


@pytest.mark.django_db
class TestStaffSearch:
    def test_full_name_matches_across_two_fields(self, make_member):
        """The bug: 'Alpha Bravo' is a substring of neither first_name nor last_name."""
        target = make_member(first_name="Alpha", last_name="Bravo")
        make_member(first_name="Charlie", last_name="Delta")

        found = search_members_staff(Member.objects.all(), "Alpha Bravo")

        assert list(found) == [target]

    def test_tokens_are_anded_not_ored(self, make_member):
        make_member(first_name="Alpha", last_name="Bravo")
        other = make_member(first_name="Alpha", last_name="Delta")

        found = search_members_staff(Member.objects.all(), "Alpha Delta")

        assert list(found) == [other]

    def test_accent_and_case_insensitive(self, make_member):
        target = make_member(first_name="Amélie", last_name="Bravo")

        found = search_members_staff(Member.objects.all(), "amelie")

        assert list(found) == [target]

    def test_whatsapp_number_is_searchable(self, make_member):
        """Operators look people up from a WhatsApp DM, and Member.whatsapp is the
        messaging identity (CLAUDE.md) — searching it returned nothing before."""
        target = make_member(first_name="Alpha", last_name="Bravo", whatsapp="22790000123")
        make_member(first_name="Charlie", last_name="Delta", whatsapp="22790000999")

        found = search_members_staff(Member.objects.all(), "90000123")

        assert list(found) == [target]

    def test_staff_search_ignores_show_city(self, make_member):
        """The member-facing search gates city behind show_city. Staff already see
        the full record, so gating it there only hides it from the one person
        entitled to read it."""
        target = make_member(first_name="Alpha", last_name="Bravo", city="Zinder", show_city=False)

        found = search_members_staff(Member.objects.all(), "Zinder")

        assert list(found) == [target]

    def test_member_list_view_finds_a_full_name(self, client, coadmin_user, make_member):
        make_member(first_name="Alpha", last_name="Bravo")
        client.force_login(coadmin_user)

        response = client.get(reverse("gestion:member_list"), {"q": "Alpha Bravo"})

        assert response.status_code == 200
        assert b"Bravo" in response.content
