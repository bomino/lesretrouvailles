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
def test_member_show_flags_default_true(make_member):
    m = make_member()
    assert m.show_email is True
    assert m.show_whatsapp is True
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
