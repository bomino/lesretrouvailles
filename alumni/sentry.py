"""Sentry event scrubbing.

This platform carries single-use credentials in URL *paths* (password-reset
keys, parrain vouch tokens, questionnaire tokens, ghost-removal tokens). The
access log and Django loggers already run every line through
`alumni.logging.redact_tokens`; an error tracker that received the raw
request URL would re-open the same hole in a third-party dashboard.

`scrub_event` is wired as `before_send` in the prod-shaped settings. It is a
pure function over Sentry's event dict so it can be unit-tested without the
SDK, and it is deliberately tolerant: a missing key must never turn a crash
report into a second crash.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from .logging import redact_tokens


def csp_report_uri(dsn: str) -> str:
    """Sentry's CSP security endpoint, derived from the DSN.

    ``https://<key>@<host>/<project>`` → ``https://<host>/api/<project>/security/?sentry_key=<key>``.
    Empty DSN → empty string (no collector, header unchanged).
    """
    if not dsn:
        return ""
    parts = urlsplit(dsn)
    project = parts.path.strip("/")
    if not (parts.username and parts.hostname and project):
        return ""
    return f"{parts.scheme}://{parts.hostname}/api/{project}/security/?sentry_key={parts.username}"


_DROPPED_HEADERS = ("Authorization", "Cookie", "X-Csrftoken")


def _scrub_str(value: Any) -> Any:
    return redact_tokens(value) if isinstance(value, str) else value


def _scrub_mapping_urls(data: Any) -> None:
    """Redact string values in a breadcrumb `data` dict (url, query, ...)."""
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = _scrub_str(value)


def scrub_event(event: dict, hint: dict) -> dict:  # noqa: ARG001 - Sentry's before_send contract
    event["transaction"] = _scrub_str(event.get("transaction"))

    request = event.get("request")
    if isinstance(request, dict):
        request["url"] = _scrub_str(request.get("url"))
        request["query_string"] = _scrub_str(request.get("query_string"))
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for name in _DROPPED_HEADERS:
                headers.pop(name, None)
            for name, value in headers.items():
                headers[name] = _scrub_str(value)

    crumbs = event.get("breadcrumbs")
    if isinstance(crumbs, dict):
        for crumb in crumbs.get("values") or []:
            if isinstance(crumb, dict):
                crumb["message"] = _scrub_str(crumb.get("message"))
                _scrub_mapping_urls(crumb.get("data"))

    exception = event.get("exception")
    if isinstance(exception, dict):
        for exc in exception.get("values") or []:
            if isinstance(exc, dict):
                exc["value"] = _scrub_str(exc.get("value"))

    event["message"] = _scrub_str(event.get("message"))

    # Keys we only ever read are left untouched; keys we may have set to None
    # because they were absent are removed again so the event shape is stable.
    for key in ("transaction", "message"):
        if event.get(key) is None:
            event.pop(key, None)
    return event
