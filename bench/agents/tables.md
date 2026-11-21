| model | arm | budget | n | correct | score (partial=0.5) | hallucination rate | context tokens (mean) | model input tokens (mean) | tool calls (mean) | latency p50 (s) | cost (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hydrogen | no context | - | 25 | 0% | 0% | 0% | 0 | 125 | 0.0 | 2.5 | 0.029 |
| hydrogen | CLAUDE.md file | 4000 | 25 | 88% | 90% | 0% | 1079 | 1431 | 0.0 | 3.5 | 0.084 |
| hydrogen | RAG (embeddings) | 4000 | 25 | 100% | 100% | 0% | 3538 | 5025 | 0.0 | 2.4 | 0.222 |
| hydrogen | capture-to-vault get_context | 4000 | 25 | 100% | 100% | 0% | 644 | 1702 | 1.0 | 4.4 | 0.101 |
| hydrogen | CLAUDE.md file | 1500 | 25 | 88% | 90% | 0% | 836 | 1183 | 0.0 | 2.9 | 0.075 |
| hydrogen | RAG (embeddings) | 1500 | 25 | 100% | 100% | 0% | 1492 | 2271 | 0.0 | 2.2 | 0.121 |
| hydrogen | capture-to-vault get_context | 1500 | 25 | 100% | 100% | 0% | 613 | 1671 | 1.0 | 5.3 | 0.104 |
| neon | no context | - | 25 | 0% | 0% | 0% | 0 | 125 | 0.0 | 4.3 | 0.054 |
| neon | capture-to-vault get_context | 4000 | 25 | 100% | 100% | 0% | 644 | 1711 | 1.0 | 7.8 | 0.212 |

Score (partial=0.5) by question kind:

| model | arm | budget | single (n=10) | multi (n=9) | fresh (n=6) |
|---|---|---|---|---|---|
| hydrogen | no context | - | 0% | 0% | 0% |
| hydrogen | CLAUDE.md file | 4000 | 100% | 72% | 100% |
| hydrogen | RAG (embeddings) | 4000 | 100% | 100% | 100% |
| hydrogen | capture-to-vault get_context | 4000 | 100% | 100% | 100% |
| hydrogen | CLAUDE.md file | 1500 | 100% | 72% | 100% |
| hydrogen | RAG (embeddings) | 1500 | 100% | 100% | 100% |
| hydrogen | capture-to-vault get_context | 1500 | 100% | 100% | 100% |
| neon | no context | - | 0% | 0% | 0% |
| neon | capture-to-vault get_context | 4000 | 100% | 100% | 100% |
