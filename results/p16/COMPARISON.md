# CH-Bench comparison — `contextheavy` suite

6 systems · 35 questions · k=10 · LLM-judge: qwen3.5-397b (NVIDIA NIM)

| system | recall@k | nDCG@10 | MRR | hit@k | answer correctness | abstention | latency p50 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **ch** | 85.7% | 81.3% | 80.0% | 85.7% | 100.0% | 100.0% | 8320ms |
| **gbrain** | 85.7% | 79.5% | 77.5% | 85.7% | — | — | 3031ms |
| **supermemory** | 85.7% | 83.8% | 82.9% | 85.7% | — | — | 1202ms |
| **mock** | 77.1% | 68.7% | 66.4% | 77.1% | 68.3% | 0.0% | 0ms |
| **ck** | 71.4% | 64.6% | 62.4% | 71.4% | — | — | 49ms |
| **mem0** | 22.9% | 21.3% | 17.6% | 22.9% | — | — | 1249ms |

Retrieval-only systems (mem0/supermemory search, ck grep) report `—` for answer-quality columns — they return ranked memories, not a synthesized answer. CH is scored end-to-end (retrieval **and** answer).
