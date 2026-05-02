import pytest


@pytest.fixture(autouse=True)
def _clear_fake_email_backend():
    """Clear FakeResendBackend.sent_messages before every test so tests don't bleed."""
    from alumni.email import FakeResendBackend

    FakeResendBackend.sent_messages.clear()
    yield
    FakeResendBackend.sent_messages.clear()


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


@pytest.fixture
def make_cooptation_request(db, make_application):
    """Create a CooptationRequest. Builds Member directly to avoid fixture inception."""
    from datetime import timedelta

    from django.utils import timezone

    from cooptation.models import CooptationRequest

    counter = {"i": 0}

    def _make(*, application=None, parrain=None, **kwargs):
        counter["i"] += 1
        application = application or make_application()
        if parrain is None:
            from django.contrib.auth import get_user_model

            from members.models import Member

            user_model = get_user_model()
            user = user_model.objects.create_user(
                username=f"parrain{counter['i']}@example.test",
                email=f"parrain{counter['i']}@example.test",
                password="x",
                is_staff=True,
            )
            parrain = Member.objects.create(
                user=user,
                first_name=f"Parrain{counter['i']}",
                last_name="X",
                years_attended=[1980, 1981, 1982, 1983],
                classes=["6e", "5e", "4e", "3e"],
                city="Niamey",
            )
        defaults = {
            "application": application,
            "parrain": parrain,
            "expires_at": timezone.now() + timedelta(days=14),
        }
        defaults.update(kwargs)
        return CooptationRequest.objects.create(**defaults)

    return _make


@pytest.fixture(autouse=True)
def _clear_django_cache():
    """django-ratelimit uses Django's default cache (LocMemCache in tests).
    Clear it between cooptation tests so signup-view IP rate limits don't
    bleed across tests sharing the 127.0.0.1 client address."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
