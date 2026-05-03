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
    app.referrer = "https://wa.me/group/SOME-IDENTIFIABLE-INVITE-LINK"
    app.utm_source = "whatsapp"
    app.utm_campaign = "invitation"
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
    # referrer is PII (group invite URLs leak membership) → cleared
    assert app.referrer == ""
    # utm_source / utm_campaign are aggregate labels with analytical value → kept
    assert app.utm_source == "whatsapp"
    assert app.utm_campaign == "invitation"
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


@pytest.mark.django_db
def test_knowledge_question_kinds():
    from cooptation.models import KnowledgeQuestion

    expected = {"closed", "open"}
    actual = {choice for choice, _ in KnowledgeQuestion.KIND_CHOICES}
    assert actual == expected


@pytest.mark.django_db
def test_knowledge_question_ordered_by_position():
    from cooptation.models import KnowledgeQuestion

    KnowledgeQuestion.objects.create(position=2, kind="open", text="Souvenir")
    KnowledgeQuestion.objects.create(position=1, kind="closed", text="Prof", answer_keys=["x"])
    KnowledgeQuestion.objects.create(position=3, kind="closed", text="Salle", answer_keys=["y"])
    qs = list(KnowledgeQuestion.objects.all())
    assert [q.position for q in qs] == [1, 2, 3]


@pytest.mark.django_db
def test_questionnaire_response_unique_per_question_per_application(make_application):
    from django.db import IntegrityError

    from cooptation.models import KnowledgeQuestion, QuestionnaireResponse

    app = make_application()
    q = KnowledgeQuestion.objects.create(position=1, kind="open", text="t")
    QuestionnaireResponse.objects.create(application=app, question=q, candidate_answer="first")
    with pytest.raises(IntegrityError):
        QuestionnaireResponse.objects.create(application=app, question=q, candidate_answer="second")


@pytest.mark.django_db
def test_questionnaire_response_auto_grade_is_nullable(make_application):
    from cooptation.models import KnowledgeQuestion, QuestionnaireResponse

    app = make_application()
    q = KnowledgeQuestion.objects.create(position=1, kind="open", text="t")
    r = QuestionnaireResponse.objects.create(application=app, question=q, candidate_answer="x")
    assert r.auto_grade is None
