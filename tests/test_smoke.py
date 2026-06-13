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
