"""Auth tokens must never reach the log stream.

Gunicorn's access log records the full request line, and this platform carries
single-use credentials in URL *paths*:

  /accounts/password/reset/key/<uidb36>-<token>/   -> full account takeover
  /cooptation/<token>/                             -> vouch as someone else
  /questionnaire/<token>/                          -> submit as the candidate
  /retrait/<entry_token>/ , /retrait/confirme/<t>/ -> remove a ghost entry

So every one of those was landing in Railway's logs in plaintext. Anyone with
log access — or any future log-shipping integration — could replay them.
"""

from __future__ import annotations

import logging

import pytest

from alumni.logging import TokenRedactingFilter, redact_tokens

SECRET_PATHS = [
    "/accounts/password/reset/key/MQ-cb4-9f8e7d6c5b4a3928/",
    "/cooptation/8f3d9a2b7c1e4f60a5d8/",
    "/questionnaire/zzTOKENzz-9f8e7d6c/",
    "/retrait/abc123def456ghi789/",
    "/retrait/confirme/xyz987uvw654/",
]


@pytest.mark.parametrize("path", SECRET_PATHS)
def test_token_is_redacted_from_a_path(path):
    out = redact_tokens(path)
    assert "REDACTED" in out
    # The token itself must be gone. Take the last non-empty path segment.
    token = [seg for seg in path.split("/") if seg][-1]
    assert token not in out, f"token {token!r} survived redaction"


def test_route_prefix_survives_so_logs_stay_useful():
    """Redaction must not blind the operator — the route is still identifiable."""
    out = redact_tokens("/cooptation/8f3d9a2b7c1e4f60a5d8/")
    assert out.startswith("/cooptation/")


@pytest.mark.parametrize(
    "path",
    ["/retrait/merci/", "/retrait/expire/", "/annuaire/?q=moussa", "/promotions/1980/6eB/"],
)
def test_non_token_paths_are_left_alone(path):
    assert redact_tokens(path) == path


def test_redacts_inside_a_full_request_line():
    line = "GET /accounts/password/reset/key/MQ-cb4-9f8e7d6c HTTP/1.1"
    out = redact_tokens(line)
    assert "9f8e7d6c" not in out
    assert out.startswith("GET /accounts/password/reset/key/")


def test_logging_filter_scrubs_the_record():
    """Django's own logger prints 'Internal Server Error: /path' — a 500 on a
    token URL would otherwise leak it even with gunicorn's log redacted."""
    f = TokenRedactingFilter()
    record = logging.LogRecord(
        name="django.request",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Internal Server Error: %s",
        args=("/questionnaire/zzTOKENzz-9f8e7d6c/",),
        exc_info=None,
    )
    assert f.filter(record) is True
    assert "zzTOKENzz" not in record.getMessage()
    assert "REDACTED" in record.getMessage()


def test_gunicorn_access_log_atoms_are_redacted():
    """This is what actually writes the request line into Railway's logs.

    Tests redact_atoms() rather than the logger class: gunicorn is unix-only, so
    the class cannot be instantiated on a Windows dev box and a skipped test is a
    test that never runs. The class is a three-line adapter over this function.
    """
    from alumni.logging import redact_atoms

    atoms = redact_atoms(
        {
            "r": "GET /cooptation/8f3d9a2b7c1e4f60 HTTP/1.1",
            "U": "/cooptation/8f3d9a2b7c1e4f60",
            "q": "",
            "s": "200",
        }
    )

    assert "8f3d9a2b7c1e4f60" not in atoms["r"], "token survived in the request line"
    assert atoms["U"] == "/cooptation/REDACTED"
    assert atoms["s"] == "200", "non-URL atoms must be left alone"


def test_settings_wire_the_filter_onto_the_console_handler(settings):
    console = settings.LOGGING["handlers"]["console"]
    assert "token_redaction" in console.get("filters", [])
