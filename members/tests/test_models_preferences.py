import pytest

from members.models import NotificationPreference


@pytest.mark.django_db
def test_preference_auto_created_on_member_save(make_member):
    m = make_member()
    assert NotificationPreference.objects.filter(member=m).exists()


@pytest.mark.django_db
def test_preference_defaults_are_gdpr_safe(make_member):
    m = make_member()
    prefs = m.preferences
    assert prefs.digest_weekly is False
    assert prefs.in_memoriam_alerts is True
    assert prefs.event_alerts is False
    assert prefs.tag_alerts is True
    assert prefs.data_saver is False


@pytest.mark.django_db
def test_preference_saving_member_does_not_create_duplicate(make_member):
    m = make_member()
    m.profession = "Enseignant"
    m.save()
    assert NotificationPreference.objects.filter(member=m).count() == 1
