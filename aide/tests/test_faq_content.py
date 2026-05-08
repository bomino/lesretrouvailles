"""Structural assertions on FAQ_ENTRIES.

These tests don't exercise the view — they enforce the shape of the data
itself, so a content edit can't accidentally ship an entry with a missing
field, an empty answer, or an unknown category.
"""

from django.urls import resolve
from django.urls.exceptions import Resolver404

from aide.faq import CATEGORIES, CATEGORY_META, FAQ_ENTRIES, FAQEntry


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


def test_category_meta_covers_all_categories():
    # Adding a category to CATEGORIES without adding it to CATEGORY_META is a
    # template crash waiting to happen — the view dereferences CATEGORY_META[name]
    # for icon and slug.
    missing = set(CATEGORIES) - set(CATEGORY_META.keys())
    assert not missing, f"CATEGORIES present but missing from CATEGORY_META: {sorted(missing)}"
    extra = set(CATEGORY_META.keys()) - set(CATEGORIES)
    assert not extra, f"CATEGORY_META has unknown categories: {sorted(extra)}"


def test_category_meta_slugs_are_unique():
    slugs = [meta["slug"] for meta in CATEGORY_META.values()]
    assert len(slugs) == len(set(slugs)), "duplicate slugs in CATEGORY_META"


def test_category_meta_entries_have_required_fields():
    for name, meta in CATEGORY_META.items():
        assert meta.get("icon"), f"Category {name!r} missing icon"
        assert meta.get("slug"), f"Category {name!r} missing slug"


def test_internal_related_links_resolve():
    """Every related_link starting with ``/`` must resolve through Django's
    URL dispatcher. Catches typos like ``/profil/edit/`` (real URL is
    ``/profil/``) or fabricated paths like ``/static/docs/guide_membre.md``.
    External URLs (http://, https://) are skipped — those break independently
    and are caught by manual review.
    """
    failures: list[str] = []
    for entry in FAQ_ENTRIES:
        for label, url in entry.related_links:
            if not url.startswith("/"):
                continue
            try:
                resolve(url)
            except Resolver404:
                failures.append(f"{entry.slug}: {label!r} -> {url!r}")
    assert not failures, "Broken internal related_links (URL doesn't resolve):\n  " + "\n  ".join(
        failures
    )
