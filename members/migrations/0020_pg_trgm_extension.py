"""Enable the `pg_trgm` Postgres contrib extension for trigram similarity.

Used by `members.search.search_members` as a typo-tolerance fallback when
multi-token AND-search returns zero results.

Reverse is intentionally a no-op: dropping an extension that any other
query may now depend on is a worse rollback story than leaving it
installed. `CREATE EXTENSION IF NOT EXISTS` is idempotent forward.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0019_alter_auditlog_action"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
