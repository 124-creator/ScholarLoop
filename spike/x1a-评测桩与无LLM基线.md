# T2a · 评测桩与无 LLM 基线

- 日期：2026-06-18
- 判定：PASS
- 基准：LitSearch；查询数：10；语料：64183 篇。
- 候选池协议：每个系统 Top-100 的并集作为共享候选池，三基线均在同池内重排评分。
- Embedding 基线：local sklearn TF-IDF + TruncatedSVD dense embedding (deterministic random_state=42)。说明：当前环境无 `sentence_transformers/transformers`，未新增重依赖，按 §10 决策预算采用本地轻量 dense embedding。
- 两次运行一致：True

## 聚合结果（10 查询平均）
| system | P@10 | R@20 | F1 |
|---|---:|---:|---:|
| keyword | 0.0000 | 0.0200 | 0.0000 |
| bm25 | 0.0800 | 0.3600 | 0.1300 |
| embedding_lsa | 0.0000 | 0.1500 | 0.0000 |

## 逐查询共享候选池与命中概览
| query_id | shared_pool_size | keyword hits@20 | bm25 hits@20 | embedding hits@20 |
|---|---:|---|---|---|
| litsearch_096 | 264 | [218487034] | [218487034, 226254579, 233407441] | [] |
| litsearch_018 | 239 | [] | [] | [] |
| litsearch_023 | 226 | [] | [] | [] |
| litsearch_002 | 272 | [] | [226254579] | [] |
| litsearch_113 | 270 | [] | [244954670, 256461055] | [244954670, 256461055] |
| litsearch_156 | 253 | [] | [244117167] | [] |
| litsearch_257 | 271 | [] | [] | [] |
| litsearch_328 | 291 | [] | [233231453] | [] |
| litsearch_334 | 231 | [] | [229923710] | [] |
| litsearch_335 | 247 | [] | [] | [237372185] |

## 证据文件
- `spike/eval/results_t2a_run1.json` / `.csv`
- `spike/eval/results_t2a_run2.json` / `.csv`
