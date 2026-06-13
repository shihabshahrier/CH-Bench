# Competitive Analysis — Context-Heavy vs the field

Where Context-Heavy (CH) and common-knowledge (ck) stand against the memory
systems we benchmark, what they lead on, and where they lag. Grounded in the
P16.5 eval (`docs/P16_RESULTS.md`) and a read of GBrain's source
(`~/github/gbrain`), which is the closest architectural competitor.

## The field

| system | what it is | shape |
| --- | --- | --- |
| **Context-Heavy** | cloud-first knowledge-graph brain (Go/Postgres/pgvector), chunk embeddings + RRF hybrid + rerank + graph, Ask + MCP + OAuth | end-to-end (retrieves **and** answers) |
| **common-knowledge** | local-first, git-backed agent-memory skill; markdown store, grep search; bridges into CH | retrieval (lexical) |
| **GBrain** | local markdown → self-wiring graph (PGLite/pgvector), hybrid search w/ query-aware graph signals, reranker, query expansion | retrieval (+ query synthesis) |
| **Mem0** | managed memory API; LLM-extracts facts from messages | retrieval |
| **Supermemory** | managed memory API; chunk + rerank, async index | retrieval |
| **Zep** | managed temporal knowledge-graph memory | retrieval |

## Where CH leads (keep + press the advantage)

- **End-to-end grounded answering** — eval-proven: 96.9% answer correctness,
  100% abstention, 0% hallucinated answers. Every competitor we tested returns
  *memories*, not an answer; CH is the only one that synthesizes a cited answer
  and honestly says "what the brain doesn't know." This is the product moat.
- **Temporal truth** — versioning, `as-of`, `valid_until`, supersession. Zep is
  the only competitor with a temporal story; GBrain/Mem0/Supermemory don't model
  "what was true then vs now." CH does, and the custom suite tests it.
- **Context profiles (personas)** — "one brain, many faces" per project/agent.
  GBrain's "lens packs" are *extraction schemas*, not behavioral personas — this
  space is unclaimed.
- **Learning loop** (typed lessons + contradiction detection), **human UI**
  (GBrain is agent-only), and **MCP + OAuth** multi-tenant access.

## Where CH lags / what CH is missing (GBrain-grounded)

Prioritized — top items are the highest-leverage:

1. **Query-aware ranking signals.** GBrain boosts a result when it's a hub *for
   that query* (adjacency), corroborated across sources (cross-source), or
   demotes weak chunks from a chatty session (session-demote); plus salience
   (emotional_weight + take_count) and recency (per-prefix age decay) as
   orthogonal, auto-detected axes, and title/alias boosts. **CH's graph only
   feeds answer *context*, not retrieval *ranking*.** The P16.5 rerank-blend fix
   closed most of the raw ranking gap (nDCG 62→77), but query-aware graph boosts
   are the next ceiling. → **highest priority.**
2. **Query expansion at hop-1.** GBrain multi-query-expands every search; CH only
   expands in `deep` mode (second pass). Hop-1 expansion would lift recall on
   paraphrased questions (where lexical overlap is low).
3. **Reranker quality.** CH uses `rerank-qa-mistral-4b`; GBrain uses ZeroEntropy.
   The blend fix de-risked a weak reranker, but a stronger cross-encoder (or a
   blend tuned per query type) is worth an A/B.
4. **Agent ergonomics on results.** GBrain tags each result with *why it matched*
   (evidence) and a *create_safety* hint (exists / probable / unknown) so an
   agent avoids creating a duplicate. CH returns neither — agents guess from a
   raw score. Cheap to add, high agent value.
5. **Search-mode cost presets.** GBrain bundles cost/quality knobs into
   `conservative | balanced | tokenmax`. CH has fast/deep/global (capability
   modes) but no single *cost-tuned* retrieval preset — relevant to the
   efficiency thesis.
6. **Code-aware retrieval.** GBrain does tree-sitter symbol chunking +
   `--near-symbol` / `--lang` / structural code-edge walks. CH chunks generically
   — a gap for the developer audience.
7. **Retrieval self-health.** GBrain `doctor` checks embeddings, graph coverage,
   dim drift, RLS. CH `/health` only checks Postgres + Redis — no retrieval-
   quality self-check (e.g. unembedded-node ratio, orphan ratio).

## Where common-knowledge lags

- **No standalone semantic retrieval.** ck search is `grep -F` over the markdown
  store — lexical only. It scored 78.9% recall on the (lexically easy) custom
  suite but will collapse on paraphrase / semantic queries. It has **no
  relevance ranking** beyond grep order and **no abstention**. It leans on the CH
  bridge for anything semantic.
- **Missing:** a local embedder + vector index (the bridge already proves CH's
  embeddings work on ck content — a local `bge-m3` via Ollama would give ck
  offline semantic recall) and a relevance-ranked result set. These are ck
  roadmap items, not CH code.

## Competitor notes from the eval

- **Mem0** — 47% recall: its LLM fact-extraction drops/merges roughly half of
  standalone memories. Strong at conversational consolidation, weak at verbatim
  document recall. (A v2/graph-retrieval mode is worth testing before final.)
- **Supermemory** — best raw retrieval ranking in the field (nDCG ~81); async
  indexing (poll-until-ready); closed/managed.
- **mock (BM25-lite)** ties the leaders on the *easy* custom suite — a signal
  that suite needs harder paraphrase/multi-hop items (tracked in P16.5 §E) before
  recall@10 can discriminate.

## Fix-next list (feeds the roadmap)

1. Query-aware graph ranking boosts (adjacency / cross-source / recency) — wire
   the graph into *retrieval ordering*, not just answer context. (CH)
2. Hop-1 query expansion. (CH)
3. Evidence + create_safety hints on every retrieved source. (CH)
4. Retrieval-quality `doctor` checks. (CH)
5. Local embedder + ranked search for offline ck. (common-knowledge)
6. Stronger / query-type-aware reranker; cost-preset retrieval modes. (CH)
