# 040 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥，只引用环境变量名。
> 凭证沿用 M010 已建的 `src/scholarloop/config.py`（import 时自加载 `secrets/llm.env.local`）；env 为空先 import 自加载，不构成停机理由；该文件只读、不改、不回显。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次任务是执行**已批准**的计划
`docs/dev/plans/040-检索排序增强-计划.md`（状态 approved，修订轮次 1）——构建 **A 主干检索排序增强（A-v2）**，把 ScholarLoop-A 的绝对 F1 **稳健**抬高（第四个业务模块）。

【唯一真源】先读这些文件，以它们为准，不要凭会话臆测：
- `docs/dev/plans/040-检索排序增强-计划.md`（**逐条照做**，尤其 §2 范围、§4 调研结论、§6 任务、§8 验收、§10 决策预算、§11 风险）
- `docs/dev/spec/015-成功标准校准.md`（S1 承重墙 + S2 效率）、`docs/dev/spec/035-选定路线冻结.md`（A 主干增强、不改冻结目标）、`docs/dev/spec/040-验证桩结论.md`（PASS + 同候选池协议）
- M010 verified 产物（**只读消费 / 移植复用，不回改其行为**）：`reports/m010/results.json`（A-v1 冻结对照 + 同候选池来源）、`src/scholarloop/{config,llm,corpus,utils,eval/run_full,rank/fusion,retrieval/{bm25,dense},query/decompose}`、`spike/eval/run_spikes.py`（同候选池协议、`metric_for_ranking`、H5、bootstrap）

【本次要做（按 §6 顺序）】
0. **凭证/基线/对照**：`import scholarloop.config`；载入 A-v1（`reports/m010/results.json`）为**冻结对照**与同候选池来源；建 `reports/m040/` 骨架。先复算 A-v1 F1=0.1128 对照值。
1. **神经嵌入升级**（`src/scholarloop/retrieval/dense_v2.py`）：用更强**开源、可离线**句向量（`bge-base-en-v1.5` / `e5-base-v2` 等）编码语料+查询、余弦召回；确定性、缓存、模型名+版本入证据。**【停机】** 需 GPU 或 >2GB 下载受阻 → 上报，不擅自换重依赖。
2. **Cross-encoder 重排**（`src/scholarloop/rank/rerank.py`）：对候选池 Top-N 用开源 cross-encoder（`bge-reranker-base` / `ms-marco-MiniLM` 等）精排；做**开/关消融**记录净 F1 贡献；确定性。
3. **融合 v2 + 子查询信号**（`src/scholarloop/rank/fusion_v2.py`）：在**全量**上重估 `sub_bm25/sub_dense`（M010 置 0），调融合权重与 Top-K——**只在留出/交叉验证集上调**，落盘调参协议与最终配置。
4. **防过拟合协议**：把 LitSearch 查询做 train/test 划分（或 k-折），**调参用 train、报告用 test**；划分协议 + test 结果落盘。
5. **全量重测 + 双显著性**（`src/scholarloop/eval/run_full_v2.py`）：≥5 系统（关键词/BM25/神经Embedding/单轮LLM/**A-v2**）+ 保留 **A-v1 对照** 同候选池算 P@10/R@20/F1/**NDCG**；对 **A-v2 vs BM25** 与 **A-v2 vs A-v1** 各做配对 bootstrap(≥10000)/置换；效率（API/Token/P50·P95）记账。产出 `reports/m040/results.json`+`.csv`、`significance.json`、`A-v2评测报告.md`。
6. **合规 / 可复现 / 复盘**：全仓无密钥；两次端到端一致；写 `docs/dev/retrospectives/040-检索排序增强-复盘.md`。

【硬红线（不得改动）】
- §8 承重：**(保) A-v2 F1 配对显著优于 BM25**（CI(ΔF1) 不含 0 或置换 p<0.05）；**(提升) A-v2 F1 > A-v1(0.1128)**，方向明确（最好配对显著）；**(防过拟合) 增益在留出/test 集上成立**，附 train/test 划分协议。
- **三者任一不达 → 停机上报**，**不得**调判据 / 挑样本 / 关基线 / 只报公开集制造表面提升。
- **A-v1（M010）冻结**：A-v2 走**新路径**，不得改 `reports/m010|m020|m030/**`、M010/M020/M030 既有源码行为、`010` 验收判据、`040 结论`、任何 FROZEN 件、`spike/**`。
- H5「0 虚构」、同候选池协议、temperature=0/seed 固定、原始落盘、确定性、密钥脱敏——**继承 M010 不放宽**。
- 只允许写 `src/scholarloop/{retrieval/dense_v2.py,rank/rerank.py,rank/fusion_v2.py,eval/run_full_v2.py 及必要新小文件}`、`tests/**`（新增 `test_m040_*.py`，**不改** `test_m010/m020/m030`）、`reports/m040/**`。
- **绝不把密钥写入任何文件**；只经 config 读取；异常对密钥脱敏。

【可自行决定（§10 预算内）】具体开源嵌入模型与 cross-encoder；Top-N/K；融合权重（仅在留出集上调）；向量索引实现（numpy/FAISS）；新增文件组织与局部命名。

【必须停机上报（写 `reports/m040/` 停机报告，交总指挥，不自行扩范围）】
- A-v2 未显著优于 BM25 **或** 未优于 A-v1 **或** 增益仅在公开集（过拟合）；需 GPU/>2GB/重依赖受阻；效率超 `015` S2 预算；需改 M010/M020/M030 产物或任何 §8 判据；需在线付费/受限数据；LLM 端点失效/凭证问题；任何只能靠虚构才能填的字段。

【交付】完成后：`src/scholarloop/**` 新增（多小文件）+ 说明；`pytest tests/ -q` 通过记录；`reports/m040/**` 评测产物（含 `significance.json`、留出集结果、raw 落盘）；写复盘 `docs/dev/retrospectives/040-检索排序增强-复盘.md`；把 `040` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查。
