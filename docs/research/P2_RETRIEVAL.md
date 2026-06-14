# P2 — Retrieval Quality: findings (in progress)

Goal: close supermemory's ranking lead (nDCG 83.8) on the contextheavy suite.
Measured against the real CH server (Ask path, NIM llama-3.3-70b, OpenRouter
bge-m3), 44 memories / 35 questions. **Facts, not bias** — every number is a run.

## Runs

| build | recall@k | nDCG@10 | mrr | note |
| --- | --- | --- | --- | --- |
| baseline (pre-P2) | 85.7% | 81.3% | 80.0% | id-named nodes, no boosts |
| + post-fusion boosts | 85.7% | 81.6% | 80.2% | title-match + recency |
| + realistic titles (broken run) | 64.3% | 61.3% | 61.4% | **invalid** — embed worker pool dropped nodes |
| + titles + **embed-drop fix** + paced ingest | 85.7% | 81.5% | 80.6% | clean; recall fully recovered |

## What we learned (honest)

1. **The post-fusion boosts (title-match + recency) are ~flat on this suite.**
   nDCG 81.3 → 81.5, mrr 80.0 → 80.6, recall unchanged. Reason: the suite is
   **recall-saturated** (85.7% — the gold docs are almost always retrieved), so
   the bottleneck is *ordering within the top-k*, and the existing vector+FTS+
   rerank already orders most tracks well. The boosts are a real production
   lever for titled notes (and carry no regression), but this benchmark can't
   show much headroom for them. Kept, not oversold.

2. **The real, persistent gap is the `researcher` track: ~67 nDCG / ~62 mrr**
   (every run: 65.5 / 71.0 / 67.0). Recall there is fine (83.3%) — the gold doc
   is retrieved but **not ranked #1** on paraphrased single-hop queries
   ("What *fuses* full-text and vector search, with what parameter?" → the RRF
   note). Title/recency don't help this; it needs a **stronger reranker signal
   or query-aware semantic matching** (term-overlap on the *body*, hop-1 graph
   corroboration, or a better cross-encoder). **This is the next P2 lever** and
   the path to passing supermemory's 83.8 (lifting researcher to track-parity
   ~83 pulls overall to ~84).

3. **The benchmark surfaced a real CH production bug** (the most valuable P2
   outcome): with rate limiting off, a bulk ingest burst overflowed the 5-slot
   embed worker pool and **silently dropped embeddings** (non-blocking acquire +
   `EMBED_BACKFILL_ON_START=false`), making a whole track unfindable (0% recall).
   Fixed in CH `0cfcc0f`: a bounded burst buffer + blocking acquire so bursts
   *pace* through the pool instead of dropping. Recall recovered to 85.7%. In
   production this was silent note loss on any bulk import.

## Metric-artifact correction (the bigger finding)

Investigating the "researcher gap" surfaced a **benchmark bug that under-reported
every system**: the 5 abstain questions (empty gold) were scored 0 on
recall/nDCG/mrr and averaged into the ranking metrics. An abstain question has no
gold to rank, so that 0 is spurious. Fixed in the runner (`has_gold` gates
ranking aggregation; abstention is scored separately). Recomputed over all
systems' saved per-question data — fair, no re-run:

| system | recall@k | nDCG@10 | mrr | answers? |
| --- | --- | --- | --- | --- |
| supermemory | 100% | **97.7%** | 96.7% | no (chunks) |
| **ch** | 100% | **95.1%** | 94.0% | **yes — 96.7% correct, 100% abstain** |
| gbrain | 100% | 92.8% | 90.4% | no (chunks) |
| ck | 83.3% | 75.3% | 72.8% | no |
| mem0 | 26.7% | 24.8% | 20.5% | no |

Honest read: **supermemory still leads raw ranking by ~2.6 nDCG points** (97.7 vs
95.1) — the gap is real, not an artifact. But CH is the only system that ranks
near-top AND returns a grounded, correct, abstaining *answer*; the others return
chunks. CH's recall is a perfect 100% (every gold doc retrieved). The remaining
ranking gap to supermemory is almost entirely the **researcher track** (corrected
80.4 nDCG vs ~95+ elsewhere) — two paraphrased questions where the gold is
retrieved but ranked #2/#5. Closing that is the live P2 lever; it needs
query-aware body-term ranking, not more title/recency weight.

## Methodology notes / honesty

- The adapter previously named nodes by bare id, blinding any title signal; it
  now derives a realistic title (CH-Bench `2d805e4`), so the title lever is at
  least *exercisable* — it just has little headroom on a recall-saturated suite.
- Latencies here (p50 ~13s, p95 ~63s) are **dev-environment NIM-rate-limited**,
  not a product number — that's P3's measurement, not this one.
- Next P2 step: query-aware ranking for the researcher-style paraphrase gap
  (body term-overlap + hop-1 graph corroboration), then re-measure vs 83.8.
