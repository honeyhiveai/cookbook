"""HTTP helpers and the poller's retryable-error set."""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request


class HttpFailure(Exception):
    """HTTPError after the response body has been consumed."""

    def __init__(self, code: int, body: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.body = body


FETCH_ERRORS = (
    OSError,
    http.client.HTTPException,
    KeyError,
    json.JSONDecodeError,
    HttpFailure,
)


def error_text(exc: BaseException) -> str:
    if isinstance(exc, KeyError) and exc.args:
        return str(exc.args[0])
    return str(exc)


def as_object(payload: object, missing: str) -> dict:
    if not isinstance(payload, dict):
        raise KeyError(missing)
    return payload


def http_json(method: str, url: str, headers: dict, data=None, form: bool = False):
    body = None
    req_headers = dict(headers)
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            req_headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            req_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read()
            if not raw:
                raise json.JSONDecodeError("empty response body", "", 0)
            return json.loads(raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", "replace")[:4000]
        except (OSError, http.client.HTTPException):
            err_body = ""
        if err_body:
            print(err_body[:1000])
        raise HttpFailure(exc.code, err_body, str(exc)) from exc


def is_fatal_http(exc: BaseException) -> bool:
    if not isinstance(exc, HttpFailure):
        return False
    if exc.code in (400, 404):
        return True
    if exc.code != 403:
        return False
    return "INSUFFICIENT_ACCESS" in exc.body or "API_DISABLED_FOR_ORG" in exc.body


def honeyhive_post_result(exc: BaseException) -> str:
    if not isinstance(exc, HttpFailure):
        return "retry"
    if exc.code in (401, 403, 404):
        return "auth"
    if exc.code == 400:
        return "reject"
    return "retry"
