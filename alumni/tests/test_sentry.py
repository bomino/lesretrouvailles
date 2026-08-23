"""Sentry wiring: opt-in via SENTRY_DSN, and never ships a live token.

The August 2026 cron outage ran for 4+ weeks because nothing pushed failures
at the owner — LOGGING is console-only and there are no ADMINS. Sentry closes
that, but this platform carries single-use credentials in URL paths, so every
event must pass through the same redaction the access log uses.
"""

from __future__ import annotations

from alumni.tests.test_infra_hardening import _boot_staging, _settings_source, _staging_boot_env

TOKEN = "8f3d9a2b7c1e4f60"


def _event() -> dict:
    return {
        "transaction": f"/cooptation/{TOKEN}/",
        "request": {
            "url": f"https://villageretrouvailles.com/cooptation/{TOKEN}/",
            "query_string": f"next=/questionnaire/{TOKEN}/",
            "cookies": {"sessionid": "abc"},
            "headers": {"Authorization": "Basic Og==", "Referer": f"https://h/retrait/{TOKEN}/"},
        },
        "breadcrumbs": {
            "values": [
                {
                    "message": f"GET /accounts/password/reset/key/{TOKEN}-xyz/",
                    "data": {"url": f"/retrait/confirme/{TOKEN}/"},
                },
            ]
        },
        "exception": {
            "values": [{"type": "Http404", "value": f"No match for /questionnaire/{TOKEN}/"}]
        },
    }


def test_scrub_event_removes_tokens_everywhere():
    from alumni.sentry import scrub_event

    out = scrub_event(_event(), {})
    assert TOKEN not in repr(out), "a token survived somewhere in the event"
    assert out["request"]["url"] == "https://villageretrouvailles.com/cooptation/REDACTED/"
    assert out["transaction"] == "/cooptation/REDACTED/"
    assert out["breadcrumbs"]["values"][0]["message"].endswith("/reset/key/REDACTED/")
    assert out["breadcrumbs"]["values"][0]["data"]["url"] == "/retrait/confirme/REDACTED/"
    assert out["exception"]["values"][0]["value"] == "No match for /questionnaire/REDACTED/"


def test_scrub_event_drops_cookies_and_authorization():
    from alumni.sentry import scrub_event

    out = scrub_event(_event(), {})
    assert "cookies" not in out["request"]
    assert "Authorization" not in out["request"]["headers"]
    assert "Referer" in out["request"]["headers"], "non-secret headers stay"


def test_scrub_event_tolerates_minimal_events():
    from alumni.sentry import scrub_event

    assert scrub_event({"message": "plain"}, {}) == {"message": "plain"}


def test_staging_boots_without_a_dsn():
    """Absent DSN = Sentry off. The Docker build loads staging settings with
    no env at all; a hard requirement here would break the image build."""
    env = _staging_boot_env()
    env.pop("SENTRY_DSN", None)
    result = _boot_staging(env)
    assert "BOOTED" in result.stdout, result.stderr


def test_staging_init_is_pii_safe_and_redacted():
    """Source-text pin, like the other staging guards: the init must route
    through scrub_event and never send default PII."""
    src = _settings_source("staging")
    assert 'env("SENTRY_DSN"' in src
    assert "before_send=scrub_event" in src
    assert "send_default_pii=False" in src
    assert "traces_sample_rate=0" in src


def test_sentry_sdk_declared_everywhere():
    """pyproject is canonical, requirements.txt feeds Railpack, the Dockerfile
    pip list is explicit — a dep missing from any one of them is a different
    silent failure (see test_declared_deps for the general rule)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for name in ("pyproject.toml", "requirements.txt", "Dockerfile"):
        assert "sentry-sdk[django]" in (root / name).read_text(encoding="utf-8"), name


def test_csp_report_uri_is_derived_from_the_dsn():
    """Review L42: the report-only CSP collected no telemetry. Sentry's
    security endpoint is derivable from the DSN, so the observation phase
    gets a collector for free once SENTRY_DSN is set."""
    from alumni.sentry import csp_report_uri

    dsn = "https://abc123@o4500.ingest.us.sentry.io/987654"
    assert (
        csp_report_uri(dsn)
        == "https://o4500.ingest.us.sentry.io/api/987654/security/?sentry_key=abc123"
    )
    assert csp_report_uri("") == ""


def test_csp_header_carries_report_uri_when_configured(settings, client):
    settings.CSP_REPORT_URI = "https://o1.ingest.sentry.io/api/2/security/?sentry_key=k"
    settings.MIDDLEWARE = [
        *settings.MIDDLEWARE,
        "core.middleware.ContentSecurityPolicyReportOnlyMiddleware",
    ]
    header = client.get("/health")["Content-Security-Policy-Report-Only"]
    assert header.endswith("; report-uri https://o1.ingest.sentry.io/api/2/security/?sentry_key=k")
    assert "https://o1.ingest.sentry.io" in header.split("connect-src")[1].split(";")[0], (
        "the browser must be allowed to POST the report"
    )


def test_real_sdk_pipeline_never_emits_a_token():
    """End-to-end through sentry_sdk itself (capturing transport, no network):
    breadcrumbs, the message and the request-ish context must all be scrubbed
    by the time the envelope leaves the client."""
    import sentry_sdk
    from sentry_sdk.transport import Transport

    from alumni.sentry import scrub_event

    captured: list = []

    class _Capture(Transport):
        def capture_envelope(self, envelope):
            captured.append(envelope)

    client = sentry_sdk.Client(
        dsn="https://k@o1.ingest.sentry.io/2",
        transport=_Capture(),
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=scrub_event,
    )
    with sentry_sdk.isolation_scope() as scope:
        scope.set_client(client)
        sentry_sdk.add_breadcrumb(
            message=f"GET /cooptation/{TOKEN}/", data={"url": f"/retrait/{TOKEN}/"}
        )
        try:
            raise ValueError(f"boom at /questionnaire/{TOKEN}/")
        except ValueError:
            sentry_sdk.capture_exception()
        client.flush(timeout=2)

    assert captured, "nothing reached the transport"
    payload = "".join(str(item.payload.json) for env in captured for item in env.items)
    assert "/questionnaire/REDACTED/" in payload
    assert TOKEN not in payload
