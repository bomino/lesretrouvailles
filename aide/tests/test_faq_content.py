"""Structural assertions on FAQ_ENTRIES.

These tests don't exercise the view — they enforce the shape of the data
itself, so a content edit can't accidentally ship an entry with a missing
field, an empty answer, or an unknown category.
"""

from aide.faq import CATEGORIES, FAQ_ENTRIES, FAQEntry


def test_all_entries_are_faq_entry_instances():
    assert all(isinstance(e, FAQEntry) for e in FAQ_ENTRIES)


def test_entries_have_required_fields_filled():
    for entry in FAQ_ENTRIES:
        assert entry.slug
        assert entry.category
        assert entry.question
        assert entry.answer_md
        assert isinstance(entry.related_links, list)


def test_entry_slugs_are_unique():
    slugs = [e.slug for e in FAQ_ENTRIES]
    assert len(slugs) == len(set(slugs)), "duplicate slugs in FAQ_ENTRIES"


def test_categories_are_known():
    for entry in FAQ_ENTRIES:
        assert entry.category in CATEGORIES, (
            f"Entry {entry.slug!r} has unknown category {entry.category!r}; "
            f"add it to CATEGORIES or use one of {CATEGORIES}"
        )


def test_related_links_shape():
    for entry in FAQ_ENTRIES:
        for link in entry.related_links:
            assert isinstance(link, tuple) and len(link) == 2
            label, url = link
            assert label and url


def test_we_have_a_reasonable_number_of_entries():
    # Spec § G targets 18 entries across 8 categories. Drift bounds check.
    assert 12 <= len(FAQ_ENTRIES) <= 30


def test_each_category_has_at_least_one_entry():
    used = {e.category for e in FAQ_ENTRIES}
    missing = set(CATEGORIES) - used
    assert not missing, f"Categories with no FAQ entry: {sorted(missing)}"
