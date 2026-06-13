#!/usr/bin/env python3
"""Assemble a cross-system comparison table from results/*.json.

Picks the latest scorecard per (system, suite), prints a Markdown table, and
writes it to results/<suite>__COMPARISON.md. Retrieval-only systems show "—" for
answer-quality columns.

    python3 scripts/compare.py [--suite contextheavy] [--results results]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _pct(v) -> str:
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "—"


def _ms(v) -> str:
    return f"{v:.0f}ms" if isinstance(v, (int, float)) else "—"


def latest_per_system(results_dir: Path, suite: str) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for p in sorted(results_dir.glob(f"*__{suite}__*.json")):
        card = json.loads(p.read_text())
        if card.get("suite") != suite:
            continue
        # Filenames are timestamped, sorted ascending → last write wins.
        cards[card["system"]] = card
    return cards


def build_table(cards: dict[str, dict], suite: str) -> str:
    rows = []
    for sys, c in cards.items():
        m = c.get("metrics", {})
        answers = "correctness" in m
        rows.append(
            {
                "system": sys,
                "recall": m.get("recall@k", 0.0),
                "ndcg": m.get("ndcg@10", 0.0),
                "mrr": m.get("mrr", 0.0),
                "hit": m.get("hit@k", 0.0),
                "correctness": m.get("correctness") if answers else None,
                "abst": m.get("abstention_accuracy") if answers else None,
                "p50": m.get("latency_ms_p50", 0.0),
                "k": c.get("k"),
                "n": c.get("n_questions"),
                "judged": c.get("judged"),
            }
        )
    rows.sort(key=lambda r: r["recall"], reverse=True)

    out: list[str] = []
    out.append(f"# CH-Bench comparison — `{suite}` suite")
    out.append("")
    n = rows[0]["n"] if rows else 0
    k = rows[0]["k"] if rows else 0
    out.append(f"{len(rows)} systems · {n} questions · k={k} · LLM-judge: qwen3.5-397b (NVIDIA NIM)")
    out.append("")
    out.append("| system | recall@k | nDCG@10 | MRR | hit@k | answer correctness | abstention | latency p50 |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        out.append(
            f"| **{r['system']}** | {_pct(r['recall'])} | {_pct(r['ndcg'])} | {_pct(r['mrr'])} "
            f"| {_pct(r['hit'])} | {_pct(r['correctness'])} | {_pct(r['abst'])} | {_ms(r['p50'])} |"
        )
    out.append("")
    out.append("Retrieval-only systems (mem0/supermemory search, ck grep) report `—` for "
               "answer-quality columns — they return ranked memories, not a synthesized answer. "
               "CH is scored end-to-end (retrieval **and** answer).")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="contextheavy")
    ap.add_argument("--results", default="results")
    args = ap.parse_args()
    rdir = Path(args.results)
    cards = latest_per_system(rdir, args.suite)
    if not cards:
        raise SystemExit(f"no scorecards for suite '{args.suite}' in {rdir}")
    table = build_table(cards, args.suite)
    print(table)
    out_path = rdir / f"{args.suite}__COMPARISON.md"
    out_path.write_text(table)
    print(f"\nwrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
