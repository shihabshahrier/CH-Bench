"""ContextHeavy-Bench — the custom, profession-based suite.

Loads every `*.json` track file under datasets/contextheavy/ (or a directory
given by CH_BENCH_DATA). Each file bundles a corpus and an eval set written to
probe what standard benchmarks miss: cross-project recall, causal 'why did we
decide' recall, temporal update/supersession, and abstention. Question.track is
set from each file so the runner emits per-profession scores.

File schema:
    {"track": "developer",
     "memories":  [{"id","text","metadata"}],
     "questions": [{"id","question","answer","relevant_ids","expect_abstain","metadata"}]}
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..core.types import Memory, Question

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "datasets" / "contextheavy"


class ContextHeavySuite:
    name = "contextheavy"

    def __init__(self, data_dir: str | os.PathLike | None = None) -> None:
        self.data_dir = Path(data_dir or os.getenv("CH_BENCH_DATA", _DEFAULT_DIR))
        self._files = sorted(self.data_dir.glob("*.json"))
        if not self._files:
            raise SystemExit(f"no track files found in {self.data_dir}")

    def _load(self) -> list[dict]:
        return [json.loads(p.read_text()) for p in self._files]

    def memories(self) -> list[Memory]:
        out: list[Memory] = []
        for track in self._load():
            for m in track.get("memories", []):
                out.append(Memory(id=m["id"], text=m["text"], metadata=m.get("metadata", {})))
        return out

    def questions(self) -> list[Question]:
        out: list[Question] = []
        for track in self._load():
            tname = track.get("track")
            for q in track.get("questions", []):
                out.append(
                    Question(
                        id=q["id"],
                        question=q["question"],
                        answer=q.get("answer"),
                        relevant_ids=q.get("relevant_ids", []),
                        track=tname,
                        expect_abstain=q.get("expect_abstain", False),
                        metadata=q.get("metadata", {}),
                    )
                )
        return out
