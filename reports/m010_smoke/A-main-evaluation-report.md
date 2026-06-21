# M010 A-main evaluation report

- Status: **BLOCKED**
- Query count: 3
- Neural model: `sentence-transformers/all-MiniLM-L6-v2`

## Aggregate metrics
| system | P@10 | R@20 | F1 | hallucinated | tokens | latency_s |
|---|---:|---:|---:|---:|---:|---:|
| keyword | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 0.00 |
| bm25 | 0.0667 | 0.5000 | 0.1162 | 0 | 0 | 0.00 |
| neural_embedding | 0.0667 | 0.5000 | 0.1162 | 0 | 0 | 0.00 |
| single_llm | 0.0667 | 0.5000 | 0.1162 | 0 | 14580 | 67.26 |
| scholarloop_a | 0.0667 | 0.5000 | 0.1162 | 0 | 933 | 7.79 |

## Significance
- Mean delta F1(A - BM25): `0.000000`
- Bootstrap 95% CI: `[0.000000, 0.000000]`
- Passed: `False`

## Explainability samples
### litsearch_000
- `221995575` score=1.1769; reason: bm25=1.000; dense=0.927; sub_bm25=1.000; sub_dense=0.989
- `257038997` score=1.0936; reason: bm25=0.886; dense=0.891; sub_bm25=1.000; sub_dense=0.973
- `218502458` score=1.0674; reason: bm25=0.888; dense=0.912; sub_bm25=0.846; sub_dense=0.910
### litsearch_001
- `252432736` score=1.1801; reason: bm25=1.000; dense=0.943; sub_bm25=1.000; sub_dense=0.972
- `6825507` score=1.1229; reason: bm25=0.924; dense=0.958; sub_bm25=0.940; sub_dense=0.931
- `227231792` score=1.0233; reason: bm25=0.715; dense=1.000; sub_bm25=1.000; sub_dense=1.000
### litsearch_002
- `233296648` score=1.1583; reason: bm25=0.980; dense=0.903; sub_bm25=1.000; sub_dense=1.000
- `226254579` score=1.1142; reason: bm25=1.000; dense=0.894; sub_bm25=0.725; sub_dense=0.954
- `256000114` score=1.0196; reason: bm25=0.813; dense=1.000; sub_bm25=0.643; sub_dense=1.000
