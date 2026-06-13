"""Retrieval-quality metrics over a ranked list of resolved suite ids.

All functions take `ranked` (best-first, may contain None for unresolvable
sources) and `relevant` (the gold set). Pure stdlib math — no numpy.
"""

from __future__ import annotations

import math
from collections.abc import Iterable


def _truncate(ranked: list[str | None], k: int) -> list[str | None]:
    return ranked[:k] if k > 0 else ranked


def recall_at_k(ranked: list[str | None], relevant: Iterable[str], k: int) -> float:
    rel = set(relevant)
    if not rel:
        return 0.0
    hit = sum(1 for r in set(_truncate(ranked, k)) if r in rel)
    return hit / len(rel)


def precision_at_k(ranked: list[str | None], relevant: Iterable[str], k: int) -> float:
    rel = set(relevant)
    top = _truncate(ranked, k)
    if not top:
        return 0.0
    hit = sum(1 for r in top if r in rel)
    return hit / len(top)


def hit_at_k(ranked: list[str | None], relevant: Iterable[str], k: int) -> float:
    rel = set(relevant)
    return 1.0 if any(r in rel for r in _truncate(ranked, k)) else 0.0


def mrr(ranked: list[str | None], relevant: Iterable[str]) -> float:
    """Reciprocal rank of the first relevant hit (0 if none)."""
    rel = set(relevant)
    for i, r in enumerate(ranked, start=1):
        if r in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str | None], relevant: Iterable[str], k: int) -> float:
    """Binary-relevance nDCG@k. DCG with the standard 1/log2(rank+1) gain,
    normalized by the ideal ordering (all relevant items first)."""
    rel = set(relevant)
    if not rel:
        return 0.0
    dcg = 0.0
    for i, r in enumerate(_truncate(ranked, k), start=1):
        if r in rel:
            dcg += 1.0 / math.log2(i + 1)
    ideal_hits = min(len(rel), k if k > 0 else len(rel))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0
