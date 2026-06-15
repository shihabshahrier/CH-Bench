"""common-knowledge (ck) adapter — the local-first OSS competitor.

ck is a local, file-backed knowledge store searched with grep (lexical FTS). We
write one Markdown file per Memory into a throwaway CK_HOME (named `<id>.md`),
then query with scripts/ck-search.sh and map matched filenames back to suite
ids. Lexical, retrieval-only (no synthesized answer) — the local-first baseline.

Config (env):
    CK_SCRIPTS   dir holding ck-search.sh (default: the repo path under
                 ~/github/skills/common-knowledge/.../scripts)
    CK_BENCH_HOME  throwaway store dir (default /tmp/ck-bench-<run>)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from ..core.types import Memory, QueryResult, RetrievedSource

_DEFAULT_SCRIPTS = "/Users/shahriar/github/skills/common-knowledge/skills/common-knowledge/scripts"
_FILE_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*?)\.md\b")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]+")
_STOP = frozenset(
    "a an and are as at be by do does did for from has have how in is it its of on or "
    "that the to was were what when where which who why will with you your about into "
    "this these those there their them they then than".split()
)


def _keywords(question: str) -> list[str]:
    """Content terms an agent would actually grep for — ck-search does fixed-string
    matching, so a whole-sentence query never hits prose. Dedupe, keep order."""
    seen: set[str] = set()
    out: list[str] = []
    for w in _WORD.findall(question):
        lw = w.lower()
        if lw in _STOP or len(w) < 3:
            continue
        if lw not in seen:
            seen.add(lw)
            out.append(w)
    return out


class CKAdapter:
    name = "ck"

    def __init__(self, scripts_dir: str | None = None, home: str | None = None, timeout: float = 30.0) -> None:
        self.scripts = Path(scripts_dir or os.getenv("CK_SCRIPTS", _DEFAULT_SCRIPTS))
        self.search = self.scripts / "ck-search.sh"
        if not self.search.exists():
            raise SystemExit(f"ck-search.sh not found at {self.search}; set CK_SCRIPTS")
        self.home = Path(home or os.getenv("CK_BENCH_HOME") or f"/tmp/ck-bench-{uuid.uuid4().hex[:8]}")
        self.project = self.home / "benchmark"
        self.timeout = timeout
        self._ids: set[str] = set()
        # filename stem (colon-safe) → original suite id, for recall scoring.
        self._stem_to_suite: dict[str, str] = {}

    def reset(self) -> None:
        if self.home.exists():
            shutil.rmtree(self.home, ignore_errors=True)
        self.project.mkdir(parents=True, exist_ok=True)
        self._ids.clear()
        self._stem_to_suite.clear()

    @staticmethod
    def _safe_stem(suite_id: str) -> str:
        # The filename regex (_FILE_RE) only recognizes [A-Za-z0-9_.-], so a
        # suite id with a colon (LoCoMo's '0:D1:2') becomes an unparseable
        # filename — the grep hit can never map back and recall scores a bogus 0.
        # Normalize to a colon-free stem and remember the mapping.
        return re.sub(r"[^A-Za-z0-9_.-]+", "-", suite_id).strip("-")

    def ingest(self, memories: list[Memory]) -> None:
        for m in memories:
            # Filename is a colon-safe form of the suite id so a grep hit maps back.
            stem = self._safe_stem(m.id)
            (self.project / f"{stem}.md").write_text(f"# {m.id}\n\n{m.text}\n")
            self._ids.add(stem)
            self._stem_to_suite[stem] = m.id

    def query(self, question: str, top_k: int) -> QueryResult:
        t0 = time.perf_counter()
        # Run ck-search once per content keyword and tally per-file hits; rank by
        # how many query terms a file matched (lexical relevance). This is how an
        # agent drives ck — keyword greps, not a sentence.
        tally: dict[str, int] = {}
        for kw in _keywords(question) or [question]:
            proc = subprocess.run(
                ["bash", str(self.search), kw, "--home", str(self.home), "--per-project", str(max(top_k * 3, 30))],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            hit_in_run: set[str] = set()
            for line in proc.stdout.splitlines():
                for stem in _FILE_RE_iter(line):
                    if stem in self._ids and stem not in hit_in_run:
                        hit_in_run.add(stem)
            for stem in hit_in_run:
                tally[stem] = tally.get(stem, 0) + 1
        dt = (time.perf_counter() - t0) * 1000
        ranked = sorted(tally, key=lambda s: tally[s], reverse=True)
        sources = [
            RetrievedSource(id=self._stem_to_suite.get(s, s), score=float(tally[s]))
            for s in ranked[:top_k]
        ]
        return QueryResult(answer=None, sources=sources, latency_ms=dt, raw={"matched": len(ranked)})

    def close(self) -> None:
        if self.home.exists():
            shutil.rmtree(self.home, ignore_errors=True)


def _FILE_RE_iter(line: str):
    for mt in _FILE_RE.finditer(line):
        yield mt.group(1)
