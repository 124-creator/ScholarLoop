# T2b · LLM 基线与 A-min

- 日期：2026-06-18
- 判定：PASS
- 端点：`https://api.deepseek.com`；模型：`deepseek-v4-flash`；temperature=0；seed=42；max_tokens=8192。
- 原始响应：`spike/raw/llm/t2b/`（未保存密钥，raw 只含响应与非敏感元数据）。

## 聚合结果（10 查询平均）
| system | P@10 | R@20 | F1 | hallucinated/out_of_pool | total_tokens | total_latency_s |
|---|---:|---:|---:|---:|---:|---:|
| keyword | 0.0000 | 0.0200 | 0.0000 | 0 | 0 | 0.00 |
| bm25 | 0.0800 | 0.3600 | 0.1300 | 0 | 0 | 0.00 |
| embedding_lsa | 0.0000 | 0.1500 | 0.0000 | 0 | 0 | 0.00 |
| single_llm | 0.0500 | 0.2700 | 0.0800 | 0 | 40493 | 146.22 |
| a_min | 0.0600 | 0.3900 | 0.0933 | 0 | 2972 | 25.17 |

## 判据
- A-min F1 `0.0933` vs 最弱基线 F1 `0.0000`：PASS。
- 单轮 LLM / A-min 虚构或越出候选池 ID：0（未知 ID 按 H5 计不相关且记录）。
- 同候选池：LLM 仅允许从 T2a 三基线 Top-100 并集候选池中选择 corpusId。

## 证据文件
- `spike/eval/results_t2b.json` / `.csv`
- `spike/raw/llm/t2b/`
