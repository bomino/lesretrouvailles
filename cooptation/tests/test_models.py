import pytest


@pytest.mark.django_db
def test_application_default_status_is_cooptation_pending(make_application):
    app = make_application()
    assert app.status == "cooptation_pending"
    assert app.cooptation_outcome == "pending"


@pytest.mark.django_db
def test_application_purge_clears_all_pii(make_application):
    app = make_application(
        full_name="Real Name",
        nickname="Nick",
        email="real@example.test",
        whatsapp="+227 90 00 00 00",
        city="Zinder",
        country="Niger",
        profession="Enseignant",
        review_note="Long internal note",
    )
    app.source_ip = "192.168.1.10"
    app.save()
    app.purge()
    app.refresh_from_db()
    assert app.full_name == ""
    assert app.nickname == ""
    assert app.email == ""
    assert app.whatsapp == ""
    assert app.city == ""
    assert app.country == ""
    assert app.profession == ""
    assert app.review_note == ""
    assert app.source_ip is None
    assert app.status == "purged"
    assert app.purged_at is not None


@pytest.mark.django_db
def test_application_status_choices_validated(make_application):
    """We use a CharField with choices but no DB CHECK; Django validates
    in full_clean() and the admin form. Verify the choices are exactly
    the 5 documented states."""
    from cooptation.models import AdminApplication

    expected = {
        "cooptation_pending",
        "awaiting_admin",
        "approved",
        "rejected",
        "purged",
    }
    actual = {choice for choice, _ in AdminApplication.STATUS_CHOICES}
    assert actual == expected


@pytest.mark.django_db
def test_application_outcome_choices(make_application):
    from cooptation.models import AdminApplication

    expected = {"pending", "all_accepted", "mixed", "all_refused", "expired"}
    actual = {choice for choice, _ in AdminApplication.OUTCOME_CHOICES}
    assert actual == expected


@pytest.mark.django_db
def test_cooptation_request_token_is_unique_and_urlsafe(make_cooptation_request):
    a = make_cooptation_request()
    b = make_cooptation_request()
    assert a.token != b.token
    assert len(a.token) >= 40  # token_urlsafe(32) yields ~43 chars
    for ch in a.token:
        assert ch.isalnum() or ch in "-_"


@pytest.mark.django_db
def test_cooptation_request_default_response_is_pending(make_cooptation_request):
    req = make_cooptation_request()
    assert req.response == "pending"
    assert req.responded_at is None
    assert req.reminder_sent_at is None


@pytest.mark.django_db
def test_cooptation_request_expires_at_required(make_cooptation_request):
    req = make_cooptation_request()
    assert req.expires_at is not None


@pytest.mark.django_db
def test_cooptation_request_application_cascade(make_cooptation_request, make_application):
    app = make_application()
    req = make_cooptation_request(application=app)
    req_pk = req.pk
    app.delete()
    from cooptation.models import CooptationRequest

    assert not CooptationRequest.objects.filter(pk=req_pk).exists()


@pytest.mark.django_db
def test_cooptation_request_parrain_protect(make_cooptation_request):
    """Deleting a Member that owns open cooptation requests must fail."""
    from django.db.models import ProtectedError

    req = make_cooptation_request()
    parrain = req.parrain
    user = parrain.user
    with pytest.raises(ProtectedError):
        user.delete()
