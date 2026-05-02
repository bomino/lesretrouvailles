import pytest
from django.contrib import admin

from members.models import ConsentRecord, Member, NotificationPreference


def test_member_registered_in_admin():
    assert admin.site.is_registered(Member)


def test_notification_preference_registered_in_admin():
    assert admin.site.is_registered(NotificationPreference)


def test_consent_record_registered_in_admin():
    assert admin.site.is_registered(ConsentRecord)


@pytest.mark.django_db
def test_consent_record_admin_blocks_delete(make_member, make_user):
    from django.contrib import admin

    from members.models import ConsentRecord

    admin_class = admin.site._registry[ConsentRecord]
    assert admin_class.has_delete_permission(None) is False
    assert admin_class.has_add_permission(None) is False
