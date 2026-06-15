"""Supermemory adapter — managed memory API (api.supermemory.ai, v3).

Each Memory is added with its suite id in `metadata`, under a unique
`containerTag` per run so namespaces don't collide and recall maps back.
Retrieval-only (search returns chunks, not a synthesized answer).

Config (env):
    SUPERMEMORY_API_KEY    required
    SUPERMEMORY_BASE_URL   default https://api.supermemory.ai
    SUPERMEMORY_TAG        container tag for this run (default fresh per-process)

Endpoints default to the v3 surface; override paths via SUPERMEMORY_ADD_PATH /
SUPERMEMORY_SEARCH_PATH if the API revises them.
"""

from __future__ import annotations

import os
import time
import uuid

from ..core.types import Memory, QueryResult, RetrievedSource
from . import _http


class SupermemoryAdapter:
    name = "supermemory"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        tag: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("SUPERMEMORY_API_KEY", "")
        if not self.api_key:
            raise ValueError("SUPERMEMORY_API_KEY is required for the supermemory adapter")
        self.base_url = (base_url or os.getenv("SUPERMEMORY_BASE_URL", "https://api.supermemory.ai")).rstrip("/")
        self.tag = tag or os.getenv("SUPERMEMORY_TAG") or f"chbench-{uuid.uuid4().hex[:8]}"
        self.add_path = os.getenv("SUPERMEMORY_ADD_PATH", "/v3/documents")
        self.search_path = os.getenv("SUPERMEMORY_SEARCH_PATH", "/v3/search")

    def _h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def reset(self) -> None:
        # Unique containerTag per run is the isolation mechanism; nothing to
        # delete on a fresh tag. (A bulk delete-by-tag endpoint can go here.)
        return

    def ingest(self, memories: list[Memory]) -> None:
        last: Memory | None = None
        for m in memories:
            _http.request_retry(
                "POST",
                f"{self.base_url}{self.add_path}",
                headers=self._h(),
                json_body={
                    "content": m.text,
                    "containerTags": [self.tag],
                    "metadata": {"suite_id": m.id, **{k: str(v) for k, v in m.metadata.items()}},
                },
            )
            last = m
        # Supermemory indexes asynchronously (add returns status="queued"). Poll
        # until the last-added memory is searchable so queries don't race ingest.
        if last is not None:
            self._wait_indexed(last)

    def _wait_indexed(self, mem: Memory, max_wait: float | None = None) -> None:
        deadline = time.time() + (max_wait if max_wait is not None else float(os.getenv("SUPERMEMORY_SETTLE_MAX", "90")))
        while time.time() < deadline:
            try:
                payload = _http.request(
                    "POST",
                    f"{self.base_url}{self.search_path}",
                    headers=self._h(),
                    json_body={"q": mem.text[:120], "containerTags": [self.tag], "limit": 5},
                )
            except _http.HTTPError:
                payload = {}
            results = payload.get("results", []) if isinstance(payload, dict) else []
            if any((r.get("metadata") or {}).get("suite_id") == mem.id for r in results):
                return
            time.sleep(3.0)

    def query(self, question: str, top_k: int) -> QueryResult:
        t0 = time.perf_counter()
        payload = _http.request_retry(
            "POST",
            f"{self.base_url}{self.search_path}",
            headers=self._h(),
            json_body={"q": question, "containerTags": [self.tag], "limit": top_k},
        )
        dt = (time.perf_counter() - t0) * 1000
        results = payload.get("results", payload) if isinstance(payload, dict) else payload
        sources: list[RetrievedSource] = []
        for r in (results or [])[:top_k]:
            meta = r.get("metadata") or {}
            # Result may nest score/metadata under different keys across versions.
            sid = meta.get("suite_id") or (r.get("document") or {}).get("metadata", {}).get("suite_id")
            sources.append(
                RetrievedSource(
                    id=sid,
                    text=r.get("content") or r.get("memory") or "",
                    score=float(r.get("score", 0.0) or 0.0),
                )
            )
        return QueryResult(answer=None, sources=sources, latency_ms=dt, raw={"n": len(sources)})

    def close(self) -> None:
        pass
