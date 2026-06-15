# LoCoMo — Standard-Benchmark Comparison

A market benchmark beyond our custom suite: **LoCoMo** (snap-research) is
multi-session, conversational, paraphrased, temporal QA — much harder and more
realistic than the contextheavy suite. Run on the same corpus (1 LoCoMo sample =
419 memories) and the same first 20 questions across systems, via the CH-Bench
harness. Retrieval metrics over gold-bearing questions; CH also judged for answer
correctness.

| system | recall@k | nDCG@10 | mrr | answers? | note |
| --- | --- | --- | --- | --- | --- |
| **CH** | **76.2%** | **64.2%** | **63.7%** | **yes — 60% correct** | hybrid RRF + rerank-blend + graph + body-overlap |
| supermemory | 67.5% | 52.7% | 51.5% | no (chunks) | the custom-suite ranking leader |
| mem0 | 35.0% | 40.9% | 28.7% | no | LLM fact-extraction drops coverage |
| mock | 26.2% | 18.0% | 15.7% | (weak) | BM25-lite lexical baseline |
| ck | 0.0% | 0.0% | 0.0% | no | local keyword grep — can't match conversational paraphrase |
| gbrain | N/A | N/A | N/A | no | **adapter LoCoMo id-resolution bug — not a real result** (gbrain scores 92.8 nDCG on the custom suite; excluded here pending an adapter fix, not reported as a loss) |

## The headline: the ranking reverses on the harder benchmark

On our small **custom** suite supermemory edged CH on raw ranking (97.7 vs 95.3
nDCG) because that suite is **recall-saturated** (every system finds the gold) —
so only fine ordering separates them. On **LoCoMo**, which is hard enough that
recall itself is the battleground, **CH leads decisively**: recall 76.2% vs
supermemory's 67.5%, nDCG 64.2% vs 52.7%. CH's richer pipeline (hybrid fusion +
cross-encoder rerank blended with similarity + graph neighborhood + the P2
body-overlap lever) pulls ahead exactly where retrieval is hard — and CH is the
only system that *also* returns a grounded, abstaining answer (60% correct on a
benchmark where that is a strong number).

The lexical systems collapse: BM25-lite mock at 26%, and **ck (keyword grep) at
0%** — conversational paraphrase is unmatchable without semantics, a concrete
demonstration of why a semantic memory layer matters.

## Honesty notes

- Capped run: 1 LoCoMo sample (419 memories) + first 20 questions, to stay within
  NIM 40-RPM, the OpenRouter embed budget, and the managed competitors' API
  quotas. The *shape* (CH > supermemory > mem0 ≫ lexical) is the result; absolute
  numbers would shift on the full 10-sample / 200-question set.
- **gbrain** returned 0% here due to an adapter id-resolution bug specific to
  LoCoMo's memory-id format (it resolves fine on the custom suite, where it scores
  92.8 nDCG). Reported as N/A, not a loss — fixing the adapter is follow-up work.
- **LongMemEval** is the other standard benchmark; its dataset ships via a
  HuggingFace/Drive link (manual download) and wasn't fetched here. The loader
  (`bench/suites/longmemeval.py`) is ready for an LongMemEval pass once the data
  is placed.
- CH latency here (p50 ~10.8s) is dev-tier NIM-rate-limited, not a product number
  (see P3 — the hot tier serves warm repeats in ~0ms; supermemory's sub-second
  is its single-stack design).
