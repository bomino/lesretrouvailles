"""Infra findings from the pre-launch review (middleware, settings, CI-adjacent)."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_login_redirect_urlencodes_multi_param_next():
    """LoginRequiredMiddleware interpolated get_full_path() raw, so a
    destination with '&' split into a truncated next= plus a stray login-page
    param — the user landed on a partially-filtered page after logging in.
    ConsentRequiredMiddleware in the same file already used urlencode()."""
    response = Client().get("/annuaire/?year=1980&city=Niamey")
    assert response.status_code == 302
    location = response["Location"]
    assert "next=%2Fannuaire%2F%3Fyear%3D1980%26city%3DNiamey" in location
    # The stray param is what the raw interpolation produced.
    assert not location.endswith("&city=Niamey")


def _settings_source(name: str) -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parents[1] / "settings" / f"{name}.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("module", ["staging", "prod"])
def test_email_backend_is_env_overridable(module):
    """The launch runbook's 'emails are bouncing en masse' rollback says
    removing the EMAIL_BACKEND var falls back to the console backend. Both
    modules hardcoded ResendBackend AFTER base.py's env read, so the
    documented rollback was a silent no-op and real sends kept bouncing."""
    src = _settings_source(module)
    assert 'EMAIL_BACKEND = "alumni.email.ResendBackend"' not in src, (
        f"{module} must read EMAIL_BACKEND from env (defaulting to ResendBackend)"
    )
    assert 'EMAIL_BACKEND = env("EMAIL_BACKEND"' in src


def test_prod_shaped_settings_never_use_per_process_locmem_cache():
    """Every rate limiter rides on the default cache. With neither
    CACHE_BACKEND=db nor REDIS_URL set, staging/prod fell back to a
    per-process LocMemCache: N gunicorn workers = N independent counters,
    all reset on every deploy — the throttles silently didn't throttle.
    They now default to the Postgres-backed DatabaseCache (no new infra;
    docker/entrypoint.sh creates the table)."""
    src = _settings_source("staging")
    assert "locmem.LocMemCache" in src, "staging must detect the LocMem fallback"
    assert "django.core.cache.backends.db.DatabaseCache" in src

    from pathlib import Path

    entrypoint = (Path(__file__).resolve().parents[2] / "docker" / "entrypoint.sh").read_text(
        encoding="utf-8"
    )
    assert "createcachetable" in entrypoint
    # The table must be created whenever the DB cache is in play, not only
    # when CACHE_BACKEND=db was set explicitly.
    assert 'if [ -z "${REDIS_URL:-}" ]; then' in entrypoint


def test_production_image_installs_every_runtime_dependency():
    """F-01: the Cloudinary upload path imports PIL, but the Dockerfile's
    explicit pip list omitted pillow — the first real server-side upload in
    production would have died with ModuleNotFoundError. CI installs from
    pyproject (which HAS pillow), masking it. Keep the three dep lists in
    sync until a single source exists."""
    import re
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {
        re.split(r"[><=\[]", dep, maxsplit=1)[0].strip().lower()
        for dep in pyproject["project"]["dependencies"]
    }

    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    requirements = (root / "requirements.txt").read_text(encoding="utf-8").lower()

    missing_docker = {d for d in declared if f'"{d}' not in dockerfile.lower()}
    missing_req = {d for d in declared if d not in requirements}
    assert not missing_docker, f"missing from Dockerfile pip list: {sorted(missing_docker)}"
    assert not missing_req, f"missing from requirements.txt: {sorted(missing_req)}"


def test_prod_settings_fail_fast_on_missing_site_url_and_resend_key():
    """F-29: staging/prod booted happily with SITE_URL still on localhost and no
    RESEND_API_KEY. The first symptom is ~200 magic links pointing at
    http://localhost:8000, DM'd to members — discovered by the members."""
    src = _settings_source("staging")
    assert "SITE_URL" in src and "RESEND_API_KEY" in src
    assert src.count("ImproperlyConfigured") >= 3


def test_pyproject_packages_lists_every_installed_app():
    """F-14: gestion, memoires, memoriam and aide were missing from the packages
    list, so a wheel/sdist build would silently omit four live apps."""
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    packages = set(data["tool"]["setuptools"]["packages"])

    from django.conf import settings

    local_apps = {
        app
        for app in settings.INSTALLED_APPS
        if not app.startswith(("django.", "allauth")) and "." not in app
    }
    missing = local_apps - packages
    assert not missing, f"apps missing from pyproject packages: {sorted(missing)}"


def test_staging_basic_auth_exposes_the_same_public_surface_as_prod():
    """F-28: /aide/ and /guide/ are login-exempt in the app but were still
    behind staging's basic-auth gate, so staging could not be used to check the
    pages an anonymous member actually lands on."""
    from core.middleware import BASIC_AUTH_PUBLIC_PREFIXES

    assert "/aide/" in BASIC_AUTH_PUBLIC_PREFIXES
    assert "/guide/" in BASIC_AUTH_PUBLIC_PREFIXES
