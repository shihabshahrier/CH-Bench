"""Render a Scorecard to JSON (machine) + Markdown (human).

Filenames are `{system}__{suite}__{timestamp}.{ext}` under the output dir, so
multiple runs accumulate and a comparison table can be assembled in P16.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .core.runner import Scorecard

_PCT = {"recall@k", "precision@k", "hit@k", "mrr", "ndcg@10", "correctness", "abstention_accuracy", "false_abstention"}


def _fmt(key: str, val: float) -> str:
    if key in _PCT:
        return f"{val * 100:.1f}%"
    if key.startswith("latency"):
        return f"{val:.0f}ms"
    if key == "tokens_mean":
        return f"{val:.0f}"
    return f"{val:.3f}"


def _metrics_table(metrics: dict[str, float]) -> str:
    rows = ["| metric | value |", "| --- | --- |"]
    for k, v in metrics.items():
        rows.append(f"| {k} | {_fmt(k, v)} |")
    return "\n".join(rows)


def to_markdown(card: Scorecard) -> str:
    lines: list[str] = []
    lines.append(f"# Scorecard — `{card.system}` on `{card.suite}`")
    lines.append("")
    lines.append(
        f"- corpus: **{card.n_memories}** memories · questions: **{card.n_questions}** "
        f"· k=**{card.k}** · judge: **{'on' if card.judged else 'off'}**"
    )
    lines.append(f"- run: {card.started_at} → {card.finished_at}")
    if card.config:
        cfg = ", ".join(f"{k}={v}" for k, v in card.config.items())
        lines.append(f"- config: {cfg}")
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append(_metrics_table(card.metrics))
    lines.append("")
    if card.tracks:
        lines.append("## Per track")
        lines.append("")
        cols = ["recall@k", "ndcg@10", "mrr", "hit@k"]
        if card.judged:
            cols += ["correctness", "abstention_accuracy"]
        header = "| track | " + " | ".join(cols) + " | latency_p50 |"
        sep = "| --- |" + " --- |" * (len(cols) + 1)
        lines.append(header)
        lines.append(sep)
        for t, m in card.tracks.items():
            # Missing answer-quality keys (retrieval-only systems) render as "—".
            cells = [(_fmt(c, m[c]) if c in m else "—") for c in cols]
            cells.append(_fmt("latency_ms_p50", m.get("latency_ms_p50", 0.0)))
            lines.append(f"| {t} | " + " | ".join(cells) + " |")
        lines.append("")
    # A few sample answers for eyeballing grounding.
    sample = [r for r in card.per_question][:5]
    if sample:
        lines.append("## Sample answers")
        lines.append("")
        for r in sample:
            a = (r.answer or "").replace("\n", " ")
            if len(a) > 240:
                a = a[:240] + "…"
            tag = "abstain" if r.expect_abstain else "answerable"
            lines.append(f"- **{r.qid}** ({tag}, recall={_fmt('recall@k', r.recall)}): {a}")
        lines.append("")
    return "\n".join(lines)


def write_scorecard(card: Scorecard, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"{card.system}__{card.suite}__{ts}"
    json_path = out / f"{stem}.json"
    md_path = out / f"{stem}.md"
    json_path.write_text(json.dumps(card.to_dict(), indent=2, default=str))
    md_path.write_text(to_markdown(card))
    return json_path, md_path
