# M060 RealScholarQuery/PaSa frozen-transfer evaluation report

Status: `implemented_pending_review`
Wall passed: `True`

## Primary (resolvable gold)
- A-v2 F1: `0.197208`
- BM25 F1: `0.105844`
- ΔF1 bootstrap: `0.091364`, CI95=`[0.065710, 0.117623]`, passed=`True`
- ΔF1 permutation p(one-sided): `0.000100`, passed=`True`

## Robustness (full 791 official gold; 52 as equal misses)
- A-v2 F1: `0.192882`
- BM25 F1: `0.103565`
- ΔF1 bootstrap: `0.089317`, CI95=`[0.064285, 0.115086]`, passed=`True`
- ΔF1 permutation p(one-sided): `0.000100`, passed=`True`

## Aggregate table (resolvable)
| system | P@10 | R@20 | F1 | NDCG@20 | hallucinated/out-of-pool |
|---|---:|---:|---:|---:|---:|
| keyword | 0.0120 | 0.0197 | 0.0137 | 0.0193 | 0 |
| bm25 | 0.1100 | 0.1479 | 0.1058 | 0.1567 | 0 |
| neural_embedding_v2 | 0.1320 | 0.1859 | 0.1208 | 0.1858 | 0 |
| single_llm | 0.1940 | 0.1806 | 0.1585 | 0.2488 | 0 |
| scholarloop_a_v2_no_rerank | 0.1980 | 0.2585 | 0.1911 | 0.2757 | 0 |
| scholarloop_a_v2 | 0.2120 | 0.2611 | 0.1972 | 0.2907 | 0 |
