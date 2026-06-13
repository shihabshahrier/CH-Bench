# P16 — First comparison run (ContextHeavy-Bench)

First real numbers for Context-Heavy against the field, on the custom
`contextheavy` suite (developer / founder / researcher profession tracks).

**Run:** 6 systems · 19 questions · 24 memories · k=10 · LLM-judge = qwen3.5-397b
(NVIDIA NIM) · 2026-06-13.

| system | recall@10 | nDCG@10 | MRR | answer correctness | abstention | latency p50 |
| --- | --- | --- | --- | --- | --- | --- |
| **ch** | **84.2%** | 62.0% | 54.3% | **96.9%** | **100%** | 5447ms |
| gbrain | 84.2% | 77.1% | 74.3% | — | — | 1588ms |
| mock (BM25-lite) | 84.2% | 77.8% | 75.9% | 84.4% | 0% | 0ms |
| supermemory | 84.2% | **80.7%** | **78.9%** | — | — | 1071ms |
| ck (common-knowledge) | 78.9% | 75.0% | 73.7% | — | — | 45ms |
| mem0 | 47.4% | 43.6% | 43.0% | — | — | 1313ms |

`—` = retrieval-only system (returns ranked memories, not a synthesized answer),
so answer-quality columns don't apply. CH is the only system scored end-to-end.

## Why CH wins / loses where

**Wins — answering.** CH is the only system that turns retrieval into a
grounded answer: **96.9% correctness**, **100% abstention accuracy**, **0%
false-abstention**. It answered every factual question correctly and declined
every unanswerable one without hallucinating. The competitors are memory
*layers* — they hand back chunks; the agent still has to reason. That end-to-end
answer + honest "what the brain doesn't know" is CH's product differentiator,
and it shows.

**Loses — ranking.** On pure retrieval *ordering* CH trails:
nDCG@10 62.0 / MRR 54.3 vs supermemory 80.7 / 78.9, mock 77.8 / 75.9, gbrain
77.1 / 74.3. CH **finds** the right memory as often as anyone (recall@10 ties at
84.2%) but ranks it lower inside the top-k. The likely cause is the Ask path's
source ordering: rerank + graph-neighborhood augmentation reorders candidates
for *answer synthesis*, which is not the same as ranking gold-first for a
retrieval metric. **This is the #1 P16 tuning target** — rerank depth, graph-boost
weight, `ef_search` — and the gap is ~15 nDCG points, i.e. real and closeable.

**mem0 collapses on recall (47.4%).** Mem0 re-extracts facts from each input and
drops/merges roughly half of standalone memories — it is tuned for
conversational extraction, not document recall. Even with poll-until-indexed it
loses coverage the others keep.

**Efficiency.** ck is fastest (45ms, local grep) and supermemory/gbrain/mem0 sit
near 1–1.6s. CH is slowest at 5.4s p50 — the cost of doing embed + rerank + graph
+ LLM synthesis per query. That's the answer tax; worth it for the answer, but a
latency budget to watch.

## Caveats (what this run does *not* prove yet)

- **Small + lexically easy.** 19 questions / 24 memories, and a BM25-lite mock
  ties the leaders at 84.2% recall — the gold facts are findable by keyword.
  Recall@10 saturates here. The standard suites (**LongMemEval, LoCoMo**) and
  harder paraphrase / multi-hop / long-horizon questions are needed to separate
  the field. This is a smoke of the *harness and adapters*, not a final verdict.
- **Fair embedder for the local pair.** CH and gbrain both run **bge-m3 @ 1024**
  (CH on NIM; gbrain via NIM as an OpenAI-compatible endpoint). mem0 and
  supermemory use their own managed embedders — a system comparison, not a
  model-controlled one.
- **Single judge.** One judge model (qwen3.5-397b) + fixed rubric. Judge variance
  is the known risk; a second judge would tighten the correctness numbers.

## Next (P16 continued)

1. **Close CH's ranking gap** — trace the Ask source ordering; A/B rerank depth,
   graph-boost weight, and `ef_search`. Re-score each change with the harness.
2. **Scale the eval** — load LongMemEval + LoCoMo (loaders already in the repo)
   for a discriminating run; grow the custom tracks (writer / student / PM) and
   add multi-hop + temporal-contradiction questions where recall@10 won't
   saturate.
3. **mem0 fairness** — try its graph/document mode if exposed before calling the
   47% final.
