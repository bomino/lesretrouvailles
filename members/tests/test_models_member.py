import pytest
from django.core.exceptions import ValidationError

from members.models import Member


@pytest.mark.django_db
def test_member_full_name_property(make_member):
    m = make_member(first_name="Idrissa", last_name="Saidou")
    assert m.full_name == "Idrissa Saidou"


@pytest.mark.django_db
def test_member_default_status_is_active(make_member):
    m = make_member()
    assert m.status == "active"


@pytest.mark.django_db
def test_member_slug_is_uuid_and_unique(make_member):
    a = make_member()
    b = make_member()
    assert a.slug != b.slug
    # Slug is a UUID, so str(slug) parses cleanly
    import uuid

    uuid.UUID(str(a.slug))


@pytest.mark.django_db
def test_member_city_is_normalized_to_titlecase_on_save(make_member):
    m = make_member(city="  niamey  ")
    assert m.city == "Niamey"


@pytest.mark.django_db
def test_member_country_default_is_niger(make_member):
    m = make_member()
    assert m.country == "Niger"


@pytest.mark.django_db
def test_member_clean_rejects_year_outside_range(make_member):
    m = make_member()
    m.years_attended = [1979, 1980]
    with pytest.raises(ValidationError):
        m.full_clean()


@pytest.mark.django_db
def test_member_clean_rejects_unknown_grade(make_member):
    m = make_member()
    m.classes = ["6e", "2nde"]
    with pytest.raises(ValidationError):
        m.full_clean()


@pytest.mark.django_db
def test_member_clean_accepts_classes_with_section_letters(make_member):
    """Real-world classes have parallel sections (4eA, 3eB). full_clean must
    accept these in addition to the level-only forms."""
    m = make_member()
    m.classes = ["6e", "6eA", "4eB", "3eC"]
    m.full_clean()  # Must not raise.


@pytest.mark.django_db
def test_member_show_flags_defaults_are_opt_in_for_contact(make_member):
    """F-02: contact visibility is opt-IN — guide_membre.md and the FAQ have
    always said so ("décoché par défaut"). This test previously asserted the
    opposite, locking in the bug: the launch roster import would have published
    ~200 alumni's phone numbers to the directory on day one. City stays on,
    which is what the docs promise for that one."""
    m = make_member()
    assert m.show_email is False
    assert m.show_whatsapp is False
    assert m.show_city is True


@pytest.mark.django_db
def test_member_user_cascade(make_member, make_user):
    user = make_user()
    m = make_member(user=user)
    member_id = m.pk
    user.delete()
    assert not Member.objects.filter(pk=member_id).exists()


@pytest.mark.django_db
def test_member_updated_at_changes_on_save(make_member):
    m = make_member()
    first = m.updated_at
    m.profession = "Enseignant"
    m.save()
    assert m.updated_at > first


# -------- Class pattern flexibility (P7.1) --------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass",
    [
        "6e",
        "5e",
        "4e",
        "3e",  # level only (long form)
        "6eA",
        "5eb",
        "4eC",
        "3eZ",  # full form with section letter
        "6a",
        "6A",
        "5b",
        "4B",
        "3c",
        "3C",  # short form (P7.1)
    ],
)
def test_member_clean_accepts_class_format(make_member, klass):
    """Both long form ("6eA") and short form ("6a") are valid. Casing is
    flexible in either form — the value is stored verbatim."""
    m = make_member()
    m.classes = [klass]
    m.full_clean()  # should not raise


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass",
    [
        "6",  # bare level — ambiguous
        "7",  # out of range
        "2nde",  # high school
        "6eAB",  # two section letters
        "6 a",  # whitespace
        "",  # empty
    ],
)
def test_member_clean_rejects_invalid_class(make_member, klass):
    m = make_member()
    m.classes = [klass]
    with pytest.raises(ValidationError):
        m.full_clean()


@pytest.mark.django_db
def test_member_can_save_with_short_form_classes(make_member):
    """Regression for P7.1: the DB CHECK constraint that previously
    blocked anything except ['6e','5e','4e','3e'] is gone (migration
    0013), so saving a Member with short-form classes now succeeds."""
    m = make_member()
    m.classes = ["6a", "5b", "4b", "3c"]
    m.full_clean()
    m.save()
    m.refresh_from_db()
    assert m.classes == ["6a", "5b", "4b", "3c"]


def test_member_classes_field_is_optional():
    """Admin and ModelForm flows derive 'required' from the model field's
    blank flag. The classes field is optional because many alumni in the
    WhatsApp roster don't remember their grade-by-grade history."""
    assert Member._meta.get_field("classes").blank is True


@pytest.mark.django_db
def test_member_full_clean_accepts_empty_classes(make_member):
    m = make_member()
    m.classes = []
    m.full_clean()  # must not raise
    m.save()
    m.refresh_from_db()
    assert m.classes == []


@pytest.mark.django_db
def test_save_does_not_mangle_correctly_cased_city_country(make_member):
    """str.title() capitalizes after every non-letter, so save() silently
    rewrote 'USA'->'Usa', 'RDC'->'Rdc', "Côte d'Ivoire"->"Côte D'Ivoire",
    'Aix-en-Provence'->'Aix-En-Provence' — on EVERY save, so an operator
    could never fix it."""
    member = make_member(city="Aix-en-Provence", country="USA")
    member.refresh_from_db()
    assert member.city == "Aix-en-Provence"
    assert member.country == "USA"

    member.country = "Côte d'Ivoire"
    member.save()
    member.refresh_from_db()
    assert member.country == "Côte d'Ivoire"


@pytest.mark.django_db
def test_save_still_title_cases_all_lowercase_input(make_member):
    """The normalization that motivated .title() is still applied to
    all-lowercase operator input."""
    member = make_member(city="niamey", country="niger")
    member.refresh_from_db()
    assert member.city == "Niamey"
    assert member.country == "Niger"
