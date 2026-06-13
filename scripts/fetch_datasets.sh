#!/usr/bin/env bash
# Fetch the standard memory benchmarks into datasets/*/data/ (gitignored).
# LongMemEval + LoCoMo are published QA-over-long-history datasets; the loaders
# in bench/suites/{longmemeval,locomo}.py read the JSON placed here.
#
#   scripts/fetch_datasets.sh [locomo|longmemeval|all]
#
# Sources (public):
#   LoCoMo:       https://github.com/snap-research/locomo  (locomo10.json)
#   LongMemEval:  https://github.com/xiaowu0162/LongMemEval (longmemeval_s.json,
#                 distributed via a HuggingFace/Drive link in their README)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WHAT="${1:-all}"

fetch() {  # name url dest
  local name="$1" url="$2" dest="$3"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ]; then echo "[$name] already present: $dest"; return 0; fi
  echo "[$name] downloading → $dest"
  if curl -fsSL "$url" -o "$dest"; then
    echo "[$name] ok ($(wc -c <"$dest") bytes)"
  else
    echo "[$name] FAILED. Download manually and place at $dest" >&2
    return 1
  fi
}

if [ "$WHAT" = "locomo" ] || [ "$WHAT" = "all" ]; then
  # LoCoMo ships the 10-sample set directly in the repo.
  fetch "locomo" \
    "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json" \
    "$ROOT/datasets/locomo/data/locomo10.json" || true
fi

if [ "$WHAT" = "longmemeval" ] || [ "$WHAT" = "all" ]; then
  # LongMemEval-S is gated behind a HF/Drive link; allow an override URL.
  url="${LONGMEMEVAL_URL:-}"
  if [ -z "$url" ]; then
    echo "[longmemeval] set LONGMEMEVAL_URL to the longmemeval_s.json link from"
    echo "             https://github.com/xiaowu0162/LongMemEval, then re-run."
  else
    fetch "longmemeval" "$url" "$ROOT/datasets/longmemeval/data/longmemeval_s.json" || true
  fi
fi

echo "done. present:"
ls -1 "$ROOT"/datasets/locomo/data/ "$ROOT"/datasets/longmemeval/data/ 2>/dev/null || true
