# AGENTS.md — spike/agentic

本目录只承载 M090 rev2 的 T0 可行性桩与桩结果。

## rev2 边界

- T0 必须真测两把刀：LLM 迭代查询重构 + DenseV2/BM25 全语料再检索 + LLM/listwise 内容重排。
- 不得用 RRF 重融合或纯引文混合冒充承重主路径。
- ranker 输入只允许 query、候选 corpusid、标题、摘要、非 gold 来源标记。
- gold 只允许在排序完成后用于离线 metric 计算。
- 推荐 id 必须来自离线语料；final H5 out-of-pool 必须为 0。
- 若真测后 F1 不显著超过冻结 A-v2，必须如实停机并写 `reports/m090/STOP_REPORT.md`，不得改判据、挑样本或伪造提升。
