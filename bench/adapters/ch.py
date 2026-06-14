"""Context-Heavy adapter — drives the real REST API.

Ingest path:   POST /v1/nodes            (one node per memory)
Answer path:   POST /v1/graph/ask        ({answer, sources[]}, modes fast/deep/global)
Recall-only:   GET  /v1/semantic         (ranked nodes, no LLM) when CH_RETRIEVAL_ONLY=1

Config (env):
    CH_BASE_URL          default http://localhost:8080
    CH_API_KEY           required — use a key for a DEDICATED benchmark workspace,
                         never your live brain (ingest writes + reset deletes nodes)
    CH_ASK_MODE          fast | deep | global   (default fast)
    CH_NODE_TYPE         node type to ingest as (default "note")
    CH_INGEST_DELAY      seconds between node creates (default 0; set ~1.6 for the
                         NIM 40-RPM free tier, which embeds on write)
    CH_RETRIEVAL_ONLY    "1" → score retrieval via /v1/semantic, skip the LLM answer

Isolation: every node is named "{prefix}{memory.id}" and tagged
properties.bench=true with a run id, so retrieved sources map back to suite ids
and `reset()` deletes only what this harness created.
"""

from __future__ import annotations

import os
import time
import uuid

from ..core.types import Memory, QueryResult, RetrievedSource
from . import _http


