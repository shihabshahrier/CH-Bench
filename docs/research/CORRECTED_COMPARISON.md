# ContextHeavy Suite — Corrected Comparison (abstain excluded from ranking)

Ranking metrics (recall/nDCG/mrr) aggregate ONLY over questions with gold
relevant_ids. Abstain questions (no gold) are scored separately. This fixes a
metric artifact that averaged spurious 0s into every system's ranking score.
Answer metrics (correctness/abstention) are LLM-judged where a system answers.

| system | recall@k | nDCG@10 | mrr | correctness | abstention | answers? |
| --- | --- | --- | --- | --- | --- | --- |
| supermemory | 100.0% | 97.7% | 96.7% | — | — | no |
| ch | 100.0% | 95.1% | 94.0% | 96.7% | 100.0% | yes |
| gbrain | 100.0% | 92.8% | 90.4% | — | — | no |
| mock | 90.0% | 80.1% | 77.5% | 68.3% | 0.0% | yes |
| ck | 83.3% | 75.3% | 72.8% | — | — | no |
| mem0 | 26.7% | 24.8% | 20.5% | — | — | no |
