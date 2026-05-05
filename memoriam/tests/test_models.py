"""Tests for memoriam.models — InMemoriamEntry."""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError


@pytest.mark.django_db
def test_entry_default_status_is_draft(make_admin_user):
    from memoriam.models import InMemoriamEntry

    entry = InMemoriamEntry.objects.create(
        full_name="Foo Bar",
        years_attended=[1980],
        classes=["6e"],
        tribute="x",
        family_consent_giver="Mère",
        family_consent_date=date(2026, 1, 1),
        family_consent_canal="email",
        created_by=make_admin_user(),
    )
    assert entry.status == "draft"
    assert entry.published_at is None
    assert entry.approved_content_version == 1


@pytest.mark.django_db
def test_entry_status_choices(make_admin_user):
    from memoriam.models import InMemoriamEntry

    expected = {"draft", "published", "archived"}
    actual = {choice for choice, _ in InMemoriamEntry.STATUS_CHOICES}
    assert actual == expected


@pytest.mark.django_db
def test_entry_clean_rejects_years_outside_range(make_memoriam_entry):
    entry = make_memoriam_entry()
    entry.years_attended = [1979, 1980]
    with pytest.raises(ValidationError):
        entry.full_clean()


@pytest.mark.django_db
def test_entry_clean_rejects_invalid_class(make_memoriam_entry):
    entry = make_memoriam_entry()
    entry.classes = ["6e", "xyz"]
    with pytest.raises(ValidationError):
        entry.full_clean()


@pytest.mark.django_db
def test_entry_clean_rejects_published_without_consent(make_memoriam_entry):
    entry = make_memoriam_entry()
    entry.status = "published"
    entry.family_consent_giver = ""
    with pytest.raises(ValidationError):
        entry.full_clean()


@pytest.mark.django_db
def test_entry_clean_rejects_birth_after_death(make_memoriam_entry):
    entry = make_memoriam_entry()
    entry.birth_year = 2000
    entry.death_year = 1990
    with pytest.raises(ValidationError):
        entry.full_clean()


@pytest.mark.django_db
def test_entry_clean_rejects_death_before_ceg_attendance(make_memoriam_entry):
    """Years_attended max 1981 — dying in 1979 is impossible."""
    entry = make_memoriam_entry()
    entry.years_attended = [1980, 1981]
    entry.death_year = 1979
    with pytest.raises(ValidationError):
        entry.full_clean()


@pytest.mark.django_db
def test_published_queryset_excludes_drafts_and_archived(make_memoriam_entry):
    from memoriam.models import InMemoriamEntry

    pub = make_memoriam_entry(status="published")
    make_memoriam_entry(status="draft")
    make_memoriam_entry(status="archived")
    qs = InMemoriamEntry.objects.published()
    assert list(qs) == [pub]


@pytest.mark.django_db
def test_tribute_teaser_strips_markdown_and_truncates(make_memoriam_entry):
    entry = make_memoriam_entry(
        tribute="**Mariama** était une femme exceptionnelle. " * 10,
    )
    teaser = entry.tribute_teaser
    assert "**" not in teaser
    assert len(teaser) <= 121  # 120 + ellipsis char
    assert teaser.endswith("…")


@pytest.mark.django_db
def test_nomination_default_status_is_pending(make_memoriam_nomination):
    nom = make_memoriam_nomination()
    assert nom.status == "pending"
    assert nom.reviewed_at is None
    assert nom.reviewed_by is None
    assert nom.linked_entry is None


@pytest.mark.django_db
def test_nomination_status_choices(make_memoriam_nomination):
    from memoriam.models import InMemoriamNomination

    expected = {"pending", "accepted", "declined", "duplicate"}
    actual = {choice for choice, _ in InMemoriamNomination.STATUS_CHOICES}
    assert actual == expected
