"""The Suite contract: a corpus + an eval set.

Standard suites (LongMemEval, LoCoMo) load published datasets; the custom
ContextHeavy suite generates profession-track histories. All expose the same
two methods so the runner is suite-agnostic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import Memory, Question


@runtime_checkable
class Suite(Protocol):
    name: str

    def memories(self) -> list[Memory]:
        """The corpus to ingest before any question is asked."""
        ...

    def questions(self) -> list[Question]:
        """The eval items to score against the ingested corpus."""
        ...
