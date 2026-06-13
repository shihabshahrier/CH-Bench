"""GBrain adapter — the primary local competitor (github.com/garrytan/gbrain).

GBrain is a local Bun/TypeScript CLI: a markdown → self-wiring knowledge graph
with hybrid retrieval (HNSW pgvector + BM25 + RRF + reranker) on embedded
PGLite. This adapter drives its CLI directly:

    init   gbrain init --pglite --embedding-model openai:<m> --embedding-dimensions <d>
    ingest gbrain put <slug> --content <text>   (slug = suite id) + gbrain embed --all
    query  gbrain query <q> --limit <k>          (hybrid; prints "[score] slug -- text")

Retrieval-only here: `query` returns ranked pages, not a synthesized answer, so
answer=None (scored on retrieval metrics, like the other memory layers).

Config (env; set in CH-Bench/.env):
    GBRAIN_DIR                 repo dir (default ~/github/gbrain)
    GBRAIN_BUN                 bun binary (default ~/.bun/bin/bun, else "bun")
    GBRAIN_HOME                brain store to wipe on reset (default ~/.gbrain)
    GBRAIN_EMBEDDING_MODEL     e.g. openai:baai/bge-m3   (same embedder as CH → fair)
    GBRAIN_EMBEDDING_DIMENSIONS  e.g. 1024
    OPENAI_API_KEY / OPENAI_BASE_URL   point GBrain's OpenAI client at the provider
                                       (NVIDIA NIM, OpenAI-compatible)

If GBRAIN_DIR is absent the adapter runs in DRY-RUN (empty results) so the
harness contract still validates without GBrain installed.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from ..core.types import Memory, QueryResult, RetrievedSource

_LINE = re.compile(r"^\[([0-9.]+)\]\s+(\S+)\s+--")


class GBrainAdapter:
    name = "gbrain"

    def __init__(self, gbrain_dir: str | None = None, timeout: float = 120.0) -> None:
        d = gbrain_dir or os.getenv("GBRAIN_DIR") or str(Path.home() / "github" / "gbrain")
        self.dir = Path(d)
        self.cli = self.dir / "src" / "cli.ts"
        self.dry_run = not self.cli.exists()
        bun = os.getenv("GBRAIN_BUN") or str(Path.home() / ".bun" / "bin" / "bun")
        self.bun = bun if Path(bun).exists() else "bun"
        self.home = Path(os.getenv("GBRAIN_HOME") or (Path.home() / ".gbrain"))
        self.embed_model = os.getenv("GBRAIN_EMBEDDING_MODEL", "openai:baai/bge-m3")
        self.embed_dim = os.getenv("GBRAIN_EMBEDDING_DIMENSIONS", "1024")
        self.timeout = timeout
        self._ids: set[str] = set()

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.bun, str(self.cli), *args],
            cwd=str(self.dir),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
            env=os.environ.copy(),
        )

    def reset(self) -> None:
        if self.dry_run:
            return
        if self.home.exists():
            shutil.rmtree(self.home, ignore_errors=True)
        self._run([
            "init", "--pglite",
            "--embedding-model", self.embed_model,
            "--embedding-dimensions", self.embed_dim,
            "--skip-embed-check",
        ])
        self._ids.clear()

    def ingest(self, memories: list[Memory]) -> None:
        if self.dry_run:
            return
        for m in memories:
            self._run(["put", m.id, "--content", m.text])
            self._ids.add(m.id)
        # GBrain defers embedding on put; generate them in one batch.
        self._run(["embed", "--all"])

    def query(self, question: str, top_k: int) -> QueryResult:
        t0 = time.perf_counter()
        if self.dry_run:
            return QueryResult(answer=None, sources=[], latency_ms=0.0, raw={"dry_run": True})
        proc = self._run(["query", question, "--limit", str(top_k)])
        dt = (time.perf_counter() - t0) * 1000
        sources: list[RetrievedSource] = []
        for line in proc.stdout.splitlines():
            mt = _LINE.match(line.strip())
            if not mt:
                continue
            score, slug = float(mt.group(1)), mt.group(2)
            sid = slug if slug in self._ids else None
            sources.append(RetrievedSource(id=sid, text=slug, score=score))
            if len(sources) >= top_k:
                break
        return QueryResult(answer=None, sources=sources, latency_ms=dt, raw={"matched": len(sources)})

    def close(self) -> None:
        pass
