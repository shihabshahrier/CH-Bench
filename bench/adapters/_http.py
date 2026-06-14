"""Tiny stdlib JSON-over-HTTP helper shared by network adapters.

urllib only — keeps the harness dependency-free. Raises HTTPError with the
response body attached so adapter failures are debuggable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlencode


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
