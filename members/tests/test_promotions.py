"""Promotions — members-only class-roster archive.

Synthetic names ONLY. The real rosters are 335 living alumni and this repo is
public; nothing derived from them may land in git (see .gitignore).
"""

from __future__ import annotations

import csv
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client

CSV_FIELDS = [
    "source_ref",
    "school_year_start",
    "class_label",
    "first_name",
    "last_name",
    "nickname",
    "needs_review",
]


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    return path


def _row(**over):
    base = {
        "source_ref": "80-81:6eB:2",
        "school_year_start": "1980",
        "class_label": "6eB",
        "first_name": "Alpha",
        "last_name": "Testeur",
        "nickname": "",
        "needs_review": "",
    }
    base.update(over)
    return base


# ---------- model ----------


@pytest.mark.django_db
def test_entry_clean_rejects_year_outside_range():
    from members.models import ClassRosterEntry

    e = ClassRosterEntry(
        source_ref="x:1", school_year_start=1979, class_label="6eB", first_name="Alpha"
    )
    with pytest.raises(ValidationError):
        e.full_clean()


@pytest.mark.django_db
def test_entry_clean_rejects_unknown_class_label():
    from members.models import ClassRosterEntry

    e = ClassRosterEntry(
        source_ref="x:2", school_year_start=1980, class_label="7e", first_name="Alpha"
    )
    with pytest.raises(ValidationError):
        e.full_clean()


@pytest.mark.django_db
def test_entry_allows_blank_last_name():
    """20 real rows carry only one name component."""
    from members.models import ClassRosterEntry

    e = ClassRosterEntry(
        source_ref="x:3", school_year_start=1980, class_label="6eB", first_name="Mononyme"
    )
    e.full_clean()
    e.save()
    assert e.last_name == ""


# ---------- import command ----------


@pytest.mark.django_db
def test_import_is_idempotent_on_source_ref(tmp_path):
    from members.models import ClassRosterEntry

    csv_path = _write_csv(
        tmp_path / "r.csv", [_row(), _row(source_ref="80-81:6eB:3", first_name="Beta")]
    )
    call_command("import_class_roster", str(csv_path), stdout=StringIO())
    assert ClassRosterEntry.objects.count() == 2

    call_command("import_class_roster", str(csv_path), stdout=StringIO())
    assert ClassRosterEntry.objects.count() == 2, "re-run must not duplicate"


@pytest.mark.django_db
def test_import_keeps_two_blank_surname_people_in_one_class(tmp_path):
    """Regression: keying idempotence on (year, class, first, last) would let
    two DIFFERENT blank-surname people collide and silently drop one."""
    from members.models import ClassRosterEntry

    rows = [
        _row(source_ref="80-81:6eA:5", class_label="6eA", first_name="Robot", last_name=""),
        _row(source_ref="80-81:6eA:9", class_label="6eA", first_name="Choffa", last_name=""),
    ]
    call_command(
        "import_class_roster", str(_write_csv(tmp_path / "r.csv", rows)), stdout=StringIO()
    )
    assert ClassRosterEntry.objects.filter(class_label="6eA").count() == 2


@pytest.mark.django_db
def test_import_dry_run_writes_nothing(tmp_path):
    from members.models import ClassRosterEntry

    csv_path = _write_csv(tmp_path / "r.csv", [_row()])
    call_command("import_class_roster", str(csv_path), "--dry-run", stdout=StringIO())
    assert ClassRosterEntry.objects.count() == 0


# ---------- privacy / auth gating ----------


@pytest.mark.django_db
def test_promotions_requires_login():
    """The whole point: these names are never exposed to anonymous visitors."""
    response = Client().get("/promotions/")
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_promotions_page_is_noindex(consenting_client, make_roster_entry):
    make_roster_entry()
    body = consenting_client.get("/promotions/").content.decode("utf-8")
    assert "noindex" in body


# ---------- pages ----------


@pytest.mark.django_db
def test_index_lists_classes_with_headcounts(consenting_client, make_roster_entry):
    make_roster_entry(class_label="6eB", first_name="Alpha")
    make_roster_entry(class_label="6eB", first_name="Beta")
    make_roster_entry(class_label="6eC", first_name="Gamma")

    body = consenting_client.get("/promotions/").content.decode("utf-8")
    assert "6eB" in body and "6eC" in body
    assert "/promotions/1980/6eB/" in body


