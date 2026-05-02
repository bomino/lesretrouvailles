from django.contrib import admin

from members.models import ConsentRecord, Member, NotificationPreference


def test_member_registered_in_admin():
    assert admin.site.is_registered(Member)


def test_notification_preference_registered_in_admin():
    assert admin.site.is_registered(NotificationPreference)


def test_consent_record_registered_in_admin():
    assert admin.site.is_registered(ConsentRecord)
