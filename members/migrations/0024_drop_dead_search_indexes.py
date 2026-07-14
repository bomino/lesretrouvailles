"""Drop three btree indexes that Postgres could never use.

Migration 0004 created:

    CREATE INDEX ... ON members_member (LOWER(unaccent_immutable(first_name)));

...and two siblings, to speed up directory search. They have never served a
single query, for two independent reasons:

1. **Wrong function.** `members/search.py` builds its predicate with Django's
   `Unaccent`, which emits `UNACCENT(...)` — the extension's own function.
   The index is on `unaccent_immutable(...)`, the local wrapper 0004 defined.
   To the planner those are two unrelated expressions, so the index never
   matches the query.

2. **Wrong access method.** Even with the names aligned, the search predicate
   is `LIKE '%needle%'`. A btree index cannot answer a leading-wildcard LIKE.

So they cost write amplification on every member INSERT/UPDATE (including the
bulk roster import) and buy nothing. Worse, they make the schema *look* like
directory search is indexed when it is a sequential scan.

Making search actually indexed is a real change, not a migration: `search.py`
must call `unaccent_immutable` (the extension's `unaccent` is STABLE, not
IMMUTABLE, and Postgres refuses to index a non-immutable expression at all),
and the indexes must become GIN + `gin_trgm_ops` on that expression, which
serves both the `%contains%` path and the trigram fallback in `_trigram_fallback`.

That is deliberately NOT done here. At ~200 members the sequential scan is
sub-millisecond, and the change sits on the hot path of the page members use
most, a week before launch. Revisit when the member count makes it measurable.
The `unaccent_immutable` function and the `pg_trgm` extension (0020) both stay
in place precisely so that follow-up is a one-file change.
"""

from django.db import migrations

DROP = """
    DROP INDEX IF EXISTS members_member_first_name_unaccent_idx;
    DROP INDEX IF EXISTS members_member_last_name_unaccent_idx;
    DROP INDEX IF EXISTS members_member_nickname_unaccent_idx;
"""

RECREATE = """
    CREATE INDEX IF NOT EXISTS members_member_first_name_unaccent_idx
        ON members_member (LOWER(unaccent_immutable(first_name)));
    CREATE INDEX IF NOT EXISTS members_member_last_name_unaccent_idx
        ON members_member (LOWER(unaccent_immutable(last_name)));
    CREATE INDEX IF NOT EXISTS members_member_nickname_unaccent_idx
        ON members_member (LOWER(unaccent_immutable(nickname)));
"""


class Migration(migrations.Migration):
    dependencies = [("members", "0023_contact_visibility_opt_in")]

    operations = [migrations.RunSQL(sql=DROP, reverse_sql=RECREATE)]
