# ContextHeavy Suite — FINAL Corrected Comparison

Ranking metrics over gold-bearing questions only (abstain excluded — see the
metric-artifact fix). CH row reflects the full P1-P5 build incl. the body-overlap
researcher lever. Competitors recomputed from their saved per-question data.

| system | recall@k | nDCG@10 | mrr | correctness | abstention | answers? |
| --- | --- | --- | --- | --- | --- | --- |
| supermemory | 100.0% | 97.7% | 96.7% | — | — | no |
| ch | 100.0% | 95.3% | 93.7% | 96.7% | 80.0% | yes |
| gbrain | 100.0% | 92.8% | 90.4% | — | — | no |
| mock | 90.0% | 80.1% | 77.5% | 68.3% | 0.0% | yes |
| ck | 83.3% | 75.3% | 72.8% | — | — | no |
| mem0 | 26.7% | 24.8% | 20.5% | — | — | no |

**Read:** supermemory leads raw ranking; CH is #2 on ranking and the ONLY system
that also returns a grounded, correct, abstaining answer. CH recall is a perfect 100%.
The body-overlap lever lifted CH's weakest track (researcher) ~80→86 nDCG with no regression.
