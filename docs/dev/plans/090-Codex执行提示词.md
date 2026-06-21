# 090 · 交给 Codex 的执行提示词（dispatch）· 修订轮次 2

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥，只引用环境变量名与 verified 产物/接口路径。
> 联网授权沿用 M050/M060。
> **修订轮次 2 背景**：rev1 在 T0 停机但**欠测**——只测了 RRF 重融合 + 引文混合，**没实现承重主路径「迭代 LLM 检索」与「强化重排」**。第十四次初查判定停机不合法（用廉价信号代替承重刀）。本轮**强制真测两把刀**，并先修复环境缺失的 `rank_bm25`。详见 `090` 计划修订轮次 2 标注与决策日志同日 rev2 审批记录。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次是 **M090 修订轮次 2**：执行**已批准**的计划
`docs/dev/plans/090-主动迭代检索与强化重排-计划.md`（approved · rev2）——把 A 主干升级为 **A-v3 主动迭代检索 + 强化重排**，抬绝对 F1（42% 主轴）+ 补官方 §3.1.2。

【为什么有 rev2（先读，避免重蹈覆辙）】
rev1 的 T0 桩**只做了两件廉价的事**：① 对 M040 **已经算好的排序**做 RRF 重融合；② A-v2 排序融合离线引文邻域（citation_blend）。两者都没实现计划承重的**真正杠杆**，且 rev1 桩**零 LLM 调用、零再检索、零真重排模型**。**本轮严禁再走这条捷径。** 引文混合已被证明过拟合（train 正、holdout/test 回退），**rev2 不以引文为焦点**。

【本轮强制真做的两把承重刀（缺一不可，必须真实实现并端到端跑）】
1. **迭代 LLM 检索（多轮，gold-blind，必须真再检索）**：用 `LLMClient` 读首轮 top-k 候选的**标题/摘要（绝不读 gold）**→ 生成**精炼/扩展子查询**→ 用 `DenseV2`（复用 `reports/m040/cache/dense_v2/` 缓存编码）**+ BM25** 对**整个语料再检索**，拿回**原候选池之外的新候选**→ 合并去重。**必须产生新候选**（不是重排已有列表）；轮数/预算有界、确定性、原始 LLM 响应落 `reports/m090/raw/llm/`。
2. **强化重排（直击 P@10，必须读内容重排）**：对扩展候选做**真重排**——优先 **listwise LLM 重排**（`LLMClient` 读候选标题/摘要，gold-blind，输出重排序）；可并行/对比**更大 cross-encoder**（如 ms-marco-MiniLM-L-12 或 bge-reranker-base）。**必须基于论文内容重新判相关性**，不是 RRF 重组 rank 位。同候选池内排序、H5 不越池。

【最高优先级 · 四条不可越的红线】
1. **gold-blind**：迭代子查询重构、listwise 重排，**只用 query + 候选标题/摘要/全文**，**绝不读 gold**；gold 只在最终评测算指标时用。T0/T4 须有 gold-blind 校验（断言 ranker 输入不含 gold id/内容）。
2. **承重 = A-v3 端到端 F1 配对显著 > A-v2 冻结基线，且增益在 holdout + test split 均成立**（防过拟合、隐藏集代理）；调参 train-only。不显著或只在 train 成立 → **停机如实上报「A-v2 已是该语料强基线、迭代+重排亦未显著超越」**，**绝不**调判据/挑样本/造假。
3. **H5 不越池 / 不伪造候选**：A-v3 推荐 id 必在离线语料内（0 越池、0 虚构）；新候选只来自**对真实语料的再检索**。
4. **成本诚实记账**：迭代/重排引入 LLM 调用——如实记 A-v3 vs A-v2 的**调用次数/token/延时增量**（效率 20% 维度）；temperature=0/seed、原始 LLM 落盘可重放。

