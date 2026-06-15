"""The run loop: reset → ingest → ask every question → score → aggregate.

Produces a `Scorecard` that the report layer renders to JSON + Markdown. The
runner is suite- and adapter-agnostic: it only speaks the `core.types` contract.
"""

from __future__ import annotations

import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .. import metrics
from .adapter import Adapter
from .judge import Judge
from .suite import Suite
from .types import Question


@dataclass(slots=True)
class QuestionResult:
    qid: str
    track: str | None
    expect_abstain: bool
    has_gold: bool  # the question carried gold relevant_ids → counts toward ranking metrics
    recall: float
    precision: float
    hit: float
    mrr: float
    ndcg_at_k: float
    correctness: float | None
    abstained: bool | None
    abstain_correct: float | None
    latency_ms: float
    tokens: int
    answer: str | None
    ranked_ids: list[str | None]


@dataclass(slots=True)
class Scorecard:
    system: str
    suite: str
    k: int
    n_memories: int
    n_questions: int
    judged: bool
    started_at: str
    finished_at: str
    metrics: dict[str, float] = field(default_factory=dict)
    tracks: dict[str, dict[str, float]] = field(default_factory=dict)
    per_question: list[QuestionResult] = field(default_factory=list)
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else 0.0


def _aggregate(rows: list[QuestionResult], judged: bool, *, seed: int = 0) -> dict[str, float]:
    # Ranking metrics aggregate ONLY over questions that carried gold
    # relevant_ids. An abstain question has no gold to rank, so recall/precision/
    # hit/mrr/ndcg are undefined for it — averaging in a spurious 0 unfairly
    # penalized every system (and most a system that correctly abstains). Latency
    # and tokens still cover every query.
    ranked = [r for r in rows if r.has_gold]
    out: dict[str, float] = {
        "recall@k": _mean([r.recall for r in ranked]),
        "precision@k": _mean([r.precision for r in ranked]),
        "hit@k": _mean([r.hit for r in ranked]),
        "mrr": _mean([r.mrr for r in ranked]),
        "ndcg@k": _mean([r.ndcg_at_k for r in ranked]),
        "latency_ms_p50": _percentile([r.latency_ms for r in rows], 50),
        "latency_ms_p95": _percentile([r.latency_ms for r in rows], 95),
        "tokens_mean": _mean([float(r.tokens) for r in rows]),
    }
    # Bootstrap 95% CIs on the headline ranking metrics, so a point estimate
    # ships with its uncertainty (a 304-question gap may not clear the band).
    # Same seed → reproducible bands across reruns; recorded in config.
    for key, arr in (
        ("recall@k", [r.recall for r in ranked]),
        ("ndcg@k", [r.ndcg_at_k for r in ranked]),
        ("mrr", [r.mrr for r in ranked]),
        ("hit@k", [r.hit for r in ranked]),
    ):
        lo, hi = metrics.bootstrap_ci(arr, seed=seed)
        out[f"{key}_ci_lo"] = lo
        out[f"{key}_ci_hi"] = hi
    if judged:
        # Only emit answer-quality metrics for rows that were actually judged
        # (a synthesized answer existed). Retrieval-only systems return
        # answer=None → no judged rows → these keys are omitted entirely, so the
        # scorecard shows "—" rather than a misleading 0%.
        answerable = [r for r in rows if not r.expect_abstain and r.correctness is not None]
        abstainers = [r for r in rows if r.expect_abstain and r.abstain_correct is not None]
        false_abst = [r for r in rows if not r.expect_abstain and r.abstained is not None]
        if answerable:
            out["correctness"] = _mean([r.correctness for r in answerable])
        if abstainers:
            out["abstention_accuracy"] = _mean([r.abstain_correct for r in abstainers])
        if false_abst:
            out["false_abstention"] = _mean([1.0 if r.abstained else 0.0 for r in false_abst])
    return out