@pytest.mark.django_db
def test_class_page_lists_entries_and_links_claimed_member(
    consenting_client, make_roster_entry, make_member
):
    member = make_member(first_name="Alpha", last_name="Testeur", status="active")
    make_roster_entry(first_name="Alpha", last_name="Testeur", member=member)
    make_roster_entry(first_name="Beta", last_name="Autre")
    # A row matching the VIEWER's own name — only such a row offers « C'est
    # moi », because can_claim() gates the button exactly like the POST does.
    viewer = consenting_client.member
    make_roster_entry(first_name=viewer.first_name, last_name=viewer.last_name)

    body = consenting_client.get("/promotions/1980/6eB/").content.decode("utf-8")
    assert "Alpha" in body and "Beta" in body
    assert f"/membres/{member.slug}/" in body, "claimed entry links to the Annuaire profile"
    assert "C&#x27;est moi" in body or "C'est moi" in body


@pytest.mark.django_db
def test_no_claim_button_on_entries_that_are_not_yours(consenting_client, make_roster_entry):
    """The button is gated by the same can_claim() guard as the POST, so it
    never dangles in front of a member who would just be refused."""
    make_roster_entry(first_name="Fernande", last_name="Bonkoungou")

    body = consenting_client.get("/promotions/1980/6eB/").content.decode("utf-8")
    assert "Fernande" in body
    assert "C&#x27;est moi" not in body and "C'est moi" not in body


@pytest.mark.django_db
def test_suspended_member_entry_is_not_linked(consenting_client, make_roster_entry, make_member):
    """profile_detail_view 404s for suspended members — don't link into a 404."""
    member = make_member(first_name="Alpha", last_name="Testeur", status="suspended")
    make_roster_entry(first_name="Alpha", last_name="Testeur", member=member)

    body = consenting_client.get("/promotions/1980/6eB/").content.decode("utf-8")
    assert f"/membres/{member.slug}/" not in body


# ---------- claim flow ----------


@pytest.mark.django_db
def test_member_can_claim_matching_entry(consenting_client, make_roster_entry):
    from members.models import AuditLog, ClassRosterEntry

    member = consenting_client.member
    entry = make_roster_entry(first_name=member.first_name, last_name=member.last_name)

    response = consenting_client.post(f"/promotions/entree/{entry.pk}/revendiquer/")
    assert response.status_code == 302

    entry.refresh_from_db()
    assert entry.member_id == member.pk
    log = AuditLog.objects.filter(action="promotions.entry.claimed").first()
    assert log is not None
    assert member.full_name in log.metadata.get("member_full_name", "")
    assert ClassRosterEntry.objects.get(pk=entry.pk).member_id == member.pk


@pytest.mark.django_db
def test_member_cannot_claim_unrelated_entry(consenting_client, make_roster_entry):
    """Impersonation guard: no shared name token -> refused."""
    entry = make_roster_entry(first_name="Fernande", last_name="Bonkoungou")

    response = consenting_client.post(f"/promotions/entree/{entry.pk}/revendiquer/")
    entry.refresh_from_db()
    assert entry.member is None
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_second_member_cannot_take_a_claimed_entry(
    consenting_client, make_roster_entry, make_member
):
    other = make_member(first_name="Alpha", last_name="Testeur")
    entry = make_roster_entry(
        first_name=consenting_client.member.first_name,
        last_name=consenting_client.member.last_name,
        member=other,
    )

    consenting_client.post(f"/promotions/entree/{entry.pk}/revendiquer/")
    entry.refresh_from_db()
    assert entry.member_id == other.pk, "already-claimed entry must not change hands"


@pytest.mark.django_db
def test_claimer_can_unclaim(consenting_client, make_roster_entry):
    from members.models import AuditLog

    member = consenting_client.member
    entry = make_roster_entry(
        first_name=member.first_name, last_name=member.last_name, member=member
    )

    consenting_client.post(f"/promotions/entree/{entry.pk}/revendiquer/", {"unclaim": "1"})
    entry.refresh_from_db()
    assert entry.member is None
    assert AuditLog.objects.filter(action="promotions.entry.unclaimed").exists()


# ---------- RGPD ----------


@pytest.mark.django_db
def test_rgpd_purge_deletes_claimed_roster_entries(make_member, make_roster_entry, settings):
    """A purge that leaves the person's full name in the roster is not a purge."""
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    settings.STORAGE_CLIENT_PATH = "alumni.storage.FakeStorage"
    from members.models import ClassRosterEntry
    from members.services import rgpd_purge_member

    member = make_member(first_name="Alpha", last_name="Testeur")
    entry = make_roster_entry(first_name="Alpha", last_name="Testeur", member=member)
    unrelated = make_roster_entry(first_name="Beta", last_name="Autre")

    summary = rgpd_purge_member(member, actor=None)

    assert not ClassRosterEntry.objects.filter(pk=entry.pk).exists()
    assert ClassRosterEntry.objects.filter(pk=unrelated.pk).exists()
    assert summary["deleted_counts"]["roster_entries"] == 1


