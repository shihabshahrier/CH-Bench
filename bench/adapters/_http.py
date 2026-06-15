"""Tiny stdlib JSON-over-HTTP helper shared by network adapters.

urllib only — keeps the harness dependency-free. Raises HTTPError with the
response body attached so adapter failures are debuggable.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

# Transient statuses worth retrying: provider rate limits + upstream hiccups +
# the 504 we synthesize for network/read timeouts.
_RETRYABLE = {429, 500, 502, 503, 504}


class HTTPError(RuntimeError):
    def __init__(self, status: int, body: str, url: str) -> None:
        super().__init__(f"HTTP {status} for {url}: {body[:300]}")
        self.status = status
        self.body = body
        self.url = url


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict | None = None,
    params: dict | None = None,
    timeout: float = 60.0,
) -> dict | list:
    if params:
        url = f"{url}?{urlencode(params)}"
    data = json.dumps(json_body).encode() if json_body is not None else None
    h = {"Accept": "application/json"}
    if data is not None:
        h["Content-Type"] = "application/json"
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise HTTPError(e.code, body, url) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # Network failure / read timeout — surface as a transient HTTPError
        # (status 504) so adapters' `except HTTPError` handling treats it as a
        # retryable miss instead of aborting the whole run on one slow request.
        raise HTTPError(504, f"network/timeout: {e}", url) from e
    if not raw:
        return {}
    return json.loads(raw)


def _retry_after(err: "HTTPError", default: float) -> float:
    """Seconds to wait before retrying. Honors a provider's
    `retryAfterSeconds` (supermemory) in the JSON body when present."""
    try:
        body = json.loads(err.body)
        ra = body.get("retryAfterSeconds") or body.get("retry_after")
        if ra:
            return float(ra)
    except (ValueError, TypeError, AttributeError):
        pass
    return default


def request_retry(
    method: str,
    url: str,
    *,
    retries: int = 5,
    backoff: float = 2.0,
    **kwargs,
) -> dict | list:
    """`request` with backoff on transient failures (429 rate limits, 5xx,
    network/read timeouts). A single slow or throttled call must not abort a
    whole benchmark run — the adapters scoring competitors rely on this so one
    provider hiccup doesn't zero a system's recall."""
    delay = backoff
    last: HTTPError | None = None
    for attempt in range(retries):
        try:
            return request(method, url, **kwargs)
        except HTTPError as e:
            if e.status not in _RETRYABLE or attempt == retries - 1:
                raise
            last = e
            wait = _retry_after(e, delay) if e.status == 429 else delay
            time.sleep(min(wait, 90.0))
            delay *= 1.8
    if last:
        raise last
    return {}
