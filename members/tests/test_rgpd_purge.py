"""Tests for the RGPD admin-purge service.

Spec: docs/superpowers/specs/2026-05-05-rgpd-admin-purge-design.md
Plan: docs/superpowers/plans/2026-05-05-rgpd-admin-purge.md
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone


@pytest.fixture
def fake_clients(settings):
    settings.CLOUDINARY_CLIENT_PATH = "alumni.cloudinary.FakeCloudinary"
    settings.STORAGE_CLIENT_PATH = "alumni.storage.FakeStorage"


@pytest.fixture(autouse=True)
def reset_fakes():
    from alumni import cloudinary as cloud_mod
    from alumni import storage as storage_mod

    storage_mod.reset_fake_client()
    cloud_mod.reset_fake_client()


def _make_admin_user(email="admin@example.test"):
    User = get_user_model()  # noqa: N806
    return User.objects.create_user(
        username="rgpdadmin", email=email, password="x", is_staff=True, is_superuser=True
    )


def _make_memory(member, public_id):
    from memoires.models import Memory

    return Memory.objects.create(
        photo_public_id=public_id,
        caption="test memory",
        status="published",
        created_by=member.user,
    )


def _make_application(email):
    from cooptation.models import AdminApplication

    return AdminApplication.objects.create(
        full_name="Cand Idate",
        nickname="cand",
        years_attended=[1980],
        classes=["6e"],
        city="Niamey",
        country="Niger",
        profession="x",
        email=email,
        whatsapp="+22790000000",
    )


def _make_cooptation_request(parrain, application):
    from cooptation.models import CooptationRequest

    return CooptationRequest.objects.create(
        application=application,
        parrain=parrain,
        expires_at=timezone.now() + timedelta(days=14),
    )


def _make_inmemoriam_nomination(nominator):
    from memoriam.models import InMemoriamNomination

    return InMemoriamNomination.objects.create(
        nominator=nominator,
        proposed_name="Some Person",
        proposed_years=[1980],
        personal_memory="x",
    )


def _make_inmemoriam_entry(creator_user, photo_public_id=""):
    from memoriam.models import InMemoriamEntry

    return InMemoriamEntry.objects.create(
        full_name="Deceased Person",
        years_attended=[1980],
        classes=["6e"],
        tribute="x",
        family_consent_giver="x",
        family_consent_date=date(2026, 1, 1),
        family_consent_canal="email",
        status="published",
        created_by=creator_user,
        photo_public_id=photo_public_id,
    )


# -------- Tests --------


@pytest.mark.django_db
def test_purge_member_with_profile_photo(fake_clients, make_member):
    from alumni import cloudinary as cloud_mod
    from alumni import storage as storage_mod
    from members.models import AuditLog
    from members.services import rgpd_purge_member

    target = make_member(photo_public_id="members/abc/photo")
    target_id = target.id
    target_user_id = target.user.id
    actor = _make_admin_user()

    # Pre-populate the bucket so list_versions returns something to delete.
    storage = storage_mod.get_client()
    storage.upload_file("members/abc/photo", b"existing-backup")
    storage.upload_calls.clear()  # don't count the setup as a purge upload

    result = rgpd_purge_member(target, actor=actor)

    cloud = cloud_mod.get_client()
    assert "members/abc/photo" in cloud.delete_calls
    assert any(d["path"] == "members/abc/photo" for d in storage.delete_calls)

    User = get_user_model()  # noqa: N806
    from members.models import Member

    assert not Member.objects.filter(id=target_id).exists()
    assert not User.objects.filter(id=target_user_id).exists()

    audit = AuditLog.objects.filter(action="rgpd.member.purged").get()
    assert audit.target_type == "Member"
    assert audit.target_id == str(target_id)
    assert result["audit_log_id"] == audit.id


@pytest.mark.django_db
def test_purge_member_who_authored_memories(fake_clients, make_member):
    from alumni import cloudinary as cloud_mod
    from members.services import rgpd_purge_member

    target = make_member()
    _make_memory(target, "memoires/m1")
    _make_memory(target, "memoires/m2")
    actor = _make_admin_user()

    rgpd_purge_member(target, actor=actor)

    cloud = cloud_mod.get_client()
    assert sorted(cloud.delete_calls) == ["memoires/m1", "memoires/m2"]

    from memoires.models import Memory

    assert Memory.objects.count() == 0


@pytest.mark.django_db
def test_purge_member_who_is_parrain(fake_clients, make_member):
    from cooptation.models import AdminApplication, CooptationRequest
    from members.services import rgpd_purge_member

    parrain = make_member()
    other = make_member()  # candidate's app email is different from parrain's
    app = _make_application(email=other.user.email)
    _make_cooptation_request(parrain, app)
    actor = _make_admin_user()

    assert CooptationRequest.objects.count() == 1

    rgpd_purge_member(parrain, actor=actor)

    assert CooptationRequest.objects.count() == 0
    assert AdminApplication.objects.filter(id=app.id).exists()


@pytest.mark.django_db
def test_purge_member_who_nominated(fake_clients, make_member):
    from members.services import rgpd_purge_member
    from memoriam.models import InMemoriamNomination

    target = make_member()
    _make_inmemoriam_nomination(target)
    actor = _make_admin_user()

    rgpd_purge_member(target, actor=actor)

    assert InMemoriamNomination.objects.count() == 0


@pytest.mark.django_db
def test_purge_refuses_when_member_created_inmemoriam_fiche(fake_clients, make_member):
    from members.services import PurgeRefused, rgpd_purge_member
    from memoriam.models import InMemoriamEntry

    target = make_member()
    _make_inmemoriam_entry(creator_user=target.user)
    actor = _make_admin_user()

    with pytest.raises(PurgeRefused) as exc_info:
        rgpd_purge_member(target, actor=actor)

    assert "In Memoriam" in str(exc_info.value)
    # Nothing deleted
    from members.models import Member

    assert Member.objects.filter(id=target.id).exists()
    assert InMemoriamEntry.objects.count() == 1


@pytest.mark.django_db
def test_purge_refuses_self_purge(fake_clients, make_member):
    from members.services import PurgeRefused, rgpd_purge_member

    target = make_member()

    with pytest.raises(PurgeRefused) as exc_info:
        rgpd_purge_member(target, actor=target.user)

    assert "yourself" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_purge_idempotent_on_already_partial(fake_clients, make_member):
    """Pre-clear Cloudinary; the service still completes (no-op delete) and
    finishes the rest of the cascade. Idempotency check."""
    from alumni import cloudinary as cloud_mod
    from members.models import Member
    from members.services import rgpd_purge_member

    target = make_member(photo_public_id="members/already/gone")
    actor = _make_admin_user()

    # Cloudinary's FakeCloudinary.delete just records; no error on missing key.
    # That's the right behavior — same as the real SDK with idempotent destroy.
    cloud = cloud_mod.get_client()

    rgpd_purge_member(target, actor=actor)

    # Member is gone even though Cloudinary "delete" was a no-op semantically
    assert not Member.objects.filter(id=target.id).exists()
    assert "members/already/gone" in cloud.delete_calls


@pytest.mark.django_db
def test_dry_run_makes_no_changes(fake_clients, make_member):
    from alumni import cloudinary as cloud_mod
    from alumni import storage as storage_mod
    from members.models import AuditLog, Member
    from members.services import rgpd_purge_member

    target = make_member(photo_public_id="members/dry/run")
    _make_memory(target, "memoires/dry")
    actor = _make_admin_user()

    result = rgpd_purge_member(target, actor=actor, dry_run=True)

    assert result["dry_run"] is True
    assert result["audit_log_id"] is None
    assert Member.objects.filter(id=target.id).exists()

    cloud = cloud_mod.get_client()
    storage = storage_mod.get_client()
    assert cloud.delete_calls == []
    assert storage.delete_calls == []
    assert not AuditLog.objects.filter(action="rgpd.member.purged").exists()
    # Plan still reports counts
    assert result["deleted_counts"]["memories"] == 1


@pytest.mark.django_db
def test_audit_log_entry_redacted(fake_clients, make_member):
    """No PII in the AuditLog metadata or target_id."""
    from members.models import AuditLog
    from members.services import rgpd_purge_member

    target = make_member(first_name="Alice", last_name="Verysecret", city="ShouldNotLeak")
    target_email = target.user.email
    actor = _make_admin_user()

    rgpd_purge_member(target, actor=actor)

    audit = AuditLog.objects.get(action="rgpd.member.purged")
    serialized = str(audit.target_id) + str(audit.metadata)
    # PII fields must NOT appear anywhere in the entry
    assert "Alice" not in serialized
    assert "Verysecret" not in serialized
    assert "ShouldNotLeak" not in serialized
    assert target_email not in serialized

    assert "email_hash" in audit.metadata
    assert len(audit.metadata["email_hash"]) == 12
    assert "deleted_counts" in audit.metadata


@pytest.mark.django_db
def test_purge_anonymizes_admin_application(fake_clients, make_member):
    from members.services import rgpd_purge_member

    target = make_member()
    app = _make_application(email=target.user.email)
    actor = _make_admin_user()

    rgpd_purge_member(target, actor=actor)

    app.refresh_from_db()
    assert app.full_name == ""
    assert app.email == ""
    assert app.status == "purged"
