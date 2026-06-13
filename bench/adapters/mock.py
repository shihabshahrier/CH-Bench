"""Deterministic in-memory adapter — the reference implementation.

No network, no API key, no LLM. Ranks memories by IDF-weighted token overlap
(a tiny BM25-lite) and answers extractively from the top hit, abstaining when
the best score is below a floor. Used to prove the harness end-to-end in CI and
to sanity-check suites without burning any provider quota.
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter

from ..core.types import Memory, QueryResult, RetrievedSource

_WORD = re.compile(r"[a-z0-9]+")

# Skipped when scoring a query so ubiquitous function words can't push an
# unrelated question above the abstain floor. (Still indexed, so IDF is honest.)
_STOP = frozenset(
    "a an and are as at be by for from has have how in is it its of on or that "
    "the to was were what when where which who why will with".split()
)


def _tok(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _query_tok(text: str) -> list[str]:
    return [t for t in _tok(text) if t not in _STOP]


class MockAdapter:
    name = "mock"

    def __init__(self, abstain_floor: float = 0.04) -> None:
        self.abstain_floor = abstain_floor
        self._mem: dict[str, Memory] = {}
        self._toks: dict[str, Counter[str]] = {}
        self._idf: dict[str, float] = {}

    def reset(self) -> None:
        self._mem.clear()
        self._toks.clear()
        self._idf.clear()

    def ingest(self, memories: list[Memory]) -> None:
        df: Counter[str] = Counter()
        for m in memories:
            toks = _tok(m.text + " " + str(m.metadata.get("title", "")))
            self._mem[m.id] = m
            self._toks[m.id] = Counter(toks)
            for t in set(toks):
                df[t] += 1
        n = max(1, len(memories))
        self._idf = {t: math.log(1 + n / (1 + d)) for t, d in df.items()}

    def _score(self, q_toks: list[str], doc: Counter[str]) -> float:
        if not doc:
            return 0.0
        dl = sum(doc.values())
        s = 0.0
        for t in set(q_toks):
            if t in doc:
                tf = doc[t] / dl
                s += tf * self._idf.get(t, 0.0)
        return s

    def query(self, question: str, top_k: int) -> QueryResult:
        t0 = time.perf_counter()
        q_toks = _query_tok(question)
        scored = sorted(
            ((self._score(q_toks, d), mid) for mid, d in self._toks.items()),
            key=lambda x: x[0],
            reverse=True,
        )
        top = scored[: max(top_k, 1)]
        sources = [
            RetrievedSource(id=mid, text=self._mem[mid].text, score=score)
            for score, mid in top
            if score > 0
        ]
        best = sources[0].score if sources else 0.0
        if best < self.abstain_floor or not sources:
            answer = "I don't have information about that in the notes."
        else:
            answer = self._mem[sources[0].id].text
        return QueryResult(
            answer=answer,
            sources=sources,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens=0,
            raw={"best_score": best},
        )

    def close(self) -> None:
        pass
