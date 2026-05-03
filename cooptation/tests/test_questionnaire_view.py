import pytest
from django.test import Client


@pytest.fixture
def expired_application_with_token(make_application):
    """An AdminApplication with questionnaire_token set, plus 3 KnowledgeQuestions
    seeded inline (matching what seed_questions creates, but with explicit answer_keys)."""
    from cooptation.models import KnowledgeQuestion

    app = make_application(email="c@example.test", status="cooptation_pending")
    app.cooptation_outcome = "expired"
    app.questionnaire_token = "abc123"
    app.save()
    KnowledgeQuestion.objects.create(
        position=1, kind="closed", text="Q1", answer_keys=["alpha", "beta"]
    )
    KnowledgeQuestion.objects.create(position=2, kind="closed", text="Q2", answer_keys=["gamma"])
    KnowledgeQuestion.objects.create(position=3, kind="open", text="Souvenir")
    return app


@pytest.mark.django_db
def test_questionnaire_get_renders_three_questions(expired_application_with_token):
    response = Client().get("/questionnaire/abc123/")
    assert response.status_code == 200
    assert response.content.count(b"<textarea") + response.content.count(b'type="text"') >= 3


@pytest.mark.django_db
def test_questionnaire_410_for_unknown_token():
    response = Client().get("/questionnaire/nope/")
    assert response.status_code == 410


@pytest.mark.django_db
def test_questionnaire_post_grades_closed_correctly(expired_application_with_token):
    """A correct closed answer (any answer_key as substring, accent-insensitive)
    is auto_graded True; a wrong one is False; open is None."""
    from cooptation.models import QuestionnaireResponse

    response = Client().post(
        "/questionnaire/abc123/",
        {
            "q1": "j'ai connu Mr Alpha",  # contains 'alpha' — match
            "q2": "Je sais pas",  # no match
            "q3": "C'était il y a 40 ans...",
        },
    )
    assert response.status_code == 302
    by_position = {r.question.position: r for r in QuestionnaireResponse.objects.all()}
    assert by_position[1].auto_grade is True
    assert by_position[2].auto_grade is False
    assert by_position[3].auto_grade is None


@pytest.mark.django_db
def test_questionnaire_accent_insensitive_match():
    """answer_keys=['Idrïssa'] matches a candidate answer 'IDRISSA'."""
    from cooptation.models import AdminApplication, KnowledgeQuestion, QuestionnaireResponse

    app = AdminApplication.objects.create(
        full_name="X",
        email="x@example.test",
        status="cooptation_pending",
        cooptation_outcome="expired",
    )
    app.questionnaire_token = "tok"
    app.save()
    KnowledgeQuestion.objects.create(position=1, kind="closed", text="Q", answer_keys=["Idrïssa"])

    Client().post("/questionnaire/tok/", {"q1": "le prof IDRISSA"})
    r = QuestionnaireResponse.objects.get(question__position=1)
    assert r.auto_grade is True


@pytest.mark.django_db
def test_questionnaire_post_transitions_application_to_awaiting_admin(
    expired_application_with_token,
):
    Client().post(
        "/questionnaire/abc123/",
        {"q1": "alpha", "q2": "gamma", "q3": "souvenir"},
    )
    expired_application_with_token.refresh_from_db()
    assert expired_application_with_token.status == "awaiting_admin"


@pytest.mark.django_db
def test_questionnaire_410_after_already_submitted(expired_application_with_token):
    Client().post(
        "/questionnaire/abc123/",
        {"q1": "alpha", "q2": "gamma", "q3": "souvenir"},
    )
    response = Client().get("/questionnaire/abc123/")
    assert response.status_code == 410
