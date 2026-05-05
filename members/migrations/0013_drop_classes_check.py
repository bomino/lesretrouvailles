"""Drop the members_member_classes_in_set CHECK constraint.

The original constraint (from migration 0005) hard-coded the allowed
values to ['6e','5e','4e','3e'] — no section letters at all. That's
inconsistent with AdminApplication and InMemoriamEntry (which have no
such constraint and accept section-letter forms via the Python regex
in members.models.VALID_CLASS_PATTERN).

Dropping the constraint means Python validation in Member.clean() is
the canonical source of truth, matching the pattern used by the other
models. The regex is loosened in the same commit to also accept the
short form ("6a", "5b") alongside the long form ("6e", "6eA").
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0012_auditlog_rgpd_action"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE members_member "
                "DROP CONSTRAINT IF EXISTS members_member_classes_in_set;"
            ),
            reverse_sql=(
                "ALTER TABLE members_member "
                "ADD CONSTRAINT members_member_classes_in_set "
                "CHECK (classes <@ ARRAY['6e','5e','4e','3e']::varchar[]);"
            ),
        ),
    ]
