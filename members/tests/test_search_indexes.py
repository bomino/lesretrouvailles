import pytest
from django.db import connection


@pytest.mark.django_db
def test_unaccent_extension_is_installed():
    with connection.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'unaccent'")
        rows = cur.fetchall()
    assert rows, "unaccent extension is not installed"


@pytest.mark.django_db
def test_unaccent_functional_indexes_exist():
    with connection.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'members_member' AND indexname LIKE '%unaccent%'"
        )
        names = {row[0] for row in cur.fetchall()}
    expected = {
        "members_member_first_name_unaccent_idx",
        "members_member_last_name_unaccent_idx",
        "members_member_nickname_unaccent_idx",
    }
    assert expected <= names


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
