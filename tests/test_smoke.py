"""End-to-end smoke: the mock adapter on the custom suite, judge off.

Proves the full loop (ingest → query → metrics → aggregate) with no network and
no API key, so CI stays green and free.
"""

from __future__ import annotations

from bench import adapters, metrics, suites
from bench.core.judge import Judge
from bench.core.runner import run


def test_mock_contextheavy_runs():
    card = run(
        adapters.build("mock"),
        suites.build("contextheavy"),
        k=5,
        judge=Judge(base_url="", model="", api_key=""),  # disabled
        progress=False,
    )
    assert card.n_memories >= 20
    assert card.n_questions >= 15
    # Mock BM25-lite must beat random on its own corpus.
    assert card.metrics["recall@k"] > 0.5
    assert card.metrics["mrr"] > 0.5
    # Per-profession tracks are present.
    assert {"developer", "founder", "researcher"} <= set(card.tracks)


def test_abstention_questions_present():
    qs = suites.build("contextheavy").questions()
    assert any(q.expect_abstain for q in qs)
    # Mock abstains when nothing scores above the floor.
    res = adapters.build("mock")
    res.ingest(suites.build("contextheavy").memories())
    out = res.query("What is the airspeed velocity of an unladen swallow?", top_k=5)
    assert "don't have information" in (out.answer or "")


def test_retrieval_metrics_math():
    ranked = ["a", "b", "c", None]
    assert metrics.recall_at_k(ranked, ["a", "c"], 5) == 1.0
    assert metrics.hit_at_k(ranked, ["c"], 5) == 1.0
    assert metrics.mrr(ranked, ["b"]) == 0.5
    assert metrics.recall_at_k(ranked, ["z"], 5) == 0.0

def test_abstain_excluded_from_ranking_metrics():
    """Abstain questions (no gold) must NOT drag ranking metrics — they have no
    gold to rank, so recall/nDCG/mrr are undefined for them (regression for the
    metric-artifact fix)."""
    from bench.core.runner import QuestionResult, _aggregate

    def row(qid, has_gold, recall, ndcg, mrr, expect_abstain=False):
        return QuestionResult(
            qid=qid, track="t", expect_abstain=expect_abstain, has_gold=has_gold,
            recall=recall, precision=recall, hit=recall, mrr=mrr, ndcg_at_k=ndcg,
            correctness=None, abstained=None, abstain_correct=None,
            latency_ms=1.0, tokens=0, answer=None, ranked_ids=[],
        )

    rows = [
        row("g1", True, 1.0, 1.0, 1.0),
        row("g2", True, 1.0, 1.0, 1.0),
        row("abstain", False, 0.0, 0.0, 0.0, expect_abstain=True),
    ]
    agg = _aggregate(rows, judged=False)
    # Without the fix this would be 2/3 ≈ 0.667; with it, the two gold rows = 1.0.
    assert agg["ndcg@k"] == 1.0
    assert agg["recall@k"] == 1.0
    assert agg["mrr"] == 1.0
    # Latency still covers every query (3 rows), not just the gold ones.
    assert agg["latency_ms_p50"] == 1.0
