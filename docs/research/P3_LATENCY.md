# P3 — Latency: budget breakdown + hot tier

Measure before optimize. Per-stage timers were added to the Ask path
(`timings_ms` in the response + a log line), then exercised live against the
real server (NIM `meta/llama-3.3-70b-instruct`, OpenRouter `bge-m3`).

## The budget (live, ms)

| stage | run A | run B | run C | run D | share |
| --- | --- | --- | --- | --- | --- |
| embed | 3156 | 1307 | 2106 | 3127 | ~1-3s (provider, variable) |
| retrieve | 442 | 487 | 259 | 247 | **sub-second** |
| rerank | 653 | 259 | 287 | 449 | **sub-second** |
| graph | 73 | 61 | 61 | 60 | **~60ms** |
| **llm** | **45813** | **19697** | **56086** | **18403** | **~90% of total** |
| total | 50137 | 21811 | 58799 | 22286 | |

**Headline: CH's own retrieval engine — retrieve + rerank + graph — is
sub-second (~0.5-1s combined). The latency is almost entirely the LLM synthesis
call** (and, secondarily, the embed call). The frequently-quoted "8.3s" (and the
20-56s seen here under a rate-limited free NIM tier) is the **chat provider**,
not CH's algorithm. This reframes P3: there is no slow CH code path to optimize —
the levers are all around the LLM call.

## Levers (in impact order)

1. **Answer-cache hot tier (shipped, CH `1ed02d8`).** A warm exact-query repeat
   skips the entire pipeline — embed + retrieve + rerank + graph + the dominant
   LLM call — and returns the cached answer. **Measured: cold 22.3s → warm ~0ms.**
   Keyed by (workspace, mode, persona, top_k, normalized query, **actor**), so
   personal-scoped answers never leak across users. Short TTL (60s) bounds
   staleness after note edits; write-time invalidation is the next refinement.
   This is the plan's "hot working-memory tier" — the biggest cut for warm/
   repeated/polling traffic (an agent re-asking, a dashboard refreshing).
2. **Faster chat provider / model** (infra, not code): the LLM is the floor.
   A co-located, higher-throughput endpoint (or a smaller distilled model for
   simple asks) is the only thing that moves the *cold* number. The provider-
   pluggable pipeline already supports swapping it.
3. **Embedding cache (shipped, CH `13a9b36`).** Query-text→vector cache in the
   EmbeddingService — deterministic per (model, input_type, text), so no
   staleness and a long TTL (6h). Shaves the embed leg on any repeat that misses
   the answer cache (e.g. same query, different top_k), and benefits every
   single-text caller (Ask, semantic, who-knows, create-safety). **Measured:
   same query / different top_k → embed 5771ms → 54ms (~100x).**
4. **Streaming** improves time-to-first-token (UX) but not total latency; orthogonal.

## Honesty notes

- Absolute numbers here are **dev-tier, NIM-rate-limited** — the cold LLM swing
  (18s vs 56s) is queue/throttle noise, not CH. A co-located prod endpoint is far
  faster; the *shape* (LLM ≫ everything else) is what matters and is stable.
- The cache win is shown by a manual warm repeat; the contextheavy suite can't
  measure it (every question is unique and `reset()` wipes between runs), which
  is correct — the cache targets real warm traffic, not a cold-start benchmark.
- recall/ranking are unaffected (cache returns the exact prior answer+sources).
