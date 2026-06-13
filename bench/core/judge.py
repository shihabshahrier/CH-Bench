"""LLM-as-judge: scores answer correctness, groundedness, and abstention.

Targets any OpenAI-compatible /chat/completions endpoint (NVIDIA NIM,
OpenRouter, OpenAI, a local model). Configured from the environment so no key
is ever hardcoded:

    JUDGE_BASE_URL   e.g. https://integrate.api.nvidia.com/v1
    JUDGE_MODEL      e.g. qwen/qwen3.5-397b-a17b
    JUDGE_API_KEY    provider key

If JUDGE_API_KEY is unset the judge is disabled and `Judge.enabled` is False;
the runner then reports correctness/abstention as null and scores only the
retrieval metrics. A fixed judge model + rubric keeps cross-system comparison
fair (the research's main caveat: judge variance).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(slots=True)
class Verdict:
    # 1.0 correct, 0.5 partially correct, 0.0 wrong/unsupported.
    correctness: float
    # True when the answer declined / said the brain doesn't know.
    abstained: bool
    reasoning: str = ""


_RUBRIC = (
    "You are a strict grader for a memory/RAG system. Compare the SYSTEM ANSWER "
    "to the REFERENCE ANSWER for the QUESTION. Grade only factual agreement with "
    "the reference; ignore style, length, and extra hedging.\n"
    "Return STRICT JSON, no prose, with keys:\n"
    '  "correctness": 1.0 if the system answer states the reference fact, 0.5 if '
    "partially correct or missing detail, 0.0 if wrong, contradictory, or empty.\n"
    '  "abstained": true if the system answer declines to answer / says it does '
    'not know / has no information, else false.\n'
    '  "reasoning": one short sentence.\n'
)


class Judge:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("JUDGE_BASE_URL", "")).rstrip("/")
        self.model = model or os.getenv("JUDGE_MODEL", "")
        self.api_key = api_key or os.getenv("JUDGE_API_KEY", "")
        # Tried in order after the primary on 429/5xx/timeout, so a rate-limited
        # judge fails over to the next reasoning model instead of dropping to the
        # heuristic. Comma-separated JUDGE_FALLBACK_MODELS.
        self.fallbacks = [m.strip() for m in os.getenv("JUDGE_FALLBACK_MODELS", "").split(",") if m.strip()]
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.model and self.api_key)

    def grade(self, question: str, reference: str | None, system_answer: str | None) -> Verdict | None:
        """Grade one answer. Returns None if the judge is disabled."""
        if not self.enabled:
            return None
        answer = (system_answer or "").strip()
        if not answer:
            return Verdict(correctness=0.0, abstained=True, reasoning="empty answer")
        # Heuristic abstention pre-check so a confident abstention is caught even
        # if the judge model is flaky; the judge still refines correctness.
        heuristic_abstain = _looks_like_abstention(answer)
        user = (
            f"QUESTION:\n{question}\n\n"
            f"REFERENCE ANSWER:\n{reference or '(none provided — judge on plausibility/grounding)'}\n\n"
            f"SYSTEM ANSWER:\n{answer}\n"
        )
        try:
            raw = self._chat(_RUBRIC, user)
            v = _parse_verdict(raw)
            if v is not None:
                return v
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass
        # Fall back to the heuristic when the judge call/parsing fails.
        return Verdict(
            correctness=0.0,
            abstained=heuristic_abstain,
            reasoning="judge unavailable; heuristic only",
        )

    def _chat(self, system: str, user: str) -> str:
        last: Exception | None = None
        for model in [self.model, *self.fallbacks]:
            try:
                return self._chat_once(model, system, user)
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (429, 500, 502, 503) and model != ([self.model, *self.fallbacks][-1]):
                    continue  # rate-limited / transient → next model
                raise
            except (urllib.error.URLError, TimeoutError):
                last = None
                continue  # transport/timeout → next model
        if last:
            raise last
        raise urllib.error.URLError("all judge models failed")

    def _chat_once(self, model: str, system: str, user: str) -> str:
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.0,
                "max_tokens": 300,
            }
        ).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read())
        return payload["choices"][0]["message"]["content"]


_ABSTAIN_PAT = re.compile(
    r"\b(i (?:do not|don'?t) (?:know|have)|no information|not (?:in|found in) the notes|"
    r"the (?:brain|notes) (?:don'?t|do not) (?:know|contain|cover)|cannot answer|"
    r"unable to (?:answer|find)|insufficient (?:information|context))\b",
    re.IGNORECASE,
)


def _looks_like_abstention(text: str) -> bool:
    return bool(_ABSTAIN_PAT.search(text))


def _parse_verdict(raw: str) -> Verdict | None:
    # Models sometimes wrap JSON in prose or fences; grab the first object.
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    try:
        c = float(obj.get("correctness", 0.0))
    except (TypeError, ValueError):
        c = 0.0
    c = max(0.0, min(1.0, c))
    return Verdict(
        correctness=c,
        abstained=bool(obj.get("abstained", False)),
        reasoning=str(obj.get("reasoning", ""))[:200],
    )
