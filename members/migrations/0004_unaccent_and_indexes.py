from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("members", "0003_consentrecord")]

    operations = [
        UnaccentExtension(),
        migrations.RunSQL(
            # Schema-qualify `public.unaccent` inside the function body. An
            # IMMUTABLE function cannot depend on the caller's search_path,
            # which is what the planner enforces when the function is used
            # in an expression index. Without the prefix, Postgres rejects
            # the index creation on Railway's managed instance even though
            # local dev (where search_path happens to include public) works.
            # CREATE OR REPLACE so retries after a partial migration are safe.
            sql="""
            CREATE OR REPLACE FUNCTION unaccent_immutable(text) RETURNS text AS
            $$SELECT public.unaccent($1)$$
            LANGUAGE sql IMMUTABLE;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS unaccent_immutable(text);",
        ),
        migrations.RunSQL(
            # IF NOT EXISTS so a retry after partial application doesn't
            # crash; Postgres 9.5+ guarantees this.
            sql="""
            CREATE INDEX IF NOT EXISTS members_member_first_name_unaccent_idx
                ON members_member (LOWER(unaccent_immutable(first_name)));
            CREATE INDEX IF NOT EXISTS members_member_last_name_unaccent_idx
                ON members_member (LOWER(unaccent_immutable(last_name)));
            CREATE INDEX IF NOT EXISTS members_member_nickname_unaccent_idx
                ON members_member (LOWER(unaccent_immutable(nickname)));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS members_member_first_name_unaccent_idx;
            DROP INDEX IF EXISTS members_member_last_name_unaccent_idx;
            DROP INDEX IF EXISTS members_member_nickname_unaccent_idx;
            """,
        ),
    ]
