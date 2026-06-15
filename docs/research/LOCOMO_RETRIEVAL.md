# LoCoMo — retrieval-quality comparison (Context-Heavy vs the field)

## Context

Every memory system on the market publishes LoCoMo numbers as **answer
accuracy** (LLM-judge "J score" / F1 — mem0, MemOS, TiMem, Eywa, …). That
measures the *tongue*: a system's retrieval **plus** whatever LLM it bolts on
top. It says nothing about retrieval quality in isolation, and it can't be
re-run without an LLM + a judge.

This run measures the thing underneath: **pure retrieval quality** — given the
same conversations and the same questions, which system surfaces the right
memories? recall@k / nDCG / MRR, no LLM anywhere. It's the axis the field
doesn't publish, and the one that actually isolates the memory engine.

## Method (identical across all systems)

- **Dataset:** the public `locomo10.json` (snap-research/LoCoMo), 2 conversations,
  **304 questions**, **788 memories**.
- **Per-conversation isolation:** each conversation is its own corpus — a
  system is reset, ingested with only that conversation's turns, then asked only
  that conversation's questions. This is the standard LoCoMo protocol (not one
  giant pooled haystack), enforced by the harness's grouped-run mode.
- **Retrieval-only:** every system returns ranked memories, **no generated
  answer**. For CH this uses the new `retrieve_only` path — the full
  hybrid+rerank+graph ranking pipeline with the LLM call skipped.
- **k = 10.** Metrics scored only over questions that carry gold evidence ids.

### Fairness controls (so the result has no asterisks)

- **Neutral titles for CH** (`CH_DERIVE_TITLE=0`): CH nodes are named by id only,
  with no derived title. CH's title-overlap ranker therefore gets **no
  bench-handed signal** competitors lack — the win is the engine, not the
  harness. (Body text is real for every system, so the body signal is fair.)
- **gbrain id-resolution fixed:** gbrain slugifies keys (lowercases, strips
  colons), so LoCoMo ids like `0:D1:2` became `0d12` and never mapped back —
  scoring a bogus 0%. Ids are now pre-normalized to a slug-stable form. gbrain
  went 0% → 58% — a real competitor number.
- **Same embedder where it's the variable:** CH and gbrain both embed with
  bge-m3; supermemory/mem0 run their own shipped stacks (this is a
  product-vs-product comparison, each system as it ships).

## Results

_2 conversations / 304 questions · per-conversation isolated · retrieval-only · neutral titles · k=10_

| system | recall@k | nDCG@10 | MRR | hit@k | p50 |
| --- | --- | --- | --- | --- | --- |
| **Context-Heavy** | **71.2%** | **60.1%** | **58.5%** | **76.2%** | 1708ms |
| supermemory | 63.3% | 45.4% | 41.0% | 67.5% | 713ms |
| gbrain | 58.0% | 38.2% | 33.5% | 61.6% | 3071ms |
| mock (BM25) | 35.3% | 20.5% | 16.8% | 37.7% | 0ms |
| mem0 | 20.6% | 17.4% | 14.6% | 22.5% | 1184ms |
| ck (grep) | 0.0% | 0.0% | 0.0% | 0.0% | 120ms |

**Context-Heavy is #1 on every retrieval metric** — recall, nDCG, MRR, hit —
in its *least* favorable configuration (no title signal, no LLM):

- vs supermemory: **+7.9 recall / +14.7 nDCG**
- vs gbrain: **+13.2 recall / +21.9 nDCG**

The honest trade-off is latency: CH p50 1.7s vs supermemory 0.7s. CH's remote
cross-encoder rerank is ~1s of that — it's the lever that buys the ranking lead.
ck (pure keyword grep) can't match conversational paraphrase at all.

## Caveats (stated, not buried)

- **Scale:** 2 conversations / 304 questions. Full LoCoMo is 10 conversations /
  ~1,986 questions; this is a bounded, per-conversation-isolated slice. Trend is
  consistent with the earlier 1-conversation run (CH led there too), but a
  full-10 pass would harden it.
- **supermemory / mem0 = free-tier, best-effort.** They rate-limit (HTTP 429);
  the adapters now retry with backoff. Their numbers are reproducible only with
  working API access; CH / gbrain / mock / ck are fully local + free.
- **This is retrieval, not the published metric.** It is **not** comparable to
  mem0's ~66% or TiMem's 75% — those are answer-J scores (a different axis). To
  sit on that leaderboard, CH needs an answer-J run too (Ask + LLM-judge).

## Reproduce

```bash
# CH server must expose /v1/graph/ask with retrieve_only; start it, then:
LOCOMO_SAMPLES=2 scripts/run_locomo.sh 2      # all six systems, sequential
python3 scripts/export_table.py --note s2     # -> results/comparison.csv + COMPARISON.md
```
