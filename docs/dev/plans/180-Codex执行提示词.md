# 180 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息。
> **核心特征**：纯 i18n 措辞优化——把实时卡"需人工核验"从"像派作业"改成"讲零幻觉卖点"。**承重 = 措辞讲价值且语义诚实（绝不把"未核实"夸大成"已核实"）+ verified 内容逐字不变。** 零逻辑改动。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/180-实时卡零幻觉措辞优化-计划.md`（状态 approved · 人类选定方案 A「改措辞」）——把实时结果卡的"需人工核验"措辞改成"讲零幻觉卖点"，**只改显示措辞、语义不变、不碰任何 verified 内容**。

【背景（人类实测旗舰 demo 后指出）】
实时结果卡的「作者/年份/DOI 需人工核验（除非已有离线核验缓存）。」措辞**像在给评委派作业/暗示半成品**。**本质澄清**：实时对新问题为快+离线**不现场调连接器**，作者/年份/DOI 语料里本就没有 → 系统**诚实标「待核验」、绝不编造假作者假 DOI**（这正是赛题反对的"大模型幻觉"，是我们最强卖点）；30 个基准查询已通过 OpenAlex 核验并显示真实值（M160 接入）。**目标 = 把这句改成"讲价值"的说法，让评委一眼读出"这是零幻觉的严谨，不是缺陷"。**

【最高优先级 · 红线】
1. **措辞讲价值且语义诚实（承重）**：把"需人工核验"框架从"待办/缺陷"转为"零臆造/绝不编造"的卖点；**但绝不把"未核实"夸大成"已核实"**——实时这三字段确实没核实，表述转正向但**事实不变**（仍是待核验，只是讲清"我们绝不臆造"）。
2. **verified 内容逐字不变**：**不改任何 verified 数值（0.1312/0.0964/0.1972 等）、证据原文、char_span、论文标题/摘要**；i18n 数值未被译。
3. **零逻辑改动**：**不改** `realtime.py` 是否调连接器的逻辑（仍不现场调）、`source_text.py`/`interactive.py` 点即核验忠实逻辑、检索逻辑/权重；只动 i18n 显示文案（+ 必要时 design.py 的 JS 兜底 fallback 串，不改逻辑）。
4. **EN 同步 + 轻栈 + 零密钥零身份**：中英两版都改、语义一致；不引框架/外链；零密钥/身份。

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/180-实时卡零幻觉措辞优化-计划.md`（**逐条照做**，§2/§6/§10）
- `docs/dev/000-决策日志.md` 顶部「M180 批准」记录（本质澄清 + 红线 + 目标文案）
- **改写对象**：`src/scholarloop/demo/i18n.py`（`realtime_manual_meta` 等文案键）；必要时 `src/scholarloop/demo/design.py`（仅同步 JS `tr(key, fallback)` 的 fallback 串，不改逻辑）
- **语义事实（只读）**：`src/scholarloop/demo/realtime.py:112-113`（实时对 authors_year/source_or_doi 返回 `status="需人工核验"`，**不现场调连接器，事实不变**）

【本轮要做（§6/§7 顺序）】
1. **T1 · 改实时卡 manual_meta 措辞** `i18n.py` `realtime_manual_meta`（zh+en）改为讲价值版（可在 §10 内润色，但守"零臆造、不谎称已核实"）：
   - zh 目标：「作者 / 年份 / DOI：本系统坚持**零臆造**——实时新问题这三项默认标「待核验」、绝不编造；30 个基准查询已通过 OpenAlex 核验并展示真实值。」
   - en 目标：「Authors / year / DOI: ScholarLoop never fabricates — for live queries these stay 'to be verified' instead of guessed; the 30 benchmark queries already show OpenAlex-verified values.」
2. **T2 · 审计其余"需人工核验"措辞**：检查点即核验空态、证据卡占位等，凡读着像"派作业"的统一改为"零幻觉/绝不臆造"价值框架（点即核验空态 `零幻觉：…绝不高亮绝不猜测` 已是价值版，保留为范式）；状态徽章短标 `需人工核验` 可保留（布局考虑），靠周边文案讲清价值。产出 `reports/m180/localization_polish.json`（改后文案到位 + verified 不被改 + 语义诚实不夸大：断言无"已核实/verified"类误导词加到实时三字段上）。
3. **T3 · 承重复验 + 合规 + 复盘**：复跑 `build_i18n_coverage`（verified 数值未被译）+ `build_studio_fidelity`（span_mismatch=0）PASS；复核 `reports/m040/results.json` sha=6eb81c83、`reports/m060/results.json` sha=bb309155 不变；无密钥/身份；上游 reports/m010..m170 未变；全量 `pytest tests/ -q` 通过；写 `docs/dev/retrospectives/180-实时卡零幻觉措辞优化-复盘.md`（改前后措辞对照 + 语义诚实证据）。

【硬红线（不得改动）】
- §8 承重：①措辞讲价值且**语义诚实**（不把"未核实"夸大成"已核实"）；②verified 数值/证据/标题摘要逐字不变；③`realtime/source_text/interactive` 逻辑与点即核验忠实不改、studio_fidelity 仍 PASS。
- 只允许写：`src/scholarloop/demo/i18n.py`（+ 必要时 `design.py` fallback 同步、不改逻辑）、`tests/test_m180_*.py`（**不改** `test_m010..m170`）、`reports/m180/**`、复盘文件。**不改** `realtime.py`/`source_text.py`/`interactive.py`/`studio.py`/`assemble.py`/`enrich_view.py` 逻辑、`retrieval/`/`rank/`、M010–M170 产物、各判据、任何 verified 数值。

【可自行决定（§10 预算内）】文案润色措辞（守"零臆造、不谎称已核实"）；状态徽章短标保留/微调。

【必须停机上报（写 `reports/m180/` 停机报告）】
- 措辞**只能靠把"未核实"说成"已核实"才好看** → 停机；需改 verified 值/忠实逻辑/检索逻辑；需改 M010–M170 产物或判据；材料无法去身份。

【交付】完成后：`demo/i18n.py`（+ 必要时 design.py fallback）；`pytest tests/ -q` 通过记录；`reports/m180/{localization_polish.json,i18n_coverage.json,studio_fidelity.json,frozen_eval_invariance.json,smoke.txt,secret_scan.json,validation_summary.json}`；写复盘；把 `180` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第二十四次初查）。
