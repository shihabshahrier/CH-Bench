# P4 — Memory Dynamics (brain-inspired)

Map cognitive memory mechanisms to concrete CH mechanisms, validated by behavior
(not by how "brain-like" they sound). Increment shipped this pass; the rest is
scoped below.

## Cognitive → CH mapping

| mechanism (cognition) | CH mechanism | status |
| --- | --- | --- |
| reconsolidation (retrieval strengthens a trace) | bump `access_count` + `last_accessed` on the sources that grounded an answer | **shipped** (`a3e1e67`) |
| Hebbian salience ("what fires together / gets used, strengthens") | `salienceScore` = log-compressed access_count, a rerank boost | **shipped** |
| Ebbinghaus decay / forgetting | recency + salience ranking → old, never-retrieved memories *sink* (soft, non-destructive) | **shipped (soft)** |
| time-since-last-access decay (full forgetting curve) | `accessFreshness` = exp decay (30-day half-life) multiplying salience — a once-hot memory cools if not re-retrieved | **shipped** |
| spreading activation | graph edges (1-hop neighborhood in the answer context) | pre-existing |
| episodic → semantic consolidation | episodes distilled into nodes | pre-existing (manual) |
| schema | communities (GraphRAG-lite summaries) | pre-existing |
| sleep-phase (scheduled) consolidation | a periodic job running distill + community refresh | **deferred — by design** (mechanism exists + is API-triggerable; only the scheduler wiring remains, which needs a service-handle exposed from `router.New` — a deliberate small refactor, not a rushed bolt-on) |

## What shipped + why this shape

- **Reconsolidation** is async and fire-and-forget: it never blocks or fails the
  answer, and it's pooler-safe (`text[]::uuid[]`). Verified live — a node reads
  `access_count=1` + a `last_accessed` timestamp after a single Ask.
- **Salience** is log-compressed (diminishing returns) and normalized across the
  candidate set, so it lifts frequently-used memories without letting a single
  hot note dominate. **Cold-corpus no-op:** when nothing has been retrieved yet
  (`maxAccess=0`) the boost is 0 — so a fresh workspace, and the reset-between-
  runs cold benchmark, are unaffected. The win is on **warm, real traffic**,
  exactly where a memory product lives.
- **Forgetting is soft, not destructive.** Old + never-retrieved memories *sink
  in rank*; nothing is deleted. For a "best memory" product that's the correct
  default — losing data is worse than ranking it low. A hard prune/archive policy
  (with `valid_until` or an archive tier) can come later behind an explicit
  opt-in, but it is not the default behavior.

## Why this isn't a cold-benchmark number

The contextheavy suite ingests fresh nodes and resets between runs, so
`access_count` is always 0 → salience is inert there (by design). Validating the
dynamics needs a **simulated multi-month history** (repeated retrieval over a
fixed corpus, measuring whether frequently-asked facts stay near the top and
stale ones fade) — a dedicated dynamics harness, listed as future work. The
shipped pieces are covered by unit tests (salience math, bounds, cold no-op) and
a live reconsolidation check.

## Next P4 steps

1. **Time-since-last-access decay**: feed `last_accessed` (now recorded) into the
   ranking so a memory not retrieved in a long time decays even if once-hot —
   the full Ebbinghaus curve, not just frequency.
2. **Scheduled sleep-phase consolidation job**: on the existing async-job
   pattern, periodically distill episodic→semantic and refresh communities, so
   the schema layer stays current without a manual rebuild.
3. **Dynamics harness** in CH-Bench: simulate a long history and measure
   retention/forgetting curves.
