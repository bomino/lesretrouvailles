"""Keep single-use auth tokens out of the log stream.

This platform carries credentials in URL *paths*, not query strings:

    /accounts/password/reset/key/<uidb36>-<token>/   full account takeover
    /cooptation/<token>/                             vouch as someone else
    /questionnaire/<token>/                          submit as the candidate
    /retrait/<entry_token>/                          request a ghost removal
    /retrait/confirme/<confirm_token>/               execute it

Gunicorn's access log records the whole request line, so every one of those was
landing in Railway's logs in plaintext — replayable by anyone with log access or
any future log-shipping integration. Django's own `django.request` logger prints
"Internal Server Error: /path" too, so a 500 on a token URL would leak it even
with the access log fixed.

Two layers, one regex:
  * `RedactingGunicornLogger`  — wired via gunicorn --logger-class.
  * `TokenRedactingFilter`     — wired onto the console handler in LOGGING, so
                                 application and django.* records are scrubbed.

The route prefix is deliberately preserved: an operator still sees that someone
hit /cooptation/, just not with which token. Blinding the logs would trade one
problem for another.
"""

from __future__ import annotations

import logging
import re

_REDACTED = "REDACTED"

# Each alternative keeps the route prefix (group 1) and swallows the secret.
# `/retrait/` needs a negative lookahead: /retrait/merci/ and /retrait/expire/
# are ordinary pages, not tokens.
_TOKEN_PATTERNS = [
    re.compile(r"(/accounts/password/reset/key/)[^/\s?]+"),
    re.compile(r"(/cooptation/)[^/\s?]+"),
    re.compile(r"(/questionnaire/)[^/\s?]+"),
    re.compile(r"(/retrait/confirme/)[^/\s?]+"),
    re.compile(r"(/retrait/)(?!merci\b|expire\b|confirme\b)[^/\s?]+"),
]


def redact_tokens(text: str) -> str:
    """Replace secret path segments with REDACTED, keeping the route visible."""
    if not text:
        return text
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub(r"\g<1>" + _REDACTED, text)
    return text


class TokenRedactingFilter(logging.Filter):
    """Scrub tokens from any log record before a handler emits it."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_tokens(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_tokens(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_tokens(a) if isinstance(a, str) else a for a in record.args
                )
        return True


try:  # pragma: no cover - gunicorn is unix-only and absent on Windows dev boxes
    from gunicorn.glogging import Logger as _GunicornLogger
except ImportError:  # pragma: no cover
    # This module is imported by LOGGING (for TokenRedactingFilter) on every
    # environment, including local Windows dev where gunicorn cannot install.
    # A hard import here would break the whole settings module.
    _GunicornLogger = object


#: gunicorn access-log atoms that can contain a URL: request line, path, query.
_URL_ATOMS = ("r", "U", "q")


def redact_atoms(atoms: dict) -> dict:
    """Scrub tokens from a gunicorn access-log atom dict, in place.

    Pulled out of the logger class so it is testable on any platform: gunicorn
    is unix-only, so the class itself cannot even be instantiated on a Windows
    dev box, and a test that skipped there would be a test that never runs.
    """
    for key in _URL_ATOMS:
        value = atoms.get(key)
        if isinstance(value, str):
            atoms[key] = redact_tokens(value)
    return atoms


class RedactingGunicornLogger(_GunicornLogger):
    """Gunicorn access logger that redacts tokens from the request line.

    gunicorn's --access-logformat cannot rewrite path segments, so the redaction
    has to happen in the logger itself. Wired via
    `--logger-class alumni.logging.RedactingGunicornLogger` in the entrypoint.
    The real work is in redact_atoms(); this is a three-line adapter.
    """

    def atoms(self, resp, req, environ, request_time):
        return redact_atoms(super().atoms(resp, req, environ, request_time))