def _percentile(xs: list[float], pct: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    rank = (pct / 100) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _ask_and_score(
    adapter: Adapter, q: Question, k: int, judge: Judge, judged: bool
) -> QuestionResult:
    res = adapter.query(q.question, top_k=k)
    ranked = res.ranked_ids()

    # Only score answer correctness for systems that synthesize an answer.
    # Retrieval-only systems (mem0/supermemory search, ck grep, CH retrieve_only)
    # return answer=None — they get retrieval metrics, not answer metrics, so
    # correctness aggregates fairly over answering systems only.
    verdict = None
    if judged and res.answer is not None and (q.answer is not None or q.expect_abstain):
        verdict = judge.grade(q.question, q.answer, res.answer)

    correctness = verdict.correctness if verdict else None
    abstained = verdict.abstained if verdict else None
    abstain_correct = None
    if q.expect_abstain and abstained is not None:
        abstain_correct = 1.0 if abstained else 0.0

    return QuestionResult(
        qid=q.id,
        track=q.track,
        expect_abstain=q.expect_abstain,
        has_gold=bool(q.relevant_ids),
        recall=metrics.recall_at_k(ranked, q.relevant_ids, k),
        precision=metrics.precision_at_k(ranked, q.relevant_ids, k),
        hit=metrics.hit_at_k(ranked, q.relevant_ids, k),
        mrr=metrics.mrr(ranked, q.relevant_ids),
        ndcg_at_k=metrics.ndcg_at_k(ranked, q.relevant_ids, k),
        correctness=correctness,
        abstained=abstained,
        abstain_correct=abstain_correct,
        latency_ms=res.latency_ms,
        tokens=res.tokens,
        answer=res.answer,
        ranked_ids=ranked,
    )


def run(
    adapter: Adapter,
    suite: Suite,
    *,
    k: int = 10,
    limit: int | None = None,
    judge: Judge | None = None,
    progress: bool = True,
    config: dict | None = None,
) -> Scorecard:
    started = datetime.now(timezone.utc)
    seed = int((config or {}).get("seed", 0))
    memories = suite.memories()
    questions: list[Question] = suite.questions()
    if limit is not None:
        questions = questions[:limit]

    judge = judge or Judge()
    judged = judge.enabled

    rows: list[QuestionResult] = []
    grouped = any(q.group is not None for q in questions)

    if grouped:
        # Per-group isolation (standard LoCoMo/LongMemEval protocol): reset +
        # ingest only a group's corpus, then ask only that group's questions
        # against it. Avoids pooling every conversation into one giant
        # non-standard haystack (and keeps each ingest small enough to be
        # feasible under provider rate limits).
        mem_by_group: dict[str | None, list] = {}
        for m in memories:
            mem_by_group.setdefault(m.group, []).append(m)
        seen_groups: list[str | None] = []
        for q in questions:
            if q.group not in seen_groups:
                seen_groups.append(q.group)
        n_ingested = 0
        for gi, g in enumerate(seen_groups, start=1):
            gmem = mem_by_group.get(g, [])
            _log(progress, f"[{adapter.name}/{suite.name}] group {gi}/{len(seen_groups)} ({g}): reset + ingest {len(gmem)} memories…")
            adapter.reset()
            adapter.ingest(gmem)
            n_ingested += len(gmem)
            for q in (q for q in questions if q.group == g):
                rows.append(_ask_and_score(adapter, q, k, judge, judged))
            if progress:
                _log(True, f"  scored {len(rows)}/{len(questions)}")
        n_memories = n_ingested
    else:
        _log(progress, f"[{adapter.name}/{suite.name}] reset + ingest {len(memories)} memories…")
        adapter.reset()
        adapter.ingest(memories)
        for i, q in enumerate(questions, start=1):
            rows.append(_ask_and_score(adapter, q, k, judge, judged))
            if progress and (i % 10 == 0 or i == len(questions)):
                _log(True, f"  scored {i}/{len(questions)}")
        n_memories = len(memories)

    adapter.close()
    finished = datetime.now(timezone.utc)

    tracks: dict[str, dict[str, float]] = {}
    track_names = sorted({r.track for r in rows if r.track})
    for t in track_names:
        tracks[t] = _aggregate([r for r in rows if r.track == t], judged, seed=seed)

    return Scorecard(
        system=adapter.name,
        suite=suite.name,
        k=k,
        n_memories=n_memories,
        n_questions=len(rows),
        judged=judged,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        metrics=_aggregate(rows, judged, seed=seed),
        tracks=tracks,
        per_question=rows,
        config=config or {},
    )


def _log(on: bool, msg: str) -> None:
    if on:
        print(msg, file=sys.stderr, flush=True)
