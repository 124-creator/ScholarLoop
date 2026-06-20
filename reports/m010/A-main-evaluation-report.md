# M010 A-main evaluation report

- Status: **PASS**
- Query count: 597
- Neural model: `sentence-transformers/all-MiniLM-L6-v2`

## Aggregate metrics
| system | P@10 | R@20 | F1 | hallucinated | tokens | latency_s |
|---|---:|---:|---:|---:|---:|---:|
| keyword | 0.0112 | 0.1583 | 0.0204 | 0 | 0 | 0.00 |
| bm25 | 0.0534 | 0.5683 | 0.0964 | 0 | 0 | 0.00 |
| neural_embedding | 0.0529 | 0.5844 | 0.0955 | 0 | 0 | 0.00 |
| single_llm | 0.0570 | 0.5456 | 0.1027 | 0 | 752242 | 4711.31 |
| scholarloop_a | 0.0625 | 0.6592 | 0.1128 | 0 | 192791 | 1689.89 |

## Protocol
- Shared candidate pool: keyword/BM25/neural top-k union; all systems scored or constrained on same pool
- Candidate top_k per local retriever: `100`
- Single-LLM prompt candidate cap: `12`
- Neural is LSA: `False`
- Temperature / seed: `0` / `42`

## Efficiency
- Total wall seconds: `20.22`
- Sum of per-query elapsed seconds: `7265.84`
- P50 / P95 query seconds: `11.55` / `20.42`
- Total tokens: `945033`
- API calls per query: `2.0`

## Significance
- Mean delta F1(A - BM25): `0.016382`
- Bootstrap 95% CI: `[0.011171, 0.021690]`
- Passed: `True`

## Explainability samples
### litsearch_000
- `221995575` score=0.9561; reason: bm25=1.000; dense=0.927; sub_bm25=1.000; sub_dense=0.872
- `258212842` score=0.9127; reason: bm25=0.782; dense=1.000; sub_bm25=0.893; sub_dense=0.886
- `218502458` score=0.9025; reason: bm25=0.888; dense=0.912; sub_bm25=0.891; sub_dense=0.827
### litsearch_001
- `252432736` score=0.9658; reason: bm25=1.000; dense=0.943; sub_bm25=0.820; sub_dense=0.966
- `6825507` score=0.9447; reason: bm25=0.924; dense=0.958; sub_bm25=0.883; sub_dense=0.999
- `227231792` score=0.8860; reason: bm25=0.715; dense=1.000; sub_bm25=1.000; sub_dense=1.000
### litsearch_002
- `226254579` score=0.9366; reason: bm25=1.000; dense=0.894; sub_bm25=0.655; sub_dense=0.947
- `233296648` score=0.9337; reason: bm25=0.980; dense=0.903; sub_bm25=1.000; sub_dense=1.000
- `256000114` score=0.9251; reason: bm25=0.813; dense=1.000; sub_bm25=0.633; sub_dense=1.000
### litsearch_003
- `7859600` score=0.9705; reason: bm25=1.000; dense=0.951; sub_bm25=0.925; sub_dense=0.964
- `11319902` score=0.9500; reason: bm25=0.970; dense=0.937; sub_bm25=0.952; sub_dense=0.973
- `472215` score=0.9437; reason: bm25=0.975; dense=0.923; sub_bm25=1.000; sub_dense=0.964
### litsearch_004
- `250551977` score=0.8829; reason: bm25=0.961; dense=0.831; sub_bm25=0.924; sub_dense=0.826
- `247594202` score=0.8552; reason: bm25=0.910; dense=0.819; sub_bm25=0.673; sub_dense=0.875
- `252918666` score=0.8477; reason: bm25=0.719; dense=0.934; sub_bm25=0.448; sub_dense=0.816
