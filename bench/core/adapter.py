"""The Adapter contract: one system under test.

Implement these four methods for any brain (Context-Heavy, GBrain, Mem0, Zep,
Supermemory, a plain vector store) and the same suites score it apples-to-apples.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import Memory, QueryResult


@runtime_checkable
class Adapter(Protocol):
    name: str

    def reset(self) -> None:
        """Clear the benchmark namespace so a run starts from empty.

        Must remove only data this harness created (track ids on ingest);
        a run against a shared/live store must never delete the user's notes.
        """
        ...

    def ingest(self, memories: list[Memory]) -> None:
        """Store every memory. Build the suite-id -> system-id mapping here so
        `query` can resolve retrieved sources back to suite ids."""
        ...

    def query(self, question: str, top_k: int) -> QueryResult:
        """Answer one question. `sources` must be ranked best-first with ids
        resolved to suite-local Memory ids (None when unresolvable)."""
        ...

    def close(self) -> None:
        """Release resources / final cleanup. Default no-op."""
        ...
