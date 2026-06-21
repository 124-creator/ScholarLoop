# M010 A-main evaluation report

- Status: **BLOCKED**
- Query count: 6
- Neural model: `sentence-transformers/all-MiniLM-L6-v2`

## Aggregate metrics
| system | P@10 | R@20 | F1 | hallucinated | tokens | latency_s |
|---|---:|---:|---:|---:|---:|---:|
| keyword | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 0.00 |
| bm25 | 0.0333 | 0.2500 | 0.0581 | 0 | 0 | 0.00 |
| neural_embedding | 0.0667 | 0.5833 | 0.1187 | 0 | 0 | 0.00 |
| single_llm | 0.0500 | 0.4167 | 0.0884 | 0 | 19187 | 115.83 |
| scholarloop_a | 0.0500 | 0.4167 | 0.0884 | 0 | 1579 | 13.75 |

## Significance
- Mean delta F1(A - BM25): `0.030303`
- Bootstrap 95% CI: `[0.000000, 0.090909]`
- Passed: `False`

## Explainability samples
### litsearch_000
- `221995575` score=0.9561; reason: bm25=1.000; dense=0.927; sub_bm25=0.930; sub_dense=0.964
- `258212842` score=0.9127; reason: bm25=0.782; dense=1.000; sub_bm25=1.000; sub_dense=0.979
- `218502458` score=0.9025; reason: bm25=0.888; dense=0.912; sub_bm25=0.851; sub_dense=0.917
### litsearch_001
- `252432736` score=0.9658; reason: bm25=1.000; dense=0.943; sub_bm25=0.838; sub_dense=0.953
- `6825507` score=0.9447; reason: bm25=0.924; dense=0.958; sub_bm25=0.924; sub_dense=0.888
- `227231792` score=0.8860; reason: bm25=0.715; dense=1.000; sub_bm25=1.000; sub_dense=0.992
### litsearch_002
- `226254579` score=0.9366; reason: bm25=1.000; dense=0.894; sub_bm25=0.842; sub_dense=0.962
- `233296648` score=0.9337; reason: bm25=0.980; dense=0.903; sub_bm25=1.000; sub_dense=1.000
- `256000114` score=0.9251; reason: bm25=0.813; dense=1.000; sub_bm25=0.746; sub_dense=1.000
### litsearch_003
- `7859600` score=0.9705; reason: bm25=1.000; dense=0.951; sub_bm25=0.938; sub_dense=0.964
- `11319902` score=0.9500; reason: bm25=0.970; dense=0.937; sub_bm25=0.952; sub_dense=0.973
- `472215` score=0.9437; reason: bm25=0.975; dense=0.923; sub_bm25=1.000; sub_dense=0.954
### litsearch_004
- `250551977` score=0.8829; reason: bm25=0.961; dense=0.831; sub_bm25=1.000; sub_dense=1.000
- `247594202` score=0.8552; reason: bm25=0.910; dense=0.819; sub_bm25=0.872; sub_dense=0.936
- `252918666` score=0.8477; reason: bm25=0.719; dense=0.934; sub_bm25=0.501; sub_dense=0.858
