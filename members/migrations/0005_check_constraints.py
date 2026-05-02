from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("members", "0004_unaccent_and_indexes")]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE members_member
                ADD CONSTRAINT members_member_status_valid
                CHECK (status IN ('active', 'suspended', 'deleted'));

            ALTER TABLE members_member
                ADD CONSTRAINT members_member_years_in_range
                CHECK (years_attended <@ ARRAY[1980,1981,1982,1983,1984,1985]);

            ALTER TABLE members_member
                ADD CONSTRAINT members_member_classes_in_set
                CHECK (classes <@ ARRAY['6e','5e','4e','3e']::varchar[]);
            """,
            reverse_sql="""
            ALTER TABLE members_member DROP CONSTRAINT IF EXISTS members_member_status_valid;
            ALTER TABLE members_member DROP CONSTRAINT IF EXISTS members_member_years_in_range;
            ALTER TABLE members_member DROP CONSTRAINT IF EXISTS members_member_classes_in_set;
            """,
        ),
    ]
