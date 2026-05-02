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
