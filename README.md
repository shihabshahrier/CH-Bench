# CH-Bench

A memory/RAG benchmark for AI **brains** — the systems that store knowledge for
people and agents and recall it later. It scores any brain on the same eval set
so you get apples-to-apples numbers, and it ships a custom **profession-based**
suite built around how people actually accumulate and recall knowledge over
months (cross-project recall, "why did we decide X", temporal updates,
abstention) — the parts standard benchmarks miss.

Built to settle [Context-Heavy](https://github.com/shihabshahrier/Context-Heavy)
against GBrain / Mem0 / Zep / Supermemory, but the harness is system-agnostic:
write a 4-method adapter and the same suites score your system too.

- **Zero runtime dependencies** — pure Python stdlib, runs in CI and offline.
- **Pluggable systems and suites** — small registries, easy to extend.
- **Retrieval *and* answer quality** — recall@k / MRR / nDCG plus an
  LLM-as-judge for correctness, groundedness, and abstention.
- **Efficiency is scored** — every run reports latency p50/p95 and token cost,
  not accuracy alone.

## Install

```bash
cd CH-Bench
pip install -e .          # or: PYTHONPATH=. python3 -m bench.cli ...
```

Python ≥ 3.11. No third-party packages required to run the harness or the
`mock`/`ch`/`gbrain` adapters.

## Quickstart

```bash
# What's available
bench list

# Reference run — deterministic mock brain on the custom suite, no network
bench run --system mock --suite contextheavy --k 5 --no-judge

# Score the real Context-Heavy API (uses a DEDICATED benchmark workspace key!)
export CH_BASE_URL=http://localhost:8080
export CH_API_KEY=cg_live_xxx_benchmark_workspace
bench run --system ch --suite contextheavy --out results/

# Turn on answer-quality scoring (correctness / abstention) with an LLM judge
export JUDGE_BASE_URL=https://integrate.api.nvidia.com/v1
export JUDGE_MODEL=qwen/qwen3.5-397b-a17b
export JUDGE_API_KEY=nvapi-xxx
bench run --system ch --suite contextheavy --out results/
```

Each run writes `results/{system}__{suite}__{timestamp}.json` (machine) and
`.md` (human scorecard with overall + per-track tables).

## Suites

| suite | what it tests | data |
| --- | --- | --- |
| `contextheavy` | **custom** profession tracks: cross-project recall, causal "why", temporal update/supersession, abstention | bundled in `datasets/contextheavy/*.json` |
| `longmemeval` | long-term conversational memory across sessions | download → `datasets/longmemeval/data/` |
| `locomo` | long multi-session dialogue QA | download → `datasets/locomo/data/` |

The custom suite is one JSON file per profession track:

```json
{
  "track": "developer",
  "memories":  [{"id": "dev-001", "text": "...", "metadata": {"timestamp": "2026-01-05"}}],
  "questions": [{"id": "dev-q1", "question": "...", "answer": "...",
                 "relevant_ids": ["dev-001"], "expect_abstain": false,
                 "metadata": {"type": "causal"}}]
}
```

`relevant_ids` drive recall@k / MRR / nDCG; `answer` drives the judge;
`expect_abstain: true` marks questions whose correct behavior is "the brain
doesn't know". Add a track by dropping a new file in the folder.

## Systems (adapters)

| system | notes |
| --- | --- |
| `mock` | deterministic BM25-lite, in-memory — the CI reference, no quota |
| `ch` | Context-Heavy REST: `POST /v1/nodes` ingest, `POST /v1/graph/ask` answer, `GET /v1/semantic` retrieval-only (`CH_RETRIEVAL_ONLY=1`) |
| `gbrain` | shells out to `GBRAIN_INGEST_CMD` / `GBRAIN_QUERY_CMD`; dry-run with no config |

Write a new adapter by implementing four methods — `reset`, `ingest`, `query`,
`close` (see [`bench/core/adapter.py`](bench/core/adapter.py)) — and registering
it in [`bench/adapters/__init__.py`](bench/adapters/__init__.py).

### ch adapter safety

The `ch` adapter **writes nodes and deletes them on reset**. Always point it at
a dedicated benchmark workspace API key — never your live brain. It namespaces
every node (`bench-{run}-{id}`, `properties.bench=true`) so retrieved sources
resolve back to suite ids and cleanup only touches what the run created. Under a
rate-limited embedding provider (e.g. NVIDIA NIM free tier, 40 RPM, which embeds
on write) set `CH_INGEST_DELAY=1.6`.

## Metrics

- **Retrieval:** `recall@k`, `precision@k`, `hit@k`, `MRR`, `nDCG@10` over the
  ranked sources, resolved to suite ids.
- **Answer (judge on):** `correctness` (1 / 0.5 / 0), `abstention_accuracy`
  (declined when it should), `false_abstention` (bailed when it shouldn't).
- **Efficiency:** `latency_ms_p50/p95`, `tokens_mean`.

The judge is a fixed OpenAI-compatible model + rubric (config via `JUDGE_*`
env). Disabled cleanly when no key is set — the run then scores retrieval only.

## Layout

```
bench/
  core/      types, Adapter/Suite contracts, runner, judge
  adapters/  mock, ch, gbrain  (+ registry)
  suites/    contextheavy, longmemeval, locomo  (+ registry)
  metrics/   recall@k, precision, hit, MRR, nDCG
  report.py  JSON + Markdown scorecards
  cli.py     `bench run` / `bench list`
datasets/    bundled custom tracks; download slots for standard suites
results/     scorecards (git-ignored; commit deliberately)
tests/       end-to-end smoke (mock × contextheavy, judge off)
```

## Roadmap

- **P15 (this repo):** harness + custom suite + standard-suite loaders + CH /
  gbrain / mock adapters. ✅
- **P16:** real comparison runs (CH vs GBrain/Mem0/Zep/Supermemory on
  LongMemEval + LoCoMo + ContextHeavy-Bench), a published scorecard table, and a
  tuning loop (rerank depth, chunk size, embedder A/B, `ef_search`).

## License

MIT.
