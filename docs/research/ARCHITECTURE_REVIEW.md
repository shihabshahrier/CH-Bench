# Architecture Review — CH vs the field

Phase-0 baseline for the "best co-work memory" program. Per-system architecture,
decisions, and trade-offs. **Evidence tags:** `[src]` = read from source,
`[docs]` = vendor docs/blog, `[eval]` = our P16.5 benchmark, `[inf]` = inference
(stated, not confirmed). No claim is asserted as fact without a tag.

Systems: **Context-Heavy (CH)**, **GBrain** (open source, `~/github/gbrain`),
**Supermemory**, **Mem0**, **Zep**, **Letta**. gbrain is the deepest read (full
source); the managed ones are docs + behavioral probing.

---

## Context-Heavy

- **Storage** `[src]`: PostgreSQL 16 + pgvector 0.8 (Neon). Nodes + typed edges +
  `node_chunks` (1200B/200-overlap chunks). `embedding vector(1024)` with **HNSW**
  (m=16, ef_construction=200, cosine) after migration 014. Redis (Upstash) for
  rate-limit; not yet a retrieval cache.
- **Retrieval** `[src]`: chunk-grain → 2-best-chunks-per-node max-pool
  (`chunk_retrieval.go`) → **RRF k=60** hybrid fusing pgvector + GIN tsvector FTS
  (`hybrid_repo.go`) → over-fetch 3×top_k → **cross-encoder rerank blended with
  similarity rank** (`RERANK_BLEND=0.5`, P16.5) → graph 1-hop neighborhood appended
  to the **answer context** (not the ranking) → LLM synthesis with abstention.
- **Ranking signals** `[src]`: vector + FTS (RRF) + one reranker, blended. **No**
  query-aware graph boost, title/alias boost, source-tier boost, recency, or
  salience. Graph helps answers, not ordering. → the main quality gap `[eval]`.
- **Graph / temporal** `[src]`: self-wiring edges from `[[wikilinks]]` + name
  mentions; communities (GraphRAG-lite summaries) for global mode; **versioning +
  `as-of` + `valid_until` + supersession** — a real temporal model most rivals lack.
- **Decay / consolidation** `[src]`: episodes (raw captures) distilled async into
  nodes; communities rebuilt on demand. **No decay/forgetting, no scheduled
  (sleep-phase) consolidation, no salience/recency weighting.**
- **Multi-tenant / security** `[src]`: DualAuth (API-key `cg_` prefix → key; else
  JWT), `workspace_id` scoping, `RequireScope(read/write/admin)`, OAuth 2.1+PKCE
  front door for hosted MCP. (Isolation completeness = Phase-0 security audit.)
- **Pipeline** `[src]`: provider-pluggable embed/chat/rerank by base-URL→key pairing;
  per-service failover chain (P16.5). MCP (SSE) + REST; webhooks; profiles (personas).
- **Latency** `[eval]`: **~8.3s p50** end-to-end Ask (embed + rerank + graph + LLM).
  The weak point. Retrieval-only (`/v1/semantic`) is far faster but unmeasured at p95.
- **Differentiator** `[eval]`: only system that returns a **grounded, cited,
  abstaining answer** (100% correctness/abstention) + a human UI + temporal truth.

## GBrain `[src]` (the architectural reference)

- **Storage**: pluggable engines — **PGLite** (embedded, 2-s local start) →
  Postgres+pgvector for scale; HNSW; typed page "kinds" (people/companies/concepts)
  via authorable schemas.
- **Retrieval** (`src/core/search/`): hybrid (`hybrid.ts`) with a **query-embed
  deadline** (6s, floor 2s) that falls back to keyword if the provider stalls;
  two-stage CTE (`sql-ranking.ts`, HNSW-safe inner ORDER BY → boost re-rank in outer
  SELECT); **multi-query expansion**; reranker (ZeroEntropy zerank-2, or local
  llama.cpp).
- **Ranking signals** — the depth CH lacks: a **post-fusion boost pipeline**
  (`runPostFusionStages`) of **backlink → salience → recency → graph-signals**, plus
  **source-tier boost** (`source-boost.ts`, prefix-keyed), **title-phrase boost**
  (`title-match.ts`, 1.25×), **alias boost** (`alias-normalize.ts`, one normalizer
  shared write+read). `base_score` stamped once; every stage stamps its own
  attribution field → `gbrain search --explain` shows per-stage contribution.
- **Cost/quality modes** (`mode.ts`): `conservative | balanced | tokenmax` bundle
  knobs (graph_signals, title_boost) and version the cache key so a graph-on write
  can't be served to a graph-off read.
- **Evidence contract** (`evidence.ts`): names the strongest matching signal
  (`alias_hit > exact_title_match > high_vector_match …`) + create-safety — closes
  the failure where an agent reads one blended score, thinks "no match, safe to
  create," and **writes a duplicate over a developed page**.
- **Code intel**: tree-sitter chunkers (`chunkers/code.ts`), symbol resolver,
  def/refs/callers/callees with a readiness signal.
