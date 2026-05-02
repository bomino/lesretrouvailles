import pytest


@pytest.fixture
def make_application(db):
    from cooptation.models import AdminApplication

    counter = {"i": 0}

    def _make(**kwargs):
        counter["i"] += 1
        defaults = {
            "full_name": f"Candidate {counter['i']}",
            "nickname": "",
            "years_attended": [1980, 1981],
            "classes": ["6e", "5e"],
            "city": "Niamey",
            "country": "Niger",
            "profession": "",
            "email": f"candidate{counter['i']}@example.test",
            "whatsapp": "",
        }
        defaults.update(kwargs)
        return AdminApplication.objects.create(**defaults)

    return _make
