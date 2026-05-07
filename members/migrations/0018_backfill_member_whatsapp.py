"""Backfill Member.whatsapp from User.username for existing rows.

For members imported via import_whatsapp_roster, User.username IS the
WhatsApp digits — backfilling is a clean copy. For coopted members
(username = email) and the super-admin (username = 'bominomla'), the
username doesn't match the digits format and the field stays blank;
admins fill it in via /gestion/membres/<slug>/modifier/ as needed.
"""

from __future__ import annotations

import re

from django.db import migrations

DIGITS_ONLY = re.compile(r"^\d{8,15}$")


def backfill(apps, schema_editor):
    Member = apps.get_model("members", "Member")
    updates = []
    for member in Member.objects.select_related("user").iterator():
        username = member.user.username if member.user_id else ""
        if DIGITS_ONLY.fullmatch(username):
            member.whatsapp = username
            updates.append(member)
    Member.objects.bulk_update(updates, ["whatsapp"], batch_size=100)


def reverse(apps, schema_editor):
    Member = apps.get_model("members", "Member")
    Member.objects.update(whatsapp="")


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0017_member_whatsapp_field"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse),
    ]
