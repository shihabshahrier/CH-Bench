"""Shared data contracts for the harness.

A *suite* produces `Memory` items (the corpus to ingest) and `Question` items
(the eval set). An *adapter* ingests the memories into a system under test and
answers the questions, returning a `QueryResult`. Everything downstream —
metrics, judge, scorecard — speaks only these types, so suites and adapters
stay fully decoupled.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Memory:
    """One unit of knowledge to store in the brain under test.

    `id` is the suite-local stable identifier; adapters map it to whatever id
    the underlying system assigns and must be able to resolve retrieved
    sources back to this id (so recall/MRR/nDCG can be scored against the
    gold `Question.relevant_ids`).
    """

    id: str
    text: str
    # Free-form: project, profession track, ISO timestamp, session id, etc.
    # Temporal/update suites rely on `timestamp` ordering; track scoring on
    # `track`. Adapters may forward whichever fields the system understands.
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class Question:
    """One eval item.

    `relevant_ids` are the gold Memory ids that should be retrieved (drives
    recall@k / MRR / nDCG). `answer` is the gold answer text (drives the
    LLM-judge correctness score). A question may have one, the other, or both.
    `expect_abstain=True` marks questions whose correct behavior is "the brain
    doesn't know" — used to score over-confident hallucination.
    """

    id: str
    question: str
    answer: str | None = None
    relevant_ids: list[str] = field(default_factory=list)
    track: str | None = None
    expect_abstain: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class RetrievedSource:
    """A single ranked source the adapter returned, resolved to a suite id.

    `id` is the suite-local Memory id when the adapter could resolve it (else
    None — counted as a non-relevant retrieval). `score` is the system's own
    relevance score (similarity/rerank logit); used only for ordering, not
    compared across systems.
    """

    id: str | None
    text: str = ""
    score: float = 0.0


@dataclass(slots=True)
class QueryResult:
    """What an adapter returns for one question."""

    answer: str | None
    sources: list[RetrievedSource] = field(default_factory=list)
    latency_ms: float = 0.0
    # Prompt+completion tokens if the system reports them; 0 = unknown.
    tokens: int = 0
    # Per-system payload for debugging / deep dives; never scored.
    raw: dict = field(default_factory=dict)

    def ranked_ids(self) -> list[str | None]:
        return [s.id for s in self.sources]
