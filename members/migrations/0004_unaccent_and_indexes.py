from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("members", "0003_consentrecord")]

    operations = [
        UnaccentExtension(),
        migrations.RunSQL(
            sql="""
            CREATE FUNCTION unaccent_immutable(text) RETURNS text AS
            $$SELECT unaccent($1)$$
            LANGUAGE sql IMMUTABLE;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS unaccent_immutable(text);",
        ),
        migrations.RunSQL(
            sql="""
            CREATE INDEX members_member_first_name_unaccent_idx
                ON members_member (LOWER(unaccent_immutable(first_name)));
            CREATE INDEX members_member_last_name_unaccent_idx
                ON members_member (LOWER(unaccent_immutable(last_name)));
            CREATE INDEX members_member_nickname_unaccent_idx
                ON members_member (LOWER(unaccent_immutable(nickname)));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS members_member_first_name_unaccent_idx;
            DROP INDEX IF EXISTS members_member_last_name_unaccent_idx;
            DROP INDEX IF EXISTS members_member_nickname_unaccent_idx;
            """,
        ),
    ]
