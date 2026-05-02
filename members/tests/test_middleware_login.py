import pytest


@pytest.mark.django_db
def test_health_endpoint_does_not_require_login(client):
    response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.django_db
def test_landing_does_not_require_login(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_page_does_not_require_login(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_redirects_anonymous_to_login(client):
    # `/admin/` is NOT in the whitelist; it has its own auth, but our middleware
    # runs first and treats it like any other private route.
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
    assert "next=/admin/" in response["Location"]


@pytest.mark.django_db
def test_static_paths_are_whitelisted(client):
    response = client.get("/static/css/output.css")
    # static may 404 in dev (file not collected) but must NOT 302 to login
    assert response.status_code != 302
