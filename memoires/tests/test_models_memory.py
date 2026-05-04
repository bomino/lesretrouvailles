"""Tests for the Memory model — fields, defaults, ordering."""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError


@pytest.mark.django_db
def test_memory_caption_required():
    """Caption is the only required text field. Saving without one
    must raise ValidationError on full_clean."""
    from memoires.models import Memory

    m = Memory(photo_public_id="memoires/sample", caption="")
    with pytest.raises(ValidationError):
        m.full_clean()


@pytest.mark.django_db
def test_memory_status_defaults_to_draft():
    from memoires.models import Memory

    m = Memory.objects.create(photo_public_id="memoires/x", caption="A caption.")
    assert m.status == "draft"


@pytest.mark.django_db
def test_memory_default_ordering_newest_taken_at_first():
    """Default queryset order: -taken_at, -created_at. Memories with NULL
    taken_at fall after dated entries (Postgres NULLS LAST on DESC)."""
    from memoires.models import Memory

    Memory.objects.create(
        photo_public_id="memoires/a",
        caption="Older",
        taken_at=date(1981, 6, 1),
    )
    Memory.objects.create(
        photo_public_id="memoires/b",
        caption="Newer",
        taken_at=date(1983, 6, 1),
    )
    Memory.objects.create(
        photo_public_id="memoires/c",
        caption="Undated",
    )

    captions = list(Memory.objects.values_list("caption", flat=True))
    assert captions[0] == "Newer"
    assert captions[1] == "Older"
    assert captions[2] == "Undated"
