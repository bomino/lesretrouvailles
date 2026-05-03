import pytest
from django.test import Client

from members.charters import CHARTER_CURRENT_VERSION
from members.models import ConsentRecord, Member


@pytest.fixture
def two_active_parrains(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()  # noqa: N806
    parrains = []
    for i in (1, 2):
        u = User.objects.create_user(
            username=f"parrain{i}@example.test",
            email=f"parrain{i}@example.test",
            password="x",
        )
        m = Member.objects.create(
            user=u,
            first_name=f"Parrain{i}",
            last_name="X",
            years_attended=[1980, 1981, 1982, 1983],
            classes=["6e", "5e", "4e", "3e"],
            city="Niamey",
        )
        ConsentRecord.objects.create(
            member=m, charter_version=CHARTER_CURRENT_VERSION, ip_address="127.0.0.1"
        )
        parrains.append((u, m))
    return parrains


@pytest.mark.django_db
def test_full_happy_path(two_active_parrains, settings):
    """Visitor signs up → both parrains accept → admin approves → user can set password."""
    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"
    from django.contrib.auth import get_user_model

    from alumni.email import FakeResendBackend
    from cooptation.models import AdminApplication, CooptationRequest
    from cooptation.services import approve_application

    p1_user, p1_member = two_active_parrains[0]
    p2_user, p2_member = two_active_parrains[1]

    # 1. Visitor submits inscription
    FakeResendBackend.sent_messages.clear()
    response = Client().post(
        "/inscription/",
        {
            "full_name": "Idrissa Saidou",
            "nickname": "",
            "years_attended": "1980,1981,1982,1983",
            "classes": "6e,5e,4e,3e",
            "city": "Niamey",
            "country": "Niger",
            "profession": "Enseignant",
            "email": "idrissa@example.test",
            "whatsapp": "",
            "parrain1_email": "parrain1@example.test",
            "parrain2_email": "parrain2@example.test",
            "website_url": "",
        },
    )
    assert response.status_code == 302
    app = AdminApplication.objects.get(email="idrissa@example.test")
    assert app.status == "cooptation_pending"
    assert CooptationRequest.objects.filter(application=app).count() == 2

    # 2. Both parrains accept via their tokens
    for parrain_user, parrain_member in two_active_parrains:
        req = CooptationRequest.objects.get(application=app, parrain=parrain_member)
        c = Client()
        c.login(username=parrain_user.username, password="x")
        c.post(f"/cooptation/{req.token}/", {"response": "accepted", "comment": ""})

    # 3. Eager transition fired → application is awaiting_admin
    app.refresh_from_db()
    assert app.status == "awaiting_admin"
    assert app.cooptation_outcome == "all_accepted"

    # 4. Admin approves via service (admin action wraps this)
    User = get_user_model()  # noqa: N806
    admin = User.objects.create_superuser(username="root", email="root@example.test", password="x")
    user, member = approve_application(app, reviewed_by=admin)
    app.refresh_from_db()
    assert app.status == "approved"
    assert Member.objects.filter(user__email="idrissa@example.test").exists()
    assert member.first_name == "Idrissa"
    assert member.status == "active"
