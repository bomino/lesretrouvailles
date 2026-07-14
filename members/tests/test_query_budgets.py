"""F-31 — query-count guardrails on the list pages.

These pages render one row per member, so an accidentally-dropped
`select_related` turns a page into an N+1: it stays correct, stays green in
every other test, and only shows up as a slow page on a low-end Android over a
Niger mobile connection — the exact audience we cannot afford to lose.

The budgets below are deliberately loose (a few queries of headroom for auth,
session and middleware). They are a ratchet against *growth*, not a
micro-optimisation: what matters is that doubling the number of rows does not
change the count. Each test asserts exactly that by rendering the page twice,
with 1 row and then with N.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

DIRECTORY_BUDGET = 12
PROMOTIONS_INDEX_BUDGET = 12
PROMOTION_CLASS_BUDGET = 12


@pytest.mark.django_db
class TestQueryBudgets:
    def test_directory_query_count_does_not_grow_with_members(
        self,
        consenting_client,
        make_member,
        django_assert_num_queries,
        django_assert_max_num_queries,
    ):
        url = reverse("members:directory")
        make_member(first_name="Alpha", last_name="Bravo")

        consenting_client.get(url)  # warm: the first request of a test pays
        # one-off costs (content-type cache, session row) that are not per-row.
        with django_assert_max_num_queries(DIRECTORY_BUDGET) as ctx:
            consenting_client.get(url)
        baseline = len(ctx.captured_queries)

        for i in range(10):
            make_member(first_name=f"Member{i}", last_name=f"Sur{i}")

        with django_assert_num_queries(baseline):
            consenting_client.get(url)

    def test_promotions_index_query_count_does_not_grow_with_classes(
        self,
        consenting_client,
        make_roster_entry,
        django_assert_num_queries,
        django_assert_max_num_queries,
    ):
        url = reverse("members:promotions_index")
        make_roster_entry(school_year_start=1980, class_label="6eA")

        consenting_client.get(url)  # warm (see above)
        with django_assert_max_num_queries(PROMOTIONS_INDEX_BUDGET) as ctx:
            consenting_client.get(url)
        baseline = len(ctx.captured_queries)

        # The headcounts must come from one aggregate, not one query per class.
        for label in ("6eB", "6eC", "6eD", "6eE", "6eF"):
            make_roster_entry(school_year_start=1980, class_label=label)

        with django_assert_num_queries(baseline):
            consenting_client.get(url)

    def test_promotion_class_query_count_does_not_grow_with_entries(
        self,
        consenting_client,
        make_roster_entry,
        make_member,
        django_assert_num_queries,
        django_assert_max_num_queries,
    ):
        """Each claimed row reaches through entry -> member -> user to build the
        profile link. Without select_related that is 2 extra queries per row."""
        url = reverse("members:promotion_class", args=[1980, "6eA"])

        make_roster_entry(
            school_year_start=1980, class_label="6eA", member=make_member(first_name="Alpha")
        )

        consenting_client.get(url)  # warm (see above)
        with django_assert_max_num_queries(PROMOTION_CLASS_BUDGET) as ctx:
            consenting_client.get(url)
        baseline = len(ctx.captured_queries)

        for i in range(8):
            make_roster_entry(
                school_year_start=1980,
                class_label="6eA",
                member=make_member(first_name=f"Claimed{i}"),
            )

        with django_assert_num_queries(baseline):
            consenting_client.get(url)
