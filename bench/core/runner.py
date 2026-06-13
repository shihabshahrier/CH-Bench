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
    recall: float
    precision: float
    hit: float
    mrr: float
    ndcg10: float
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


def _aggregate(rows: list[QuestionResult], judged: bool) -> dict[str, float]:
    out: dict[str, float] = {
        "recall@k": _mean([r.recall for r in rows]),
        "precision@k": _mean([r.precision for r in rows]),
        "hit@k": _mean([r.hit for r in rows]),
        "mrr": _mean([r.mrr for r in rows]),
        "ndcg@10": _mean([r.ndcg10 for r in rows]),
        "latency_ms_p50": _percentile([r.latency_ms for r in rows], 50),
        "latency_ms_p95": _percentile([r.latency_ms for r in rows], 95),
        "tokens_mean": _mean([float(r.tokens) for r in rows]),
    }
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
    memories = suite.memories()
    questions: list[Question] = suite.questions()
    if limit is not None:
        questions = questions[:limit]

    judge = judge or Judge()
    judged = judge.enabled

    _log(progress, f"[{adapter.name}/{suite.name}] reset + ingest {len(memories)} memories…")
    adapter.reset()
    adapter.ingest(memories)

    rows: list[QuestionResult] = []
    for i, q in enumerate(questions, start=1):
        res = adapter.query(q.question, top_k=k)
        ranked = res.ranked_ids()

        # Only score answer correctness for systems that synthesize an answer.
        # Retrieval-only systems (mem0/supermemory search, ck grep, CH semantic
        # mode) return answer=None — they get retrieval metrics, not answer
        # metrics, so correctness aggregates fairly over answering systems only.
        verdict = None
        if judged and res.answer is not None and (q.answer is not None or q.expect_abstain):
            verdict = judge.grade(q.question, q.answer, res.answer)

        correctness = verdict.correctness if verdict else None
        abstained = verdict.abstained if verdict else None
        abstain_correct = None
        if q.expect_abstain and abstained is not None:
            abstain_correct = 1.0 if abstained else 0.0

        rows.append(
            QuestionResult(
                qid=q.id,
                track=q.track,
                expect_abstain=q.expect_abstain,
                recall=metrics.recall_at_k(ranked, q.relevant_ids, k),
                precision=metrics.precision_at_k(ranked, q.relevant_ids, k),
                hit=metrics.hit_at_k(ranked, q.relevant_ids, k),
                mrr=metrics.mrr(ranked, q.relevant_ids),
                ndcg10=metrics.ndcg_at_k(ranked, q.relevant_ids, 10),
                correctness=correctness,
                abstained=abstained,
                abstain_correct=abstain_correct,
                latency_ms=res.latency_ms,
                tokens=res.tokens,
                answer=res.answer,
                ranked_ids=ranked,
            )
        )
        if progress and (i % 10 == 0 or i == len(questions)):
            _log(True, f"  scored {i}/{len(questions)}")

    adapter.close()
    finished = datetime.now(timezone.utc)

    tracks: dict[str, dict[str, float]] = {}
    track_names = sorted({r.track for r in rows if r.track})
    for t in track_names:
        tracks[t] = _aggregate([r for r in rows if r.track == t], judged)

    return Scorecard(
        system=adapter.name,
        suite=suite.name,
        k=k,
        n_memories=len(memories),
        n_questions=len(rows),
        judged=judged,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        metrics=_aggregate(rows, judged),
        tracks=tracks,
        per_question=rows,
        config=config or {},
    )


def _log(on: bool, msg: str) -> None:
    if on:
        print(msg, file=sys.stderr, flush=True)
