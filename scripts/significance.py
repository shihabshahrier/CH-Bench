#!/usr/bin/env python3
"""Cross-system significance: is the baseline's retrieval lead real, or noise?

Loads the latest scorecard per system for a suite, aligns each competitor's
per-question metric array against the baseline (default `ch`) by qid, and runs a
paired permutation test (bench.metrics.paired_permutation) per metric. Writes a
baseline-vs-each-competitor table of mean gap + p-value to results/SIGNIFICANCE.md.

Paired by qid because every system answers the identical question set — the
per-question difference cancels question-difficulty variance, so the test asks
exactly "could this gap arise by chance?".

    python3 scripts/significance.py [--suite locomo] [--baseline ch] [--note full10]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bench.metrics import paired_permutation  # noqa: E402

# Per-question fields carried in each scorecard row (see runner.QuestionResult).
METRICS = [("recall", "recall@k"), ("ndcg_at_k", "nDCG@k"), ("mrr", "MRR"), ("hit", "hit@k")]


def _latest_per_system(results_dir: str, suite: str, note: str | None) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(results_dir, f"*__{suite}__*.json"))):
        try:
            card = json.loads(open(path).read())
        except (ValueError, OSError):
            continue
        if card.get("suite") != suite:
            continue
        if note is not None and (card.get("config") or {}).get("note") != note:
            continue
        sysname = card["system"]
        cur = latest.get(sysname)
        if cur is None or str(card.get("finished_at", "")) > str(cur.get("finished_at", "")):
            latest[sysname] = card
    return latest


def _gold_by_qid(card: dict) -> dict[str, dict]:
    """qid → per-question row, keeping only rows that carried gold (ranking-scored)."""
    return {r["qid"]: r for r in card.get("per_question", []) if r.get("has_gold")}


def _aligned(base_rows: dict[str, dict], comp_rows: dict[str, dict], field: str) -> tuple[list[float], list[float]]:
    """Metric arrays for the qids both systems scored, in a stable shared order."""
    qids = sorted(set(base_rows) & set(comp_rows))
    a = [float(base_rows[q][field]) for q in qids]
    b = [float(comp_rows[q][field]) for q in qids]
    return a, b


def build(results_dir: str, suite: str, baseline: str, note: str | None) -> str:
    cards = _latest_per_system(results_dir, suite, note)
    if baseline not in cards:
        raise SystemExit(f"no '{baseline}' scorecard for suite '{suite}'" + (f" note='{note}'" if note else ""))
    base = cards[baseline]
    base_rows = _gold_by_qid(base)
    competitors = sorted(s for s in cards if s != baseline)

    out: list[str] = []
    out.append(f"# Significance — `{baseline}` vs the field · `{suite}` suite")
    out.append("")
    scope = f" · note=`{note}`" if note else ""
    out.append(
        f"Paired permutation test (10k resamples), aligned by qid over gold-bearing "
        f"questions. Gap = mean({baseline} − competitor){scope}. "
        f"**p < 0.05** ⇒ the gap is unlikely to be chance."
    )
    out.append("")
    header = "| competitor | n | " + " | ".join(f"{lbl} gap / p" for _, lbl in METRICS) + " |"
    sep = "| --- | --- | " + " | ".join("---" for _ in METRICS) + " |"
    out.append(header)
    out.append(sep)

    for comp in competitors:
        comp_rows = _gold_by_qid(cards[comp])
        n = len(set(base_rows) & set(comp_rows))
        cells: list[str] = []
        for field, _lbl in METRICS:
            a, b = _aligned(base_rows, comp_rows, field)
            if not a:
                cells.append("—")
                continue
            gap = sum(x - y for x, y in zip(a, b)) / len(a)
            p = paired_permutation(a, b, seed=0)
            mark = "**" if p < 0.05 else ""
            cells.append(f"{mark}{gap * 100:+.1f}pp / p={p:.3f}{mark}")
        out.append(f"| {comp} | {n} | " + " | ".join(cells) + " |")

    out.append("")
    out.append(
        "Bold = significant at α=0.05. A non-significant gap means the two systems "
        "are statistically indistinguishable on that metric at this sample size — "
        "report it as a tie, not a win."
    )
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--suite", default="locomo")
    ap.add_argument("--baseline", default="ch")
    ap.add_argument("--note", default=None, help="only compare scorecards with this config.note")
    args = ap.parse_args()
    table = build(args.results, args.suite, args.baseline, args.note)
    print(table)
    out_path = os.path.join(args.results, "SIGNIFICANCE.md")
    open(out_path, "w").write(table)
    print(f"\nwrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
