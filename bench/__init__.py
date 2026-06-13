"""CH-Bench — a memory/RAG benchmark for AI brains.

Public surface:
    from bench import run, Memory, Question, QueryResult
    from bench import adapters, suites
"""

from __future__ import annotations

from . import adapters, metrics, suites
from .core import (
    Adapter,
    Judge,
    Memory,
    Question,
    QueryResult,
    QuestionResult,
    RetrievedSource,
    Scorecard,
    Suite,
    run,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "run",
    "Adapter",
    "Suite",
    "Memory",
    "Question",
    "QueryResult",
    "RetrievedSource",
    "Judge",
    "Scorecard",
    "QuestionResult",
    "adapters",
    "suites",
    "metrics",
]