【T0 第一步 · 先修环境（硬前置）】
- `rank_bm25` 在当前环境**缺失**（`src/scholarloop/retrieval/bm25.py` 依赖 `from rank_bm25 import BM25Okapi`），rev1 时退化（M080 时全量 `pytest` 尚 33 passed）。**先 `pip install rank_bm25` 恢复**，确保 BM25 再检索可用 + 全量 `pytest tests/ -q` 能跑（恢复回归基线）。若仍有其它缺失依赖一并修复或如实记录。

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/090-主动迭代检索与强化重排-计划.md`（**逐条照做**，§2/§6/§7/§8/§10/§11；**rev2 标注**）
- `docs/dev/000-决策日志.md` 顶部「M090 修订轮次 2」审批记录 + 第十四次初查记录（欠测判定 + rev2 强制项）
- `00-赛题/...txt` §3.1.2（迭代检索）；`015`（S1/F1 + S2 效率）；`02`（X1 公开 gold、H5）
- **A-v2 冻结基线 + 可复用接口（只读，不改）**：
  - `reports/m040/results.json`（A-v2 = `protocol.final_weights={bm25:0.1,dense_v2:0.4,sub_bm25:0.15,sub_dense_v2:0.15,cross_encoder:0.2}` + bge-small + ms-marco；A-v2 LitSearch F1=0.1312/R@20=0.7564/**P@10=0.0727←要抬的瓶颈**；分 split train0.1270/holdout0.1452/test0.1286）
  - `reports/m040/cache/dense_v2/`（bge-small 语料编码缓存——迭代再检索复用，免重编码）
  - `src/scholarloop/retrieval/{bm25.py,dense_v2.py}`（`BM25Retriever`、`DenseV2.scores`/`batch_scores`）、`src/scholarloop/rank/{fusion_v2.py,rerank.py}`、`src/scholarloop/query/decompose.py`（`QueryDecomposer`）
  - `src/scholarloop/eval/run_full_v2.py`（`deterministic_query_split`→train/holdout/test、`aggregate_by_split`、`paired_bootstrap(seed=42)`、`metric_with_ndcg`——A-v3 评测**沿用同 split/metric/显著性**）
  - `src/scholarloop/llm.py`（`LLMClient(raw_dir).chat_json(...)`，原始响应落 `reports/m090/raw/llm/`；先 `precheck` 确认 LLM 端点可用，不可用则停机）

【本轮要做（按 §6/§7 顺序）】
0. **T0 · 修环境 + 可行性桩（gate，真测两把刀）**：装回 `rank_bm25`；在 train 子集上**真实运行**迭代 LLM 检索 + listwise 重排（或更大 cross-encoder），验证 gold-blind 下相对 A-v2 冻结 F1 **正向且方向稳定（train/holdout/test 一致正向、bootstrap CI 下界>0）**。产出 `reports/m090/spike/agentic_spike.json`（须含真实 LLM 调用计数 + 新候选召回证据，**不得**再是纯 RRF/引文）。**【停机】** 真测两把刀后仍不正向/只 train 正 → 此时方可如实停机「A-v2 已是强基线」。
1. **T1 · 迭代检索** `src/scholarloop/retrieval/iterative.py` + `src/scholarloop/agent/**`：多轮 gold-blind 重构 + DenseV2/BM25 再检索 + 合并新候选；单测覆盖确定性、gold 未进检索输入、**新候选确来自再检索（非已有列表）**、候选∈语料。
2. **T2 · 强化重排** `src/scholarloop/rank/rerank_v2.py`：listwise LLM 重排 / 更大 cross-encoder，读内容重排抬 P@10；同池、H5、确定性、原始 LLM 落盘。
3. **T3 · 引文扩展（可选·非焦点）**：rev1 已证引文混合过拟合；仅当与迭代+重排正交且能稳定增益才保留，否则**砍掉**并记录。
4. **T4 · 端到端承重评测** `src/scholarloop/eval/run_full_v3.py`：A-v3（迭代+重排）vs **A-v2 冻结** vs 基线在**同 gold** 上端到端 P@10/R@20/F1/NDCG，沿用 `run_full_v2` 的 split + `paired_bootstrap`，调参 train-only、留出/test 只验证；**成本记账**。产出 `reports/m090/{results.json,significance.json,评测报告.md}`（含 `aggregate_by_split`、`protocol.gold_blind=true`、LLM 调用/token/延时增量）。
5. **T5 · 合规 / 可复现 / 复盘**：原始 LLM 重放一致；无密钥；上游 M010–M080 sha 未变；全量 `pytest tests/ -q` 恢复通过；写 `docs/dev/retrospectives/090-主动迭代检索与强化重排-复盘.md`（F1 提升成立/不成立 + 成本口径，都如实；并复盘 rev1 欠测教训）。

【硬红线（不得改动）】
- 见上四条红线 + 两把刀必须真实实现；**严禁**用 RRF 重融合已有排序或纯引文混合冒充承重主路径。
- §8 承重：A-v3 端到端 F1 **配对显著 > A-v2 冻结** 且 **holdout+test 均成立**。
- 防过拟合：调参 train-only，增益跨 split 成立。确定性/可复现：temperature=0/seed、原始 LLM 落盘可重放。
- **上游冻结只读**：M010–M080 产物/源码行为/判据 + A-v2 冻结配置全只读；A-v3 走新文件。
- 只允许写：`src/scholarloop/retrieval/{iterative.py,citation_expand.py}`、`src/scholarloop/agent/**`、`src/scholarloop/rank/rerank_v2.py`、`src/scholarloop/eval/run_full_v3.py`、`spike/agentic/**`、`tests/test_m090_*.py`（**不改** `test_m010..m080`）、`reports/m090/**`、复盘文件。环境依赖 `rank_bm25` 允许安装（记录到复盘/requirements）。

【可自行决定（§10 预算内）】迭代轮数与候选预算；子查询重构 prompt；重排实现（listwise LLM 与/或更大 cross-encoder，可二选一或对比）；缓存键；`agent/` 文件组织与局部命名。所有有界决策落盘依据。**但「是否真实实现迭代再检索 + 强化重排」不在自由裁量内——必须做。**

【必须停机上报（写 `reports/m090/` 停机报告，交总指挥）】
- **真测两把刀后** A-v3 仍不显著 > A-v2 冻结（此时停机合法，须附真实 LLM 调用/再检索证据，证明确已实现并测试）；增益只在 train 成立（过拟合）；需 gold 泄漏才成立（红线）；需伪造候选或联网冒充离线（红线）；LLM 端点不可用（precheck 失败）；成本爆炸而 F1 无显著增益（如实报，交人类裁定）；需改 M010–M080 产物或任何 §8 判据。
- **不接受**仅以 RRF/引文混合的负结果停机——那不是承重主路径。

【交付】完成后：`src/scholarloop/{retrieval/iterative.py,agent/**,rank/rerank_v2.py,eval/run_full_v3.py}` + `spike/agentic/run_agentic_spike.py`（rev2，真测两把刀）；`pytest tests/ -q` 全量通过记录（含 rank_bm25 修复）；桩结论 + 端到端评测产物 `reports/m090/**`（含 split 增益、gold_blind 协议、成本记账、可离线重放原始 LLM）；写复盘。把 `090` 状态推进为 `implemented`（若真测两把刀后承重不达，保持 `approved` 并附**含真实 LLM/再检索证据**的停机报告）。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第十五次初查）。
