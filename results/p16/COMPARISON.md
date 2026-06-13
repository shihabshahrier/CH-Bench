# CH-Bench comparison — `contextheavy` suite

6 systems · 19 questions · k=10 · LLM-judge: qwen3.5-397b (NVIDIA NIM)

| system | recall@k | nDCG@10 | MRR | hit@k | answer correctness | abstention | latency p50 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **ch** | 84.2% | 62.0% | 54.3% | 84.2% | 96.9% | 100.0% | 5447ms |
| **gbrain** | 84.2% | 77.1% | 74.3% | 84.2% | — | — | 1588ms |
| **mock** | 84.2% | 77.8% | 75.9% | 84.2% | 84.4% | 0.0% | 0ms |
| **supermemory** | 84.2% | 80.7% | 78.9% | 84.2% | — | — | 1071ms |
| **ck** | 78.9% | 75.0% | 73.7% | 78.9% | — | — | 45ms |
| **mem0** | 47.4% | 43.6% | 43.0% | 47.4% | — | — | 1313ms |

Retrieval-only systems (mem0/supermemory search, ck grep) report `—` for answer-quality columns — they return ranked memories, not a synthesized answer. CH is scored end-to-end (retrieval **and** answer).
