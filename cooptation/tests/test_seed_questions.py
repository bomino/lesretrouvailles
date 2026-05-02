import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_questions_creates_three_questions():
    call_command("seed_questions")
    from cooptation.models import KnowledgeQuestion

    qs = list(KnowledgeQuestion.objects.all())
    assert len(qs) == 3
    assert [q.position for q in qs] == [1, 2, 3]
    assert qs[0].kind == "closed"
    assert qs[1].kind == "closed"
    assert qs[2].kind == "open"
    assert qs[2].answer_keys == []


@pytest.mark.django_db
def test_seed_questions_idempotent():
    call_command("seed_questions")
    call_command("seed_questions")
    from cooptation.models import KnowledgeQuestion

    assert KnowledgeQuestion.objects.count() == 3
