"""LoCoMo loader — long multi-session conversations with QA probes.

Dataset (not bundled; download once):
    https://github.com/snap-research/LoCoMo
Place locomo10.json at datasets/locomo/data/locomo10.json (or set LOCOMO_FILE).
Structure (per sample): a `conversation` with sessions of dialog turns, plus a
`qa` list of {question, answer, evidence:[turn ids], category}.

Each dialog turn becomes a Memory keyed by its dialog id; `qa.evidence` turn ids
become the gold relevant_ids; `qa.answer` drives the judge; `qa.category` is the
track. Adapter-agnostic, so the same questions can hit any system.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..core.types import Memory, Question

_DEFAULT = Path(__file__).resolve().parents[2] / "datasets" / "locomo" / "data" / "locomo10.json"


class LoCoMoSuite:
    name = "locomo"

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self.path = Path(path or os.getenv("LOCOMO_FILE", _DEFAULT))
        if not self.path.exists():
            raise SystemExit(
                f"LoCoMo data not found at {self.path}.\n"
                "Download it from https://github.com/snap-research/LoCoMo and set "
                "LOCOMO_FILE, or place locomo10.json under datasets/locomo/data/."
            )
        self._samples = json.loads(self.path.read_text())

    def _iter_turns(self):
        """Yield (sample_idx, dialog_id, speaker, text) for every turn."""
        for s_idx, sample in enumerate(self._samples):
            conv = sample.get("conversation", {})
            for key, turns in conv.items():
                if not key.startswith("session") or not isinstance(turns, list):
                    continue
                for turn in turns:
                    did = turn.get("dia_id") or turn.get("id")
                    text = turn.get("text") or turn.get("content") or ""
                    if did and text:
                        yield s_idx, str(did), turn.get("speaker", ""), text

    def memories(self) -> list[Memory]:
        out: list[Memory] = []
        for s_idx, did, speaker, text in self._iter_turns():
            out.append(
                Memory(
                    id=f"{s_idx}:{did}",
                    text=(f"{speaker}: {text}" if speaker else text),
                    metadata={"sample": s_idx, "dia_id": did},
                )
            )
        return out

    def questions(self) -> list[Question]:
        out: list[Question] = []
        for s_idx, sample in enumerate(self._samples):
            for q_idx, qa in enumerate(sample.get("qa", [])):
                evidence = qa.get("evidence") or []
                relevant = [f"{s_idx}:{e}" for e in evidence]
                ans = qa.get("answer")
                out.append(
                    Question(
                        id=f"{s_idx}:q{q_idx}",
                        question=qa["question"],
                        answer=None if ans is None else str(ans),
                        relevant_ids=relevant,
                        track=str(qa.get("category", "locomo")),
                        expect_abstain=(ans is None),
                        metadata={"category": qa.get("category")},
                    )
                )
        return out
