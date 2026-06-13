"""Mem0 adapter — the managed memory-layer competitor (api.mem0.ai).

Each Memory is added with its suite id in `metadata` so search results map back
for recall scoring (Mem0 re-extracts facts, so ids aren't otherwise preserved).
Retrieval-only: Mem0 search returns memories, not a synthesized answer, so this
adapter reports `answer=None` and is scored on retrieval metrics.

Config (env):
    MEM0_API_KEY     required
    MEM0_BASE_URL    default https://api.mem0.ai
    MEM0_USER_ID     namespace for this run (default a fresh per-process id)
"""

from __future__ import annotations

import os
import time
import uuid

from ..core.types import Memory, QueryResult, RetrievedSource
from . import _http


class Mem0Adapter:
    name = "mem0"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, user_id: str | None = None) -> None:
        self.api_key = api_key or os.getenv("MEM0_API_KEY", "")
        if not self.api_key:
            raise ValueError("MEM0_API_KEY is required for the mem0 adapter")
        self.base_url = (base_url or os.getenv("MEM0_BASE_URL", "https://api.mem0.ai")).rstrip("/")
        self.user_id = user_id or os.getenv("MEM0_USER_ID") or f"chbench-{uuid.uuid4().hex[:8]}"

    def _h(self) -> dict[str, str]:
        return {"Authorization": f"Token {self.api_key}"}

    def reset(self) -> None:
        # Delete everything under this run's namespace so a run starts clean.
        try:
            _http.request("DELETE", f"{self.base_url}/v1/memories/", headers=self._h(), params={"user_id": self.user_id})
        except _http.HTTPError:
            pass

    def ingest(self, memories: list[Memory]) -> None:
        last: Memory | None = None
        for m in memories:
            _http.request(
                "POST",
                f"{self.base_url}/v1/memories/",
                headers=self._h(),
                json_body={
                    "messages": [{"role": "user", "content": m.text}],
                    "user_id": self.user_id,
                    "metadata": {"suite_id": m.id, **{k: str(v) for k, v in m.metadata.items()}},
                },
            )
            last = m
        # Mem0 extracts + embeds asynchronously; query right after ingest races
        # indexing and recall collapses. Poll until the last memory is searchable.
        if last is not None:
            self._wait_indexed(last)

    def _wait_indexed(self, mem: Memory, max_wait: float | None = None) -> None:
        deadline = time.time() + (max_wait if max_wait is not None else float(os.getenv("MEM0_SETTLE_MAX", "90")))
        while time.time() < deadline:
            try:
                payload = _http.request(
                    "POST",
                    f"{self.base_url}/v1/memories/search/",
                    headers=self._h(),
                    json_body={"query": mem.text[:120], "user_id": self.user_id, "top_k": 5},
                )
            except _http.HTTPError:
                payload = {}
            results = payload.get("results", payload) if isinstance(payload, dict) else payload
            if any((r.get("metadata") or {}).get("suite_id") == mem.id for r in (results or [])):
                return
            time.sleep(3.0)

    def query(self, question: str, top_k: int) -> QueryResult:
        t0 = time.perf_counter()
        payload = _http.request(
            "POST",
            f"{self.base_url}/v1/memories/search/",
            headers=self._h(),
            json_body={"query": question, "user_id": self.user_id, "top_k": top_k},
        )
        dt = (time.perf_counter() - t0) * 1000
        results = payload.get("results", payload) if isinstance(payload, dict) else payload
        sources: list[RetrievedSource] = []
        for r in (results or [])[:top_k]:
            meta = r.get("metadata") or {}
            sources.append(
                RetrievedSource(
                    id=meta.get("suite_id"),
                    text=r.get("memory", ""),
                    score=float(r.get("score", 0.0) or 0.0),
                )
            )
        return QueryResult(answer=None, sources=sources, latency_ms=dt, raw={"n": len(sources)})

    def close(self) -> None:
        pass