- **Salience/temporal**: `emotional_weight` per (page, source), `getRecentSalience`,
  `findAnomalies`; effective-date filters (`--since/--until`).
- **Dynamics**: stale-embedding detection on model/dim drift; post-upgrade re-embed
  cost estimate; Minions job queue (cron/background) — consolidation infra CH lacks.
- **Co-work**: **source-scoping** (`sourceScopeOpts`) — a source-bound OAuth client
  can't see neighboring sources via search/query/list; `whoknows`/`find-experts`
  (who-knows-what); contract-first ops with `scope` + `localOnly` and **fail-closed**
  trust-boundary checks (they fixed an MCP shell-job RCE where a read+write token
  could submit `shell` jobs). **Directly relevant to CH P1 co-work + the security audit.**
- **Trade-off** `[inf]`: very mature + many knobs = heavier, more surface; agent-only
  (no human UI); no synthesized grounded answer in the same product sense.

## Supermemory `[docs]`

- 5-layer: connectors (Slack/Notion/Gmail auto-sync) → extractors (multimodal chunk)
  → **Super-RAG** (hybrid + context-aware rerank, one query) → **memory graph**
  (relationship + conflict resolution + temporal ordering) → user profiles (static
  prefs + live session).
- **Brain-inspired**: hot **Cloudflare-KV tier = working memory**; **intelligent
  decay** (less-accessed fades, frequent stays sharp); reconsolidation via summary
  rewrite; recency bias. **Sub-300–400ms** single-stack (no network hops), "custom
  graph engine skips full index scans" `[docs/inf]`.
- **Gap for us** `[eval]`: best raw ranking we measured (nDCG 83.8) + fastest; but
  returns chunks, not answers; closed; decay/graph params undisclosed.

## Mem0 `[docs][eval]`
- Cloud API; **LLM-extracts facts** from messages → vector store (graph add-on).
  Strength: conversational consolidation. **Weakness** `[eval]`: extraction drops
  standalone memories → 22.9% recall on our hard suite. Data-sovereignty/offline gaps `[docs]`.

## Zep `[docs]`
- **Temporal knowledge graph** (Graphiti); retrieval = graph temporal reasoning +
  semantic. Closest to CH's temporal story. Trade-off: graph traversal **50–150ms**
  vs ~10–50ms vector-only `[docs]`.

## Letta (MemGPT) `[docs]`
- **OS-inspired tiers** — core context / recall / archival; the **LLM self-manages**
  what's promoted/evicted. Inspiration for CH's **token-budget 3-tier context** (P3).
  Risk `[docs]`: agent reasoning errors can corrupt memory; requires Letta runtime.

---

## Comparative matrix

| axis | CH | GBrain | Supermemory | Mem0 | Zep | Letta |
| --- | --- | --- | --- | --- | --- | --- |
| store | PG+pgvector/HNSW | PGLite→PG | proprietary+KV | cloud vector | KG (Graphiti) | tiered |
| hybrid+rerank | ✓ (blended) | ✓ (multi-stage) | ✓ | partial | semantic+graph | LLM-driven |
| query-aware graph rank | ✗ | **✓** | ✓ (graph) | graph add-on | ✓ | ✗ |
| title/alias/source boost | ✗ | **✓** | partial | ✗ | ✗ | ✗ |
| evidence / create-safety | ✗ | **✓** | ✗ | ✗ | ✗ | ✗ |
| decay / consolidation jobs | ✗ | ✓ | **✓** | partial | ✓ | ✓ (tiers) |
| working-memory hot tier | ✗ | ✗ | **✓** | ✗ | ✗ | ✓ (core) |
| temporal / as-of | **✓** | partial | ✓ | ✗ | **✓** | ✗ |
| grounded answer + abstain | **✓** | partial | ✗ | ✗ | ✗ | ✓ |
| co-work scoping / who-knows | partial | **✓** | profiles | ✗ | ✗ | ✗ |
| human UI | **✓** | ✗ | ✓ | ✓ | ✓ | partial |
| latency p50 | 8.3s `[eval]` | 3.0s `[eval]` | 1.2s `[eval]` | 1.2s | ~graph | varies |

## Takeaways for CH (feed the build phases)

1. **Borrow gbrain's post-fusion boost pipeline** — backlink/salience/recency/graph +
   source/title/alias boosts with per-stage attribution. Biggest ranking lever (P2),
   and `--explain`-style attribution is cheap + high-trust.
2. **Adopt an evidence + create-safety contract** (P1) — prevents duplicate memories;
   gbrain proves the failure mode is real.
3. **Working-memory hot tier + decay** (P3/P4) — supermemory's brain mapping; we have
   Redis idle and the async-job pattern ready.
4. **Source-scoping + who-knows-what + fail-closed trust boundary** (P1 + security) —
   gbrain's source-scope ladder and the MCP shell-job RCE are a direct checklist for
   CH's hosted MCP/OAuth.
5. **Keep CH's edge**: grounded answering + abstention + temporal/as-of + human UI —
   nobody else has all four. Co-work is the unclaimed space.
