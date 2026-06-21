# 100 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息。
> 联网授权沿用 M050/M060。
> **核心特征**：F1 封顶后转专家分 40% + 结构化 10%。承重 = 关系图忠实零伪造 + 消融诚实可复现 + 实时成本透明。M010–M090 + M080 demo verified 面板/fidelity + M070 verified 空白产物**冻结只读**，全部新增走新文件。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/100-专家分攻坚与演示升级-计划.md`（状态 approved）——F1 主轴已封顶（M090 两轮诚实攻坚证 A-v2 为强基线），本轮转向**高赢面的专家分 40%（创新/落地/泛化）+ 结构化 10%**，并正面消除两个历史携带项（M070 频率混杂、M080 关系图为表格非可视图）。

【最高优先级 · 红线（先读再动手）】
1. **冻结只读**：M010–M090 全部产物/源码行为/验收判据、M080 的 `src/scholarloop/demo/**` 既有 **verified 面板与 fidelity**、M070 的 `reports/m070/**` verified 空白产物——**一律只读不改**；本轮全部**新增**走新文件（复刻 A-v2/demo 的"新增不改原件"纪律）。
2. **零伪造**：关系图节点/边值**逐字来自 verified JSON**（M070 gaps_display / M020 evidence）；实时模式结果**不编造**，失败优雅回退；缺失字段标"需人工核验"，不补写。
3. **诚实消融**：频率配平消融若显示空白预测信号**减弱或消失**，**如实照报并收紧创新主张**——这是**正常结果不是停机项**，绝不藏、绝不夸大。
4. **零身份 / 零密钥**：提交物料不得含学校/学院/导师；UA 邮箱脱敏；无密钥落盘/回显。

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/100-专家分攻坚与演示升级-计划.md`（**逐条照做**，§2/§6/§7/§8/§10/§11）
- `docs/dev/000-决策日志.md` 顶部「M100 批准」+「M090 封档/转向」记录
- `00-赛题/...txt` §3.1.4（「关系图」结构化展示）、§4（专家评分）；`015`（S3/S4/S5）
- **冻结只读复用对象**：
  - M070 频率口径：`src/scholarloop/gaps/detect.py`（`extract_concepts`、past/recent df、`_random_baseline` 范式）、`reports/m070/{gaps_display.json,results.json,significance.json}`（空白候选 + 概念 counts + 现有随机基线 0.108 vs 0.022）
  - M080 demo 框架：`src/scholarloop/demo/{app.py,assemble.py,render.py,verify.py}`（既有端点 `/healthz`、`/api/queries`、`/api/metrics`、`/api/gaps`、`/api/queries/{qid}`、`/?qid=` 与 fidelity 范式——**新增视图/端点，不改这些**）
  - 实时管线复用：`src/scholarloop/{query/decompose.py,retrieval/{bm25.py,dense_v2.py},rank/{fusion_v2.py,rerank.py},llm.py}`（A-v2 在线跑）、`reports/m040/cache/dense_v2/`（编码缓存）

【本轮要做（按 §6/§7 顺序）】
1. **T1 · M070 频率配平消融（必做 · 创新硬化）** `src/scholarloop/gaps/frequency_ablation.py`：
   - 构造**频率匹配的随机基线**——对每个检出空白候选（概念对 a,b），抽取**边际频率相近**的随机概念对（按 past_df/recent_df 分桶匹配），剥离"候选是高活跃概念对"的混杂。
   - 重算空白预测效力（过去检出被未来填补率）是否仍**显著 > 频率配平基线**（确定性、bootstrap≥10000/置换，seed 固定）。
   - 产出 `reports/m100/gap_frequency_ablation.json` + 诚实结论：信号仍显著 → 创新主张升级为"控制频率后仍成立"；信号减弱/消失 → **如实收紧**为"频率为主要驱动 / 部分预测效力"。**不改 `reports/m070/**`。**
2. **T2 · 可视化关系图（必做 · 结构化）** `src/scholarloop/demo/graph.py` + demo **新增**视图/端点（如 `/api/graph`、`/graph`）：
   - 研究空白/证据的**节点连线图**——概念为节点，共现/引用/未来填补为边（数据**逐字来自** `reports/m070/gaps_display.json` 的 `concept_nodes`/`matrix_edges`、M020 evidence）；轻量内联 **SVG/Canvas**（不引重前端框架，守 035 视觉红线）。
   - **fidelity 校验**：图上每个节点/边的值==后端 verified JSON（零伪造、缺失不补写）；产出 `reports/m100/graph_fidelity.json`（fabrication=0）。
3. **T3 · 实时提问演示模式（落地 · 默认离线+可选开关+优雅回退）** `src/scholarloop/demo/realtime.py` + **新增**端点（如 `/api/realtime?q=...`，默认关闭，需显式开关启用）：
   - 接受用户**自由文本新查询**→ 跑实时 A-v2 管线（LLM 拆解→BM25/DenseV2 检索→A-v2 融合排序→证据）；
   - **诚实记成本**（LLM 调用/token/延时，页面显示）；**优雅回退**（LLM 端点不可用/超时→显式提示"实时不可用"，**不编造结果**）；**明确标注"实时·非确定性·非 verified 承重"**，与离线 verified 面板**分离**；默认 offline，realtime 为可选开关（环境变量/参数）。
   - 烟测 `reports/m100/realtime_smoke.txt`（含成本 + 回退路径）。
4. **T4 · 提交物料硬化** `docs/submission/**`（**追加**，不改既有 verified 主张）：写入频率消融结论（含诚实边界）、关系图、实时能力；每条主张挂证据；零身份/零夸大。
5. **T5 · 合规 / 可复现 / 复盘**：消融可重放；图 fidelity=0 伪造；无密钥；上游 M010–M090 sha 未变；全量 `pytest tests/ -q` 通过；写 `docs/dev/retrospectives/100-专家分攻坚与演示升级-复盘.md`（含频率消融诚实结论）。

【硬红线（不得改动）】
- §8 承重②**关系图忠实零伪造**：图节点/边值逐字==后端 verified JSON、fabrication=0。
- 频率消融**诚实**：显著性如实报，信号减弱则收紧主张（非停机）。
- 实时模式**成本透明 + 优雅回退 + 标非确定性**，不编造、不当 verified 承重。
- **冻结只读**：M010–M090 产物/源码行为/判据 + M080 demo verified 面板/fidelity + M070 verified 空白产物全只读；新增走新文件。
- 零身份（无学校/学院/导师，UA 脱敏）；零密钥；确定性消融可复现。
- 只允许写：`src/scholarloop/gaps/frequency_ablation.py`、`src/scholarloop/demo/{graph.py,realtime.py}`（+ demo 路由**新增**端点，不改既有处理）、`tests/test_m100_*.py`（**不改** `test_m010..m090`）、`reports/m100/**`、`docs/submission/**`（追加）、复盘文件。

【可自行决定（§10 预算内）】SVG/Canvas 选型与关系图布局；频率配平基线实现（分桶/匹配口径）；实时超时阈值与回退文案；`graph.py`/`realtime.py` 组织与局部命名；提交文档式样。

【必须停机上报（写 `reports/m100/` 停机报告，交总指挥）】
- 关系图**无法在不伪造下**忠实呈现某 verified 值 → 标注或停机，绝不编造；实时模式**只能靠编造**才能演示（如离线确无实时检索能力）→ 如实标注限制或停机；需改 M010–M090 产物 / M080 demo fidelity / M070 产物 / 任何 §8 判据；材料无法去身份；任何只能靠虚构填的字段。
- **频率消融信号消失不是停机项**——如实改创新主张即可。

【交付】完成后：`src/scholarloop/gaps/frequency_ablation.py` + `src/scholarloop/demo/{graph.py,realtime.py}` + `docs/submission/**`（追加）；`pytest tests/ -q` 通过记录；`reports/m100/{gap_frequency_ablation.json,graph_fidelity.json,realtime_smoke.txt,secret_scan.json,validation_summary.json}`；写复盘；把 `100` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第十六次初查）。