class CHAdapter:
    name = "ch"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        ask_mode: str | None = None,
        node_type: str | None = None,
        ingest_delay: float | None = None,
        retrieval_only: bool | None = None,
        run_id: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("CH_BASE_URL", "http://localhost:8080")).rstrip("/")
        self.api_key = api_key or os.getenv("CH_API_KEY", "")
        if not self.api_key:
            raise ValueError("CH_API_KEY is required for the ch adapter")
        self.ask_mode = ask_mode or os.getenv("CH_ASK_MODE", "fast")
        self.node_type = node_type or os.getenv("CH_NODE_TYPE", "note")
        self.ingest_delay = (
            ingest_delay
            if ingest_delay is not None
            else float(os.getenv("CH_INGEST_DELAY", "0"))
        )
        # Pace queries to stay under a rate-limited chat/embed provider (each Ask
        # fans out to embed + rerank + completion calls).
        self.query_delay = float(os.getenv("CH_QUERY_DELAY", "0"))
        self.retrieval_only = (
            retrieval_only
            if retrieval_only is not None
            else os.getenv("CH_RETRIEVAL_ONLY", "") == "1"
        )
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.prefix = f"bench-{self.run_id}-"
        self._sys_to_suite: dict[str, str] = {}
        self._created: list[str] = []

    # ── helpers ──
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _suite_id_from_name(self, name: str | None) -> str | None:
        if name and name.startswith(self.prefix):
            return name[len(self.prefix):]
        return None

    # ── Adapter contract ──
    def reset(self) -> None:
        # Purge every leftover "bench-" node in the workspace (not just ids
        # tracked this process) so separate CLI runs don't pollute each other's
        # recall with stale nodes. The benchmark uses a dedicated workspace, so
        # deleting all bench-prefixed nodes is safe.
        for _ in range(200):  # page cap
            try:
                page = _http.request(
                    "GET", f"{self.base_url}/v1/nodes",
                    headers=self._headers(), params={"limit": 200},
                )
            except _http.HTTPError:
                break
            rows = (page.get("data") or []) if isinstance(page, dict) else []
            victims = [r.get("id") for r in rows if str(r.get("name", "")).startswith("bench-")]
            if not victims:
                break
            for nid in victims:
                try:
                    _http.request("DELETE", f"{self.base_url}/v1/nodes/{nid}", headers=self._headers())
                except _http.HTTPError:
                    pass
        self._created.clear()
        self._sys_to_suite.clear()

    def ingest(self, memories: list[Memory]) -> None:
        for m in memories:
            body = {
                "type": self.node_type,
                "name": f"{self.prefix}{m.id}",
                "body": m.text,
                "description": m.text[:200],
                "properties": {"bench": True, "bench_run": self.run_id, "suite_id": m.id, **m.metadata},
            }
            try:
                node = _http.request(
                    "POST",
                    f"{self.base_url}/v1/nodes",
                    headers=self._headers(),
                    json_body=body,
                )
            except _http.HTTPError as e:
                # A duplicate slug (re-run) is non-fatal; skip and continue.
                if e.status == 409:
                    continue
                raise
            nid = node.get("id") if isinstance(node, dict) else None
            if nid:
                self._sys_to_suite[str(nid)] = m.id
                self._created.append(str(nid))
            if self.ingest_delay:
                time.sleep(self.ingest_delay)

    def query(self, question: str, top_k: int) -> QueryResult:
        if self.query_delay:
            time.sleep(self.query_delay)
        try:
            if self.retrieval_only:
                return self._semantic(question, top_k)
            return self._ask(question, top_k)
        except _http.HTTPError as e:
            # A rate-limited / transient upstream failure on one question must
            # not abort the whole run — score it as a miss and move on.
            return QueryResult(answer=None, sources=[], latency_ms=0.0, raw={"error": str(e)[:200]})

    def _post_retry(self, url: str, json_body: dict, timeout: float = 60.0):
        """POST with backoff on NIM rate limits / transient upstream errors
        (429/500/502/503) and network read-timeouts (504, surfaced by _http),
        which CH hits when the embed+rerank+chat chain trips the 40-RPM free
        tier or an Ask stalls past the socket timeout."""
        attempts = int(os.getenv("CH_RETRIES", "4"))
        delay = 3.0
        last: _http.HTTPError | None = None
        for i in range(attempts):
            try:
                return _http.request("POST", url, headers=self._headers(), json_body=json_body, timeout=timeout)
            except _http.HTTPError as e:
                if e.status not in (429, 500, 502, 503, 504) or i == attempts - 1:
                    raise
                last = e
                time.sleep(delay)
                delay *= 1.8
        if last:
            raise last
        return {}

    def _ask(self, question: str, top_k: int) -> QueryResult:
        t0 = time.perf_counter()
        # Ask fans out to embed+rerank+(multi-)chat; under NIM rate limits a
        # single call can exceed the default 60s, so give it a wider ceiling.
        payload = self._post_retry(
            f"{self.base_url}/v1/graph/ask",
            {"query": question, "top_k": top_k, "mode": self.ask_mode},
            timeout=float(os.getenv("CH_ASK_TIMEOUT", "150")),
        )
        dt = (time.perf_counter() - t0) * 1000
        answer = payload.get("answer") if isinstance(payload, dict) else None
        sources = []
        for s in (payload.get("sources") or []) if isinstance(payload, dict) else []:
            sid = self._sys_to_suite.get(str(s.get("id"))) or self._suite_id_from_name(s.get("name"))
            sources.append(
                RetrievedSource(id=sid, text=s.get("name", ""), score=float(s.get("similarity", 0.0)))
            )
        return QueryResult(answer=answer, sources=sources, latency_ms=dt, tokens=0, raw=payload if isinstance(payload, dict) else {})

    def _semantic(self, question: str, top_k: int) -> QueryResult:
        t0 = time.perf_counter()
        payload = _http.request(
            "GET",
            f"{self.base_url}/v1/semantic",
            headers=self._headers(),
            params={"q": question, "limit": top_k},
        )
        dt = (time.perf_counter() - t0) * 1000
        rows = payload.get("data") or [] if isinstance(payload, dict) else []
        sources = []
        for r in rows:
            sid = self._sys_to_suite.get(str(r.get("id"))) or self._suite_id_from_name(r.get("name"))
            sources.append(
                RetrievedSource(id=sid, text=r.get("name", ""), score=float(r.get("similarity", 0.0)))
            )
        return QueryResult(answer=None, sources=sources, latency_ms=dt, tokens=0, raw={"n": len(rows)})

    def close(self) -> None:
        # Leave reset() to the next run; explicit cleanup happens there. If a
        # caller wants a tidy DB immediately, call reset() before close().
        pass
