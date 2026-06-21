# 070 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥，只引用环境变量名。
> 联网授权沿用 M050/M060（Codex 可联网/浏览器控制）。
> **核心特征**：本模块是**条件触发**件，**T0 第一步即补建并通过 schema 桩（make-or-break）**——桩不过则停机、不建主体。这是全模块最可能正当停机于 T0 的一个；诚实停机优于硬凑创新。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/070-研究空白发现层-计划.md`（状态 approved）——构建**研究空白发现层**（第七个业务模块），补 S4 **创新（15%）** 的核心差异化件。**人类已拍板方案 A：结构化检测 + 接地叙述 + 预测性承重**。

【最高优先级 · 治理 gate（先读再动手）】
035 第 4 步「研究空白层」是**条件触发 = schema 桩通过**，而 `030 §4.1.3` 原定的 schema spike **从未建**（030 明确延后）。因此本模块**第一步（T0）就是补建并通过这个 schema 桩**：先用小样本证明"结构化空白候选 + 预测性验证"可成立——**过去时间切片上检出的空白，被未来留出切片的真实论文填补的比例，配对显著 > 随机概念对基线（CI 不含 0 或置换 p<0.05）**。**桩不过即停机上报、绝不建主体**（完全复刻 040 验证桩 gate 整个项目的纪律）。如果结构化空白被证明**无预测效力**，就如实写停机报告说"研究空白发现不具可证伪信号"——**绝不**用 LLM 叙述冒充发现、绝不自标注空白价值来硬凑通过。

【唯一真源】先读这些，以它们为准，不要凭会话臆测：
- `docs/dev/plans/070-研究空白发现层-计划.md`（**逐条照做**，尤其 §2 范围、§6 任务、§7 顺序、§8 验收、§10 决策预算、§11 风险）
- `docs/dev/000-决策日志.md` 顶部「2026-06-20 · M070 批准」审批记录（人类授权范围 + 红线 + 诚实停机条件）
- `docs/dev/spec/015-成功标准校准.md`（S4 创新点名"研究空白发现"、S5 证据状态）、`docs/dev/spec/035-选定路线冻结.md`（第 4 步条件触发 + schema 桩前置）、`02-评审分级.md`（X1 不自标注、X2 同候选池）
- 上游 verified 产物（**只读复用，不改**）：
  - RealScholarQuery 语料/查询/gold：`reports/m060/cache/realscholarquery/corpus.jsonl`（字段含 `corpusid`/`arxiv_id`(形如 "2404.00001"，**YYMM 可时间切片**)/`title`/`abstract`）、`reports/m060/raw/query_records/RealScholarQuery_*.json`（字段含 `query_id`/`split`/`resolvable_gold`/`full_gold_count`/`pool_ids`）、RealScholarQuery gold 的 `source_meta.published_time`（形如 "20241001"）
  - LitSearch 语料：`src/scholarloop/corpus/litsearch.py`（**注意**：当前 `load_corpus` 只读 `["corpusid","title","abstract"]` 三列，**未加载 `citations`**——见下「信号源」段的硬约束）
  - M020 证据矩阵接地范式：`src/scholarloop/evidence/**`、`reports/m020/evidence/*.json`（接地叙述的范式参考）
  - 评测协议：`src/scholarloop/eval/run_benchmark2.py`（同候选池/bootstrap/置换/metric/H5 写法可借鉴）

【方案 A 的三件套（人类拍板，照此实现）】
1. **结构化检测（确定性）** 检出空白候选，三类信号：
   - **组合空白**：两子主题/概念各自高频但近乎不共现（概念抽取须**确定性**：离线 n-gram / 受控词表 / 离线 KeyBERT，**不**让 LLM 主观判定"是不是空白"）。
   - **引用空白**：高被引论文邻域覆盖稀疏（用 LitSearch `citations`——**前提是该列存在**，见下硬约束）。
   - **时间空白**：曾活跃后沉寂的主题（用 RealScholarQuery `arxiv_id` 的 YYMM / gold 的 `published_time` 做时间切片）。
2. **接地叙述（LLM 只解释，不新增事实）**：LLM 仅对检出候选所**关联的真实论文**做自然语言说明；输出挂证据溯源（论文 id、共现/引用/时间计数）；**叙述提及的论文 id 必须全部在候选证据集内**（池外/虚构 = 0）。
3. **预测性承重（make-or-break）**：在"过去切片"检出空白，验证被"未来留出切片"真实论文填补的比例**配对显著 > 随机概念对基线**（bootstrap≥10000 / 置换，CI 不含 0 或 p<0.05）。

【信号源（已核实事实 + 硬约束）】
- RealScholarQuery：`arxiv_id` 形如 "2404.00001" → **YYMM=2404 可时间切片**；gold `source_meta.published_time` 形如 "20241001"；语料/查询已缓存在 `reports/m060/`，**优先离线复用、不重新联网**。
- LitSearch `citations`：**当前 `corpus/litsearch.py` 未加载该列**。引用空白信号**仅当**你确认 `corpus_clean` parquet 实际含 `citations`（或等价被引/引用字段）时才可用。**【硬约束】** 若该列不存在/不可得 → **引用空白信号降级或弃用**，在 T0 桩用其余信号（组合/时间）证明预测效力；**绝不**为了凑"引用空白"去联网抓取或编造引用关系。三类信号**至少一类**在 T0 桩展现显著预测效力即可建主体；**一类都不显著 → 停机**。
- 概念/主题抽取必须**确定性、可复现**（temperature=0/seed），口径写入产物；时间切片边界与随机基线构造在 §10 预算内自定并落盘依据。

【本轮要做（按 §6/§7 顺序，桩不过即停于 T0）】
0. **T0 · schema 桩（gate · make-or-break）**：小样本定义空白输出 schema（每条候选**带证据溯源**：关联论文 id + 共现/引用/时间计数）；在**时间切片**上检测组合空白（及可用的其它信号）；验证**预测效力**（过去检出被未来填补率 vs 随机概念对基线）**显著**。产出 `reports/m070/spike/gap_schema_spike.json` + 结论。**【停机】** 预测效力不显著 / 需自标注价值才成立 / 概念抽取无法确定性化 / 三类信号一类都不可用 → 写停机报告，**不建主体**。
1. **T1 · 结构化检测器** `src/scholarloop/gaps/detect.py`：实现可用的空白信号（确定性、缓存）；单测覆盖检测可复现 + 证据溯源完整（`tests/test_m070_*.py`）。
2. **T2 · 接地叙述层** `src/scholarloop/gaps/narrate.py`：LLM 仅对候选关联真实论文叙述，挂溯源；**fabrication 校验**——叙述提及的论文 id 必在候选证据集内，越界/虚构 = 0（落 `results.json.narration_out_of_evidence=0`）。
3. **T3 · 预测性承重评测**（make-or-break）`src/scholarloop/eval/run_gaps.py`：全量跑预测效力 + bootstrap(≥10000)/置换 + 随机概念对基线；产出 `reports/m070/results.json` + `significance.json` + `评测报告.md`。
4. **T4 · 结构化展示对接**：空白结果导出为**列表 + 关系/矩阵**结构（承接 S3/B-lite 形态，**不**做大规模交互知识图谱），落 `reports/m070/gaps_display.json`（区分"已有证据支持/证据不足/存在争议"——S5）。
5. **T5 · 合规 / 可复现 / 复盘**：无密钥；缓存可离线重放一致；写 `docs/dev/retrospectives/070-研究空白发现层-复盘.md`（**空白发现成立/不成立都如实**）。

【硬红线（不得改动）】
- **schema 桩（gate）**：结构化空白预测效力**显著 > 随机基线**（CI 不含 0 或 p<0.05），schema 含证据溯源——**桩不过则停机、不建主体**。
- **承重墙（S4）**：全量预测性评测——过去检出空白被未来论文填补率**配对显著 > 随机概念对基线**。
- **X1 不自标注**：空白只用**操作化结构定义**（共现/引用/时间）+ 预测性验证，**绝不**让专家或 LLM 自标注"这是有价值的空白"。
- **H5 零虚构**：LLM **只接地叙述真实论文，零新增事实**——不新增任何论文/DOI/作者/年份；叙述提及 id 全在候选证据集内（越界=0）。
- **S5 证据状态**：区分"已有证据支持 / 证据不足 / 存在争议"。
- **确定性 / 同语料**：temperature=0/seed、bootstrap≥10000/置换、原始落盘——继承 M040/M060 不放宽。
- **上游冻结只读**：不得改 `reports/m010|m020|m030|m040|m050|m060/**`、M010–M060 既有源码行为、A-v2 配置、各模块验收判据、FROZEN 件、既有 `spike/**`（新建写在 `spike/gaps/`）。
- 只允许写：`src/scholarloop/gaps/**`、`src/scholarloop/eval/run_gaps.py`、`spike/gaps/**`、`tests/test_m070_*.py`（**不改** `test_m010..m060`）、`reports/m070/**`、复盘 `docs/dev/retrospectives/070-研究空白发现层-复盘.md`。

【可自行决定（§10 预算内）】概念/主题抽取实现（离线 n-gram / 受控词表 / 离线 KeyBERT）；时间切片边界与随机基线构造；缓存键；`gaps/` 文件组织与局部命名；三类信号中实际采用哪些（至少一类须在 T0 桩显著）。所有有界决策落盘依据。

【必须停机上报（写 `reports/m070/` 停机报告，交总指挥，不自行扩范围）】
- **schema 桩预测效力不显著 > 随机**（研究空白无可证伪信号）——这是真实信号，如实上报，由人类决定（接受"研究空白发现不成立"的诚实结论 / 换信号 / 降级为纯结构化统计展示而**不称"发现"**）；
- 需**自标注空白价值**才能成立（X1 红线）；
- LLM 叙述需**新增论文/事实**才能填字段（H5 红线）；
- 三类信号**一类都不可用/不显著**；
- 概念抽取无法确定性化（只能靠 LLM 主观）；
- 样本量不足以做显著性；
- 需改 M010–M060 任何产物或 §8 任一判据；
- 任何只能靠**虚构**才能填的字段。

【交付】完成后：`src/scholarloop/gaps/**` + `eval/run_gaps.py` + `spike/gaps/run_gap_spike.py`；`pytest tests/ -q` 通过记录；schema 桩结论 `reports/m070/spike/gap_schema_spike.json`；预测性评测产物 `reports/m070/{results.json,significance.json,评测报告.md,gaps_display.json}`（含 X1 operational_definition、H5 narration_out_of_evidence=0 协议标记、可离线重放缓存）；写复盘 `docs/dev/retrospectives/070-研究空白发现层-复盘.md`（含"空白发现成立/不成立"的诚实结论）；把 `070` 状态推进为 `implemented`（若停机于 T0 则保持 `approved` 并附停机报告）。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第十二次初查）。
