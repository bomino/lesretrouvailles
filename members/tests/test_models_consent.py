import time

import pytest

from members.models import ConsentRecord


@pytest.mark.django_db
def test_consent_record_stores_version_ip_and_member(make_member):
    m = make_member()
    rec = ConsentRecord.objects.create(
        member=m,
        charter_version="1.0",
        ip_address="127.0.0.1",
    )
    assert rec.charter_version == "1.0"
    assert rec.ip_address == "127.0.0.1"
    assert rec.accepted_at is not None


@pytest.mark.django_db
def test_consent_records_ordered_newest_first(make_member):
    m = make_member()
    a = ConsentRecord.objects.create(member=m, charter_version="1.0", ip_address="127.0.0.1")
    time.sleep(0.01)
    b = ConsentRecord.objects.create(member=m, charter_version="1.1", ip_address="127.0.0.1")
    qs = list(ConsentRecord.objects.filter(member=m))
    assert qs[0].pk == b.pk
    assert qs[1].pk == a.pk


@pytest.mark.django_db
def test_consent_record_cascades_when_member_deleted(make_member):
    m = make_member()
    ConsentRecord.objects.create(member=m, charter_version="1.0", ip_address="127.0.0.1")
    member_pk = m.pk
    m.user.delete()
    assert ConsentRecord.objects.filter(member_id=member_pk).count() == 0
