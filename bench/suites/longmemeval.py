"""LongMemEval loader — long-term conversational memory.

Dataset (not bundled; download once):
    https://github.com/xiaowu0162/LongMemEval  (or its HuggingFace mirror)
Place the JSON at datasets/longmemeval/data/longmemeval_s.json (or set
LONGMEMEVAL_FILE). The file is a list of items shaped roughly:

    {"question_id", "question", "answer",
     "haystack_sessions": [[{"role","content"}, ...], ...],
     "answer_session_ids": [...]}

Each chat turn becomes a Memory (id = "{question_id}:{session}:{turn}"); the
sessions that contain the answer become the gold relevant_ids so retrieval is
scored, and `answer` drives the judge. Abstention items (answer == null / the
dataset's 'no answer' marker) are flagged.

This mapping is intentionally simple and documented; tune it in P16 once we run
against the real file (LongMemEval has several question types we can split into
tracks).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..core.types import Memory, Question

_DEFAULT = Path(__file__).resolve().parents[2] / "datasets" / "longmemeval" / "data" / "longmemeval_s.json"


class LongMemEvalSuite:
    name = "longmemeval"

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self.path = Path(path or os.getenv("LONGMEMEVAL_FILE", _DEFAULT))
        if not self.path.exists():
            raise SystemExit(
                f"LongMemEval data not found at {self.path}.\n"
                "Download it from https://github.com/xiaowu0162/LongMemEval and set "
                "LONGMEMEVAL_FILE, or place longmemeval_s.json under "
                "datasets/longmemeval/data/."
            )
        self._items = json.loads(self.path.read_text())

    def _turn_id(self, qid: str, s_idx: int, t_idx: int) -> str:
        return f"{qid}:s{s_idx}:t{t_idx}"

    def memories(self) -> list[Memory]:
        out: list[Memory] = []
        for item in self._items:
            qid = str(item.get("question_id") or item.get("id"))
            sessions = item.get("haystack_sessions") or item.get("sessions") or []
            for s_idx, session in enumerate(sessions):
                for t_idx, turn in enumerate(session):
                    content = turn.get("content") if isinstance(turn, dict) else str(turn)
                    if not content:
                        continue
                    role = turn.get("role", "") if isinstance(turn, dict) else ""
                    out.append(
                        Memory(
                            id=self._turn_id(qid, s_idx, t_idx),
                            text=(f"{role}: {content}" if role else content),
                            metadata={"question_id": qid, "session": s_idx},
                            group=qid,  # each question's haystack is its own isolated corpus
                        )
                    )
        return out

    def questions(self) -> list[Question]:
        out: list[Question] = []
        for item in self._items:
            qid = str(item.get("question_id") or item.get("id"))
            answer = item.get("answer")
            ans_sessions = set(item.get("answer_session_ids") or [])
            relevant: list[str] = []
            sessions = item.get("haystack_sessions") or item.get("sessions") or []
            for s_idx, session in enumerate(sessions):
                # answer_session_ids may be indices or session-id strings; match either.
                sid = item.get("haystack_session_ids", [None] * len(sessions))[s_idx] if item.get("haystack_session_ids") else s_idx
                if s_idx in ans_sessions or sid in ans_sessions:
                    relevant.extend(
                        self._turn_id(qid, s_idx, t_idx) for t_idx in range(len(session))
                    )
            out.append(
                Question(
                    id=qid,
                    question=item["question"],
                    answer=answer,
                    relevant_ids=relevant,
                    track=item.get("question_type", "longmemeval"),
                    expect_abstain=(answer is None or str(answer).strip().lower() in {"", "no answer", "n/a"}),
                    metadata={"question_type": item.get("question_type")},
                    group=qid,
                )
            )
        return out
