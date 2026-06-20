# M040 A-v2 evaluation report

- Status: **PASS**
- Query count: `597`
- Dense model: `BAAI/bge-small-en-v1.5`
- Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Device: `cpu`
- Final weights: `{"bm25": 0.1, "dense_v2": 0.4, "sub_bm25": 0.15, "sub_dense_v2": 0.15, "cross_encoder": 0.2}`

## Aggregate metrics
| system | P@10 | R@20 | F1 | NDCG@20 | hallucinated | tokens | latency_s |
|---|---:|---:|---:|---:|---:|---:|---:|
| keyword | 0.0112 | 0.1583 | 0.0204 | 0.0684 | 0 | 0 | 0.00 |
| bm25 | 0.0534 | 0.5683 | 0.0964 | 0.3931 | 0 | 0 | 0.00 |
| neural_embedding_v2 | 0.0590 | 0.6397 | 0.1065 | 0.4494 | 0 | 0 | 0.00 |
| single_llm_frozen_m010 | 0.0570 | 0.5456 | 0.1027 | 0.4924 | 0 | 752242 | 4711.31 |
| scholarloop_a_v1_frozen | 0.0625 | 0.6592 | 0.1128 | 0.4853 | 0 | 192791 | 1689.89 |
| scholarloop_a_v2_no_rerank | 0.0709 | 0.7481 | 0.1281 | 0.5453 | 0 | 0 | 0.00 |
| scholarloop_a_v2 | 0.0727 | 0.7564 | 0.1312 | 0.5657 | 0 | 0 | 973.88 |

## Split F1 (anti-overfit evidence)
| split | BM25 | A-v1 frozen | A-v2 | Δ(A-v2-BM25) | Δ(A-v2-A-v1) |
|---|---:|---:|---:|---:|---:|
| train | 0.0928 | 0.1085 | 0.1270 | 0.0342 | 0.0185 |
| holdout | 0.1056 | 0.1255 | 0.1452 | 0.0397 | 0.0198 |
| test | 0.0977 | 0.1123 | 0.1286 | 0.0309 | 0.0164 |

## Significance
- A-v2 vs BM25 ΔF1: `0.034793`, CI95=`[0.028662, 0.040876]`, passed=`True`
- A-v2 vs A-v1 ΔF1: `0.018411`, CI95=`[0.013473, 0.023421]`, passed=`True`

## Efficiency
- Total wall seconds: `1145.68`
- P50/P95 query seconds: `1.50` / `2.82`
- A-v2 API calls per query / tokens: `0.0` / `0`

## Stop condition
- Wall passed: `True`
