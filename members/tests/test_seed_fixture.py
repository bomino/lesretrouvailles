import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_members_fixture_loads_cleanly():
    call_command("loaddata", "seed_members")
    from members.models import Member

    assert Member.objects.count() >= 6
    assert Member.objects.filter(city="Niamey").exists()
    assert Member.objects.filter(country="France").exists()
