# 120 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息。
> **核心特征**：Demo 顶尖化（可信交互）。承重 = **点即核验忠实**（高亮逐字==char_span==value、mismatch=0）。M010–M110 + M080 既有 demo 面板/fidelity 冻结只读，新增走新文件/端点、复跑 M080 verify 须仍 PASS。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/120-Demo顶尖化升级-计划.md`（状态 approved）——把 Demo 提到顶尖：以**"可核验的可信"**为中心。

【为什么这么做（网络调研依据）】
顶尖学术搜索 Agent（Ai2 Paper Finder/Elicit/Consensus/Undermind）共性 = 展示完整推理轨迹 + 证据综合；AI Agent UX 黄金法则 = 渐进式披露推理 + 逐条置信 + 事实挂引用；**关键反直觉发现 = 用户嘴上信引用却几乎不点开核对 → 光有引用不够，要让证据真正可核验**。**我们的杀手锏正是行业最缺的**：M020 字符级原文定位证据（fabrication=0）——别人的引用没人点，我们的证据**点一下高亮到原文那一句**。

【最高优先级 · 红线】
1. **点即核验忠实（承重）**：交互高亮的文本必须**逐字等于** M020 该字段的 `char_span` 切片，且 == 字段 `value`（三者相等）。**不符则不高亮 + 标"需人工核验"，绝不假高亮**（假可信比朴素更糟）。`span_fidelity.json` mismatch 必须=0。
2. **轨迹零编造**：推理/决策轨迹**只 surface 流水线真实做过的步骤**（拆解/检索/排序/接地的 verified 数据），**绝不让 LLM 现编一段"思考"**冒充推理。
3. **不破 M080**：M010–M110 + M080 既有 demo 面板/`render.py`/`verify.py`/fidelity **冻结只读**；增强走**新文件 + 新端点**；完成后**复跑 M080 verify 须仍 PASS**。
4. **offline 默认 / 零密钥 / 零身份 / 轻栈**：默认 0-LLM；不引重前端框架（守 035 视觉红线）；缺失标"需人工核验"不补写。

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/120-Demo顶尖化升级-计划.md`（**逐条照做**，§2/§6/§7/§8/§10/§11）
- `docs/dev/000-决策日志.md` 顶部「M120 批准」记录（三支柱 + 红线）
- **点即核验底座（只读）**：`reports/m020/evidence/*.json`——每 card 的 `fields.{title,recommendation_reason,supported_research_question,method,data_or_scenario,main_conclusion,limitations,...}` 含 `value`/`status`/`source_field`/`char_span[start,end]`/`confidence`；**`value == 源字段文本[char_span]`**（M020 fabrication=0 已 verified）。源字段文本（title/abstract）取自 LitSearch 语料（`src/scholarloop/corpus/litsearch.py` 的 `corpus_clean`，只读）。
- **轨迹数据（只读）**：M080 `src/scholarloop/demo/assemble.py`（已组装查询拆解/排序/证据/出处/空白视图）、`reports/m040`（排序+相关性标注）、`reports/m070/gaps_display.json`（空白候选，按 **M110 频率边界口径**：候选生成启发、非预测性）、`reports/m100/gap_frequency_ablation.json`（频率边界）。
- **demo 框架（扩展不改）**：`src/scholarloop/demo/{app.py,render.py,verify.py,graph.py,realtime.py}`（既有端点 `/`、`/api/*`、`/graph`、`/api/realtime`——**新增不改这些**）。

【本轮要做（三支柱 · 按 §6/§7 顺序）】
1. **T1 · 点即核验证据链（杀手锏 · 承重）** `src/scholarloop/demo/interactive.py` + `src/scholarloop/demo/source_text.py`（只读加载源论文 title/abstract）+ 新端点 `/api/verify_span`：
   - 交互：点任一证据字段 → 展开**源字段文本**并**高亮 `char_span` 那一段** + 旁注 `status`/`source_field`/`confidence`。
   - **校验**：对全部有 char_span 的字段断言 `源文本[char_span] == value`，逐字相等；产出 `reports/m120/span_fidelity.json`（mismatch=0）。char_span 为 null/不符的字段显式标"需人工核验"，不假高亮。
2. **T2 · 推理/决策轨迹面板** 新端点 `/api/trail` + 视图：渐进式披露一条查询全链路——①查询拆解（M010 子查询）②检索/排序策略与相关性标注（M040）③证据接地（M020）④研究空白候选启发（M070，**标 M110 频率边界**）。**每步数据溯源 verified 产物**；产出 `reports/m120/trail_fidelity.json`（每步挂来源、编造=0）。
3. **T3 · 视觉/交互打磨** 增强视图端点 `/pro`：精炼版式与信息层次、状态/置信视觉编码（色彩+图标一致语义，沿用证据状态四类）、关系图交互升级（hover/点选聚焦，复用 `/api/graph` 数据）、响应式；**轻量内联 CSS/JS、无前端框架**。
4. **T4 · 合规 / 可复现 / 复盘**：offline 重放一致；无密钥/身份；上游 M010–M110 sha 未变；**复跑 M080 verify 仍 PASS**；全量 `pytest tests/ -q` 通过；写 `docs/dev/retrospectives/120-Demo顶尖化升级-复盘.md`（网络调研→落地对照）。

【硬红线（不得改动）】
- §8 承重**点即核验忠实**：高亮逐字==char_span==value、`span_fidelity.json` mismatch=0；不符不高亮+标"需人工核验"。
- **轨迹零编造**：只 surface 真实步骤、溯源 verified。
- **不破 M080**：既有面板/`render.py`/`verify.py`/fidelity 只读、复跑仍 PASS；增强走新文件/端点。
- offline 默认、零密钥、零身份、轻栈无框架、缺失标"需人工核验"不补写、不为视觉牺牲忠实。
- 只允许写：`src/scholarloop/demo/{interactive.py,source_text.py}`（+ app 路由**新增**端点，不改既有处理）、`tests/test_m120_*.py`（**不改** `test_m010..m110`）、`reports/m120/**`、复盘文件。

【可自行决定（§10 预算内）】版式/配色/图标语义/交互细节；轻量 JS 实现（无框架）；关系图交互方式；`/pro` 布局；source_text 加载与缓存键。

【必须停机上报（写 `reports/m120/` 停机报告，交总指挥）】
- 某证据字段 char_span 与源文本**不符、无法忠实核验** → 标"需人工核验"或停机，**绝不假高亮**；推理轨迹**只能靠编造**才能填 → 上报；需改 M010–M110 产物 / M080 fidelity / 任何 §8 判据；需引重前端框架才能达成 → 上报；材料无法去身份；任何只能靠虚构填的字段。

【交付】完成后：`src/scholarloop/demo/{interactive.py,source_text.py}` + demo 新增端点；`pytest tests/ -q` 通过记录；`reports/m120/{span_fidelity.json,trail_fidelity.json,smoke.txt,secret_scan.json,validation_summary.json}`；**M080 verify 复跑 PASS 证据**；写复盘；把 `120` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第十八次初查）。
