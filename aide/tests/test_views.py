"""Tests for /aide/ — public access, ?q= filter, no-results AuditLog."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from members.models import AuditLog


@pytest.fixture
def client_anon():
    return Client()


@pytest.fixture
def client_auth(make_user):
    user = make_user(password="testpass123")
    c = Client()
    c.login(username=user.username, password="testpass123")
    c.user = user
    return c


@pytest.mark.django_db
def test_aide_is_public_for_anonymous(client_anon):
    response = client_anon.get(reverse("aide:index"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_aide_renders_for_authenticated_user(client_auth):
    response = client_auth.get(reverse("aide:index"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_aide_default_view_lists_all_entries(client_anon):
    from aide.faq import FAQ_ENTRIES

    response = client_anon.get(reverse("aide:index"))
    body = response.content.decode("utf-8")
    for entry in FAQ_ENTRIES:
        assert escape(entry.question) in body, f"Question missing from default page: {entry.slug}"


@pytest.mark.django_db
def test_aide_q_filter_narrows_results(client_anon):
    # 'photo' should match entries 'photo-profil', 'photo-bloque', 'proposer-photo'.
    response = client_anon.get(reverse("aide:index"), {"q": "photo"})
    body = response.content.decode("utf-8")
    assert "Comment ajouter ou modifier ma photo" in body
    assert "photo de profil ne se charge pas" in body
    # An unrelated entry should NOT appear in the filtered set.
    assert "Comment me connecter au quotidien" not in body


@pytest.mark.django_db
def test_aide_q_no_results_writes_auditlog_anonymous(client_anon):
    assert AuditLog.objects.filter(action="aide.query.no_results").count() == 0
    response = client_anon.get(reverse("aide:index"), {"q": "zzzzz_no_such_word_zzzz"})
    assert response.status_code == 200
    rows = AuditLog.objects.filter(action="aide.query.no_results")
    assert rows.count() == 1
    row = rows.first()
    assert row.actor is None
    assert row.metadata.get("q") == "zzzzz_no_such_word_zzzz"
    assert row.metadata.get("actor_username") == "anonymous"


@pytest.mark.django_db
def test_aide_q_no_results_writes_auditlog_authenticated(client_auth):
    response = client_auth.get(reverse("aide:index"), {"q": "definitely_not_in_faq_xyz"})
    assert response.status_code == 200
    rows = AuditLog.objects.filter(action="aide.query.no_results")
    assert rows.count() == 1
    row = rows.first()
    assert row.actor_id == client_auth.user.id
    assert row.metadata.get("actor_username") == client_auth.user.username


@pytest.mark.django_db
def test_aide_q_truncates_long_queries_in_log(client_anon):
    long_q = "x" * 200
    client_anon.get(reverse("aide:index"), {"q": long_q})
    row = AuditLog.objects.filter(action="aide.query.no_results").first()
    assert row is not None
    assert len(row.metadata["q"]) == 80


@pytest.mark.django_db
def test_aide_empty_q_does_not_log(client_anon):
    client_anon.get(reverse("aide:index"), {"q": ""})
    assert AuditLog.objects.filter(action="aide.query.no_results").count() == 0


@pytest.mark.django_db
def test_aide_q_with_results_does_not_log(client_anon):
    client_anon.get(reverse("aide:index"), {"q": "photo"})
    assert AuditLog.objects.filter(action="aide.query.no_results").count() == 0


@pytest.mark.django_db
def test_aide_q_no_results_log_is_rate_limited_per_ip(client_anon):
    """Without a bound, any anonymous visitor can flood `members_auditlog`
    by sending a curl loop with arbitrary `?q=` values. Cap writes per IP
    per hour so the dataset remains useful and the table doesn't grow
    without bound."""
    # 35 distinct no-results queries from the same IP. The rate cap (30/h)
    # must clamp the AuditLog write count at <= 30. Page itself stays 200.
    for i in range(35):
        response = client_anon.get(reverse("aide:index"), {"q": f"zzznoresult_{i}_zzz"})
        assert response.status_code == 200

    count = AuditLog.objects.filter(action="aide.query.no_results").count()
    assert count <= 30, f"Expected at most 30 rows under per-IP limit, got {count}"
    # Also assert the cap actually engaged — if it's 35 the limit isn't wired.
    assert count >= 1


@pytest.mark.django_db
def test_plain_aide_gets_do_not_consume_no_results_budget(client_anon):
    """Regression: the view-level decorator counted EVERY GET (page loads,
    successful searches), so a member browsing the FAQ 30+ times silently
    stopped no-results logging — the dataset under-collected exactly when
    the page was in use. Only actual log-write attempts may consume."""
    for _ in range(31):
        assert client_anon.get(reverse("aide:index")).status_code == 200
    # Successful searches don't consume either.
    for _ in range(5):
        client_anon.get(reverse("aide:index"), {"q": "mot de passe"})

    client_anon.get(reverse("aide:index"), {"q": "zzz_definitely_no_match_zzz"})
    assert AuditLog.objects.filter(action="aide.query.no_results").count() == 1
