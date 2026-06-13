"""GBrain adapter — the primary local competitor.

GBrain ships as a local CLI. Its exact ingest/query interface is wired here via
two configurable commands so no GBrain internals are assumed:

    GBRAIN_INGEST_CMD   shell template, receives {text} and {id} per memory
    GBRAIN_QUERY_CMD    shell template, receives {query} and {k}; must print
                        JSON {"answer": str|null, "sources": [{"id": str,
                        "score": float}]} on stdout

If neither is set the adapter runs in DRY-RUN: it returns empty, well-formed
results so the harness contract and scorecard shape can be validated end-to-end
without GBrain installed (plan P15 verify: "a dry-run gbrain adapter returns
comparable JSON"). Fill the two env templates in P16 to get real numbers.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time

from ..core.types import Memory, QueryResult, RetrievedSource


class GBrainAdapter:
    name = "gbrain"

    def __init__(
        self,
        ingest_cmd: str | None = None,
        query_cmd: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.ingest_cmd = ingest_cmd if ingest_cmd is not None else os.getenv("GBRAIN_INGEST_CMD", "")
        self.query_cmd = query_cmd if query_cmd is not None else os.getenv("GBRAIN_QUERY_CMD", "")
        self.timeout = timeout
        self.dry_run = not (self.ingest_cmd and self.query_cmd)

    def reset(self) -> None:
        # GBrain corpus reset is engagement-specific (drop its store dir). Left
        # to the operator's GBRAIN_RESET_CMD if needed; dry-run is stateless.
        cmd = os.getenv("GBRAIN_RESET_CMD", "")
        if cmd and not self.dry_run:
            subprocess.run(shlex.split(cmd), timeout=self.timeout, check=False)

    def ingest(self, memories: list[Memory]) -> None:
        if self.dry_run:
            return
        for m in memories:
            cmd = self.ingest_cmd.format(text=shlex.quote(m.text), id=shlex.quote(m.id))
            subprocess.run(cmd, shell=True, timeout=self.timeout, check=False)

    def query(self, question: str, top_k: int) -> QueryResult:
        t0 = time.perf_counter()
        if self.dry_run:
            return QueryResult(answer=None, sources=[], latency_ms=(time.perf_counter() - t0) * 1000, raw={"dry_run": True})
        cmd = self.query_cmd.format(query=shlex.quote(question), k=top_k)
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=self.timeout, check=False)
        dt = (time.perf_counter() - t0) * 1000
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return QueryResult(answer=None, sources=[], latency_ms=dt, raw={"stdout": proc.stdout[:500]})
        sources = [
            RetrievedSource(id=str(s.get("id")), score=float(s.get("score", 0.0)))
            for s in out.get("sources", [])
        ]
        return QueryResult(answer=out.get("answer"), sources=sources, latency_ms=dt, raw=out)

    def close(self) -> None:
        pass