@pytest.mark.django_db
def test_empty_archive_does_not_render_a_zero_count(consenting_client):
    """Regression (seen in prod before the data was imported): the count line
    rendered "0 camarades retrouvés" — the source-language plural rule pluralizes
    zero — above copy inviting you to find your class on an empty page."""
    body = consenting_client.get("/promotions/").content.decode("utf-8")
    assert "0 camarade" not in body
    assert "Retrouvez votre classe" not in body
    assert "seront publiées ici" in body


@pytest.mark.django_db
def test_populated_archive_renders_the_count(consenting_client, make_roster_entry):
    make_roster_entry()
    make_roster_entry()
    body = consenting_client.get("/promotions/").content.decode("utf-8")
    assert "2 camarades" in body


# ---------- claim hardening (external security review) ----------


@pytest.mark.django_db
def test_sharing_one_common_first_name_is_not_enough_to_claim(
    consenting_client, make_roster_entry, make_member, make_user
):
    """The reviewer's case: "Moussa Issoufou" could claim "Moussa Harouna"
    because they share the token "moussa". In a Sahelian cohort, given names
    like Moussa/Mariama/Ibrahim repeat constantly — one shared token is not
    identity, it is a coincidence."""
    from members.services import can_claim

    user = make_user()
    member = make_member(user=user, first_name="Moussa", last_name="Issoufou")
    entry = make_roster_entry(first_name="Moussa", last_name="Harouna")

    assert can_claim(entry, member) is False


@pytest.mark.django_db
def test_full_name_match_still_claims(make_roster_entry, make_member, make_user):
    from members.services import can_claim

    member = make_member(user=make_user(), first_name="Mahamadou", last_name="Laouali")
    entry = make_roster_entry(first_name="Mahamadou", last_name="Laouali")
    assert can_claim(entry, member) is True


@pytest.mark.django_db
def test_single_name_roster_entry_needs_the_surname_to_match_too(
    make_roster_entry, make_member, make_user
):
    """20 roster rows carry only a given name. Those must NOT become a free
    claim for anyone sharing that given name."""
    from members.services import can_claim

    member = make_member(user=make_user(), first_name="Fernande", last_name="Bonkoungou")
    entry = make_roster_entry(first_name="Fernande", last_name="")
    # A lone given name identifies nobody — an admin must make this link.
    assert can_claim(entry, member) is False


@pytest.mark.django_db
def test_nickname_match_counts_as_a_second_signal(make_roster_entry, make_member, make_user):
    """Surnoms are strong identifiers here — «Bomino» is one person."""
    from members.services import can_claim

    member = make_member(user=make_user(), first_name="Mahamadou", last_name="Laouali")
    entry = make_roster_entry(first_name="Mahamadou", last_name="Sani", nickname="Laouali")
    assert can_claim(entry, member) is True


@pytest.mark.django_db
def test_member_cannot_claim_two_entries_from_the_same_school_year(
    consenting_client, make_roster_entry
):
    """A pupil sits in ONE class per year. Claiming several entries for the same
    year is either a mistake or someone hoovering up identities."""
    from members.services import ClaimRefused, claim_entry

    member = consenting_client.member
    first = make_roster_entry(
        first_name=member.first_name, last_name=member.last_name, class_label="6eB"
    )
    second = make_roster_entry(
        first_name=member.first_name, last_name=member.last_name, class_label="6eC"
    )

    claim_entry(first, member=member, actor=member.user)
    with pytest.raises(ClaimRefused):
        claim_entry(second, member=member, actor=member.user)

    second.refresh_from_db()
    assert second.member is None


@pytest.mark.django_db
def test_member_may_claim_one_entry_per_year(consenting_client, make_roster_entry):
    """Repeating 6ème is legitimate — one entry in 1980 AND one in 1981."""
    from members.services import claim_entry

    member = consenting_client.member
    a = make_roster_entry(
        first_name=member.first_name, last_name=member.last_name, school_year_start=1980
    )
    b = make_roster_entry(
        first_name=member.first_name, last_name=member.last_name, school_year_start=1981
    )

    claim_entry(a, member=member, actor=member.user)
    claim_entry(b, member=member, actor=member.user)

    a.refresh_from_db()
    b.refresh_from_db()
    assert a.member_id == member.pk and b.member_id == member.pk
