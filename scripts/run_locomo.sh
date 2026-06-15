#!/usr/bin/env bash
# Sequential LoCoMo sweep — one system at a time so the slow/network-bound
# adapters don't starve each other (running all six at once made even the
# in-memory mock crawl). LOCOMO_SAMPLES bounds the corpus to N conversations
# (each scored in isolation); pass it as $1 (default 2).
#
#   scripts/run_locomo.sh 3
set -uo pipefail
cd "$(dirname "$0")/.."

SAMPLES="${1:-2}"
export LOCOMO_SAMPLES="$SAMPLES"
NOTE="s${SAMPLES}"
K=10

run() { echo "########## $1 (samples=$SAMPLES) ##########"; shift; "$@"; }

# Local / fast first.
run mock        python3 -m bench.cli run --system mock        --suite locomo --k $K --no-judge --note "$NOTE" --out results/
run ck          python3 -m bench.cli run --system ck          --suite locomo --k $K --no-judge --note "$NOTE" --out results/
run gbrain      python3 -m bench.cli run --system gbrain      --suite locomo --k $K --no-judge --note "$NOTE" --out results/

# CH: retrieval-only (full rerank+graph ranking, no LLM) + neutral titles.
# Pace ingest to roughly the OpenRouter bge-m3 embed throughput so queries
# don't race async indexing.
run ch  env CH_RETRIEVAL_ONLY=1 CH_DERIVE_TITLE=0 CH_INGEST_DELAY=1.0 CH_QUERY_DELAY=0 \
        python3 -m bench.cli run --system ch --suite locomo --k $K --no-judge --note "$NOTE" --out results/

# Paid competitors last (rate-limited; the adapters now retry w/ backoff).
run supermemory python3 -m bench.cli run --system supermemory --suite locomo --k $K --no-judge --note "$NOTE" --out results/
run mem0        python3 -m bench.cli run --system mem0        --suite locomo --k $K --no-judge --note "$NOTE" --out results/

echo "ALL_LOCOMO_DONE samples=$SAMPLES"
python3 scripts/export_table.py
