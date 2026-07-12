"""F-02: contact visibility must be opt-IN, as the guide and FAQ promise.

`show_email` and `show_whatsapp` defaulted to True while
docs/guides/guide_membre.md and aide/faq.py both tell members they are
"décoché par défaut". The launch import creates ~200 members straight from the
WhatsApp roster — every one of them would have published their phone number to
the whole directory on day one, having been told the opposite.

`show_city` stays True: the docs promise that one is checked by default.
"""

from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_new_member_hides_email_and_whatsapp_by_default(make_member):
    member = make_member()
    assert member.show_email is False
    assert member.show_whatsapp is False


@pytest.mark.django_db
def test_new_member_still_shows_city_by_default(make_member):
    """The docs promise city IS checked by default — don't over-correct."""
    member = make_member()
    assert member.show_city is True


@pytest.mark.django_db
def test_roster_imported_member_does_not_publish_their_phone(tmp_path, settings):
    """The launch path: a member created by the WhatsApp roster import must not
    have their number visible to the directory."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    import csv
    from io import StringIO

    from django.core.management import call_command

    from members.models import Member

    fields = ["first_name", "last_name", "whatsapp", "email", "years_attended", "city"]
    csv_path = tmp_path / "roster.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerow(
            {
                "first_name": "Prive",
                "last_name": "Membre",
                "whatsapp": "+22790000777",
                "email": "",
                "years_attended": "1980",
                "city": "Niamey",
            }
        )

    call_command(
        "import_whatsapp_roster",
        str(csv_path),
        "--magic-links-out",
        str(tmp_path / "links.csv"),
        stdout=StringIO(),
    )

    member = Member.objects.get(user__username="22790000777")
    assert member.whatsapp == "22790000777"
    assert member.show_whatsapp is False, "the roster import must not publish phone numbers"
    assert member.show_email is False


@pytest.mark.django_db
def test_profile_page_hides_contact_by_default(consenting_client, make_member, make_user):
    """End to end: with the defaults, another member sees no email/phone."""
    user = make_user(email="secret@example.test")
    target = make_member(user=user, whatsapp="22790000888")

    body = consenting_client.get(f"/membres/{target.slug}/").content.decode("utf-8")
    assert "secret@example.test" not in body
    assert "22790000888" not in body


@pytest.mark.django_db
def test_member_can_still_opt_in(consenting_client, make_member, make_user):
    """Opt-in must remain possible — this is a default change, not a removal."""
    user = make_user(email="public@example.test")
    target = make_member(user=user, whatsapp="22790000999", show_email=True, show_whatsapp=True)

    body = consenting_client.get(f"/membres/{target.slug}/").content.decode("utf-8")
    assert "public@example.test" in body
    assert "22790000999" in body


@pytest.mark.django_db
def test_data_migration_hides_contact_for_existing_members(make_member):
    """Existing rows were created under the old default=True. They were never
    given an informed choice (the guide told them it was off), so the migration
    flips everyone to hidden. Re-opting-in is one checkbox away."""
    from django.apps import apps as global_apps

    from members.migrations._helpers import hide_contact_by_default
    from members.models import Member

    member = make_member()
    Member.objects.filter(pk=member.pk).update(show_email=True, show_whatsapp=True, show_city=True)

    hide_contact_by_default(global_apps, None)

    member.refresh_from_db()
    assert member.show_email is False
    assert member.show_whatsapp is False
    assert member.show_city is True, "city visibility must be left alone"
