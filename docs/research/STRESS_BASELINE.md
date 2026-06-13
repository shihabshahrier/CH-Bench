# Stress / Scale Baseline — pgvector + HNSW (Phase 0)

What CH's retrieval engine (pgvector 0.8 HNSW, 1024-dim) does at scale, measured
with `Context-Heavy/api/cmd/stress` against the **dev DB (free Neon, 0.5 GB RAM)**.
Synthetic random vectors generated server-side (no embedding API → no cost), into
a throwaway `UNLOGGED` table, dropped after. **Production is RDS** — these numbers
flag where dev-tier limits bite and how to size prod.

Run: `go run ./cmd/stress --n <N> --maint-mem <M> --queries 200 --concurrency 16`.

## Headline findings

1. **HNSW build is memory-bound — this is the dominant scale constraint.** The
   graph must fit `maintenance_work_mem`; past that, pgvector falls back to a slow
   multi-pass build (it emits `NOTICE: hnsw graph no longer fits into
   maintenance_work_mem after N tuples`). On free Neon (64 MB default) that trips at
   **~14K rows**. Build time swings hugely with memory:

   | N | maintenance_work_mem | build time |
   | --- | --- | --- |
   | 20K | 256 MB | 67 s |
   | 100K | 64 MB (default) | 96 s (degraded multi-pass) |
   | 100K | 2 GB | **15 s** |
   | 100K | 256 MB (on 0.5 GB Neon) | **did not complete** (>8 min / memory pressure) |

   → **The free Neon tier has only 0.5 GB total RAM, so a build can't realistically get
   more than ~256–400 MB — and a 100K × 1024-dim HNSW build does NOT complete on it.**
   The practical dev ceiling is ~tens-of-thousands of chunks; **scale needs production RDS
   with RAM ≥ the graph and `maintenance_work_mem` in the multi-GB range for builds.** This
   is a hard pre-deploy sizing requirement, not a tuning nicety.

2. **The query engine is fast — sub-millisecond.** `EXPLAIN (ANALYZE)` on the exact
   retrieval query (`ORDER BY embedding <=> $1 LIMIT 10`) shows **Index Scan, ~0.47 ms
   server-side execution** at 20K–50K. HNSW is doing its job.

3. **The 190–310 ms "latency" the harness prints is NETWORK RTT to remote Neon, not
   the engine.** Querying a cloud DB from a laptop pays ~190 ms round-trip per query
   (psql wall `Time: 193ms` vs `Execution Time: 0.47ms`). Co-located prod (app + RDS in
   one VPC) sees ~sub-ms. **Treat the harness's wall-latency + qps as dev-network-bound,
   not a product latency number** — the real budget work (P3) measures the CH Ask path
   end-to-end (8.3 s), which is LLM + embed + rerank, not the vector query.

4. **recall@10 = 1.000** at 20K with an adequately-sized build (exact self-retrieval:
   does HNSW return a row for its own vector). Recall is healthy when the graph fits
   memory. recall@100K could not be measured on the dev tier (build didn't complete) —
   defer the at-scale recall figure to an RDS-class run.

5. **Ingest throughput (server-side vector generation): ~2.7K–6.7K rows/s**, batch- and
   compute-bound on the 0.5 GB tier. This is *synthetic* load; real ingest goes through
   CH's embed pipeline and is **provider-bound** (NIM 40 RPM, or OpenRouter) — a separate,
   much tighter limit measured elsewhere.

## What this means for the roadmap

- **P3 (efficiency):** the vector query is not the bottleneck — the Ask latency (8.3 s)
  is LLM + embed + rerank. Budget work targets those, plus a hot working-memory tier to
  skip retrieval entirely for warm context.
- **Production sizing:** RDS instance RAM must hold the HNSW graph for the workspace's
  chunk count (1024-dim, m=16 ≈ a few KB/row of graph) **plus** headroom; set
  `maintenance_work_mem` to multiple GB for (re)builds. Budget this before deploy.
- **Large corpora on small RAM:** options to fit more in memory — `halfvec` (halve vector
  bytes), lower `m`, or IVFFlat for very large sets; or build with temporary high RAM then
  serve. Test in a later scale pass on RDS-class hardware.

## Caveats (honesty)

- Random uniform vectors are a *worst case* for ANN navigation and lack the cluster
  structure real bge-m3 embeddings have — recall on real embeddings is typically higher
  than on random data at the same scale. This baseline measures **build cost + engine
  mechanics + memory limits**, not semantic recall (that's the CH-Bench suites).
- A genuine bug was caught and fixed mid-run: the server-side generator's `LATERAL` was
  uncorrelated → the planner produced **one identical vector for every row** (`distinct=1`).
  Correlating it (`generate_series(1, dim + 0*g)`) restores per-row randomness
  (`distinct=N`). Recall numbers before the fix are void.
- Measured on remote Neon from a laptop; absolute latency/qps are network-bound. Re-run on
  RDS in-VPC for production latency figures.
