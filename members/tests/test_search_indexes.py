import pytest
from django.db import connection


@pytest.mark.django_db
def test_unaccent_extension_is_installed():
    with connection.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'unaccent'")
        rows = cur.fetchall()
    assert rows, "unaccent extension is not installed"


@pytest.mark.django_db
def test_dead_unaccent_indexes_are_gone():
    """This test used to assert the three btree indexes from migration 0004
    existed. They did — and Postgres could never use a single one of them:

    1. They index `LOWER(unaccent_immutable(col))`, but `members/search.py`
       emits `UNACCENT(col)` via Django's `Unaccent`. Different function, so
       the planner never matches the expression.
    2. The search predicate is `LIKE '%needle%'`. A btree index cannot answer a
       leading-wildcard LIKE even if the expressions did match.

    So the test was pinning a false claim: it made the schema look like
    directory search was indexed when it was a sequential scan, while the
    indexes still cost write amplification on every member write. Migration
    0024 drops them. See its docstring for what a real fix requires.
    """
    with connection.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'members_member' AND indexname LIKE '%unaccent%'"
        )
        names = {row[0] for row in cur.fetchall()}
    assert names == set(), f"dead search indexes are back: {sorted(names)}"


@pytest.mark.django_db
def test_unaccent_immutable_function_is_retained():
    """`unaccent_immutable` stays even though nothing indexes with it today.

    The extension's own `unaccent()` is STABLE, and Postgres refuses to build an
    expression index on a non-immutable function — so this wrapper is exactly
    what a correct GIN + gin_trgm_ops index will need. Dropping it would make
    the eventual fix a two-migration job for no gain.
    """
    with connection.cursor() as cur:
        cur.execute("SELECT proname FROM pg_proc WHERE proname = 'unaccent_immutable'")
        rows = cur.fetchall()
    assert rows, "unaccent_immutable was dropped; the future trigram index needs it"


@pytest.mark.django_db
def test_status_check_constraint_rejects_invalid_value(make_user):
    from django.db import IntegrityError, transaction
    from django.db import connection as conn

    user = make_user()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO members_member "
                    "(user_id, slug, first_name, last_name, nickname, "
                    " years_attended, classes, city, country, profession, "
                    " photo_public_id, show_email, show_whatsapp, show_city, "
                    " status, created_at, updated_at) "
                    "VALUES (%s, gen_random_uuid(), 'A', 'B', '', "
                    " ARRAY[1980], ARRAY['6e']::varchar[], 'Niamey', 'Niger', '', "
                    " '', true, true, true, "
                    " 'WHATEVER', NOW(), NOW())",
                    [user.pk],
                )


@pytest.mark.django_db
def test_year_check_constraint_rejects_out_of_range(make_user):
    from django.db import IntegrityError, transaction
    from django.db import connection as conn

    user = make_user()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO members_member "
                    "(user_id, slug, first_name, last_name, nickname, "
                    " years_attended, classes, city, country, profession, "
                    " photo_public_id, show_email, show_whatsapp, show_city, "
                    " status, created_at, updated_at) "
                    "VALUES (%s, gen_random_uuid(), 'A', 'B', '', "
                    " ARRAY[1979], ARRAY['6e']::varchar[], 'Niamey', 'Niger', '', "
                    " '', true, true, true, "
                    " 'active', NOW(), NOW())",
                    [user.pk],
                )
