# M010 A-main evaluation report

- Status: **BLOCKED**
- Query count: 1
- Neural model: `sentence-transformers/all-MiniLM-L6-v2`

## Aggregate metrics
| system | P@10 | R@20 | F1 | hallucinated | tokens | latency_s |
|---|---:|---:|---:|---:|---:|---:|
| keyword | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 0.00 |
| bm25 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 0.00 |
| neural_embedding | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 0.00 |
| single_llm | 0.0000 | 0.0000 | 0.0000 | 0 | 1858 | 12.44 |
| scholarloop_a | 0.0000 | 0.0000 | 0.0000 | 0 | 259 | 1.90 |

## Significance
- Mean delta F1(A - BM25): `0.000000`
- Bootstrap 95% CI: `[0.000000, 0.000000]`
- Passed: `False`

## Explainability samples
### litsearch_000
- `221995575` score=0.9561; reason: bm25=1.000; dense=0.927; sub_bm25=1.000; sub_dense=0.980
- `258212842` score=0.9127; reason: bm25=0.782; dense=1.000; sub_bm25=1.000; sub_dense=0.980
- `218502458` score=0.9025; reason: bm25=0.888; dense=0.912; sub_bm25=0.831; sub_dense=0.921
