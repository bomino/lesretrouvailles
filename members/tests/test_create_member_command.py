import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from members.models import Member, NotificationPreference


@pytest.mark.django_db
def test_create_member_creates_user_and_member():
    call_command(
        "create_member",
        "--email",
        "idrissa@example.test",
        "--first-name",
        "Idrissa",
        "--last-name",
        "Saidou",
        "--years",
        "1980",
        "1981",
        "1982",
        "1983",
        "--classes",
        "6e",
        "5e",
        "4e",
        "3e",
        "--city",
        "Niamey",
    )
    user = get_user_model().objects.get(email="idrissa@example.test")
    assert user.member.first_name == "Idrissa"
    assert NotificationPreference.objects.filter(member=user.member).exists()


@pytest.mark.django_db
def test_create_member_idempotent_on_email():
    for _ in range(2):
        call_command(
            "create_member",
            "--email",
            "idi@example.test",
            "--first-name",
            "Idrissa",
            "--last-name",
            "Saidou",
            "--years",
            "1980",
            "--classes",
            "6e",
            "--city",
            "Niamey",
        )
    assert get_user_model().objects.filter(email="idi@example.test").count() == 1
    assert Member.objects.filter(user__email="idi@example.test").count() == 1


@pytest.mark.django_db
def test_create_member_rejects_invalid_year():
    with pytest.raises((CommandError, Exception)):
        call_command(
            "create_member",
            "--email",
            "x@example.test",
            "--first-name",
            "X",
            "--last-name",
            "Y",
            "--years",
            "1979",
            "--classes",
            "6e",
            "--city",
            "Niamey",
        )


@pytest.mark.django_db
def test_create_member_rejects_invalid_grade():
    with pytest.raises((CommandError, Exception)):
        call_command(
            "create_member",
            "--email",
            "x@example.test",
            "--first-name",
            "X",
            "--last-name",
            "Y",
            "--years",
            "1980",
            "--classes",
            "2nde",
            "--city",
            "Niamey",
        )


@pytest.mark.django_db
def test_create_member_password_optional_creates_unusable_password():
    call_command(
        "create_member",
        "--email",
        "x@example.test",
        "--first-name",
        "X",
        "--last-name",
        "Y",
        "--years",
        "1980",
        "--classes",
        "6e",
        "--city",
        "Niamey",
    )
    user = get_user_model().objects.get(email="x@example.test")
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_create_member_password_explicit_sets_usable_password():
    call_command(
        "create_member",
        "--email",
        "x@example.test",
        "--first-name",
        "X",
        "--last-name",
        "Y",
        "--years",
        "1980",
        "--classes",
        "6e",
        "--city",
        "Niamey",
        "--password",
        "test-pw-1",
    )
    user = get_user_model().objects.get(email="x@example.test")
    assert user.check_password("test-pw-1")
