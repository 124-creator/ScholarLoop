# 130 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息。
> 联网授权沿用 M050/M060（实时模式需 LLM 端点）。
> **核心特征**：Demo 旗舰级全面顶尖化——切题实时搜索 + 顶尖观感 + 关系图稳定。承重 = ①图确定性稳定（两渲染坐标相等）②点即核验/基准忠实（mismatch=0）。M080/M120 既有逻辑/fidelity 冻结只读、复跑仍 PASS。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/130-Demo旗舰级全面顶尖化-计划.md`（状态 approved）——把 Demo 从每一个角度升级到**顶尖旗舰水准**。

【为什么（人类指令 + 调研）】
人类体验现有 demo 后要求"无论从哪个角度都升级到顶尖"：①当前只能选 30 基准查询、没把**"问任意问题自主搜索"（赛题 §3.1 核心）**做成主体验——切题缺口；②观感要顶尖；③**关系图线条要稳定**。调研结论：顶尖观感靠**设计令牌统一视觉语言 + 微交互/状态设计**；**关系图抖动根因 = 浏览器端跑力导向模拟 → 顶尖解 = 确定性算一次/坐标冻结/静态 SVG + viewBox（端侧零模拟=构造零抖动、resize 只缩放不重排）**。

【最高优先级 · 红线】
1. **关系图确定性稳定（承重·人类点名）**：布局**确定性算好、坐标冻结**，**端侧不跑任何力导向/物理模拟**（=构造上零抖动）；节点碰撞间距（标签不重叠）；边锚定节点中心、路径稳定；**viewBox SVG**（resize 只缩放不重排）；hover/focus 高亮邻居**仅切 CSS 类、不改坐标**（无闪烁）。**断言**：同数据两次渲染 SVG 坐标**逐字相等**、所有边锚定到存在的节点、无 NaN 坐标（写入 `graph_determinism.json`）。
2. **点即核验/基准忠实（承重）**：旗舰内点即核验**复用 M120 `source_text.verify_value_span`**——高亮**逐字等于** char_span 切片且 == value，不符则不高亮+标"需人工核验"；基准展示值**逐字等于 verified JSON**。`studio_fidelity.json` mismatch=0。
3. **实时诚实**：实时结果**明确标"实时·非确定性·非 verified 承重"** + **成本披露**（调用/token/延时）+ **失败优雅回退不编造**（实时关闭/LLM 不可用/超时→显式提示，绝不假造推荐）。
4. **不破 M080/M120 + 轻栈 + 零密钥零身份**：M080 `render.py`/`verify.py`/既有 `/`、M120 `interactive.py`/`source_text.py`/既有 `/pro` **冻结只读**，完成后**复跑两者 verify 须仍 PASS**；**不引重前端框架（React/Vue 等），仅轻量内联 CSS/JS**；offline 默认；零密钥/身份；缺失标"需人工核验"/空状态不补写。**绝不为观感牺牲忠实/稳定/可复现。**

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/130-Demo旗舰级全面顶尖化-计划.md`（**逐条照做**，§2/§6/§7/§8/§10/§11）
- `docs/dev/000-决策日志.md` 顶部「M130 批准」记录（三支柱 + 红线）
- `00-赛题/...txt` §3.1（查询理解→多策略检索→排序→结构化展示，实时主体验要展示这套）
- **实时路径（复用，不重建）**：`src/scholarloop/demo/realtime.py`（`run_realtime_query(query)`：LLM 拆解→BM25+DenseV2+子查询→A-v2 融合+cross-encoder→top 结果，搜 LitSearch 64k，成本披露，失败优雅回退，默认 `SCHOLARLOOP_REALTIME_ENABLED` 关）——本轮**把它包成旗舰主体验 UX**，不改其检索逻辑。
- **点即核验/数据（复用，不改）**：`src/scholarloop/demo/{source_text.py,interactive.py,assemble.py,graph.py,app.py}`、`reports/m020/evidence/*`、`reports/m070/gaps_display.json`（按 **M110 频率边界口径**：候选启发非预测）、`reports/m100/gap_frequency_ablation.json`。

【本轮要做（三支柱 · 按 §6/§7 顺序）】
1. **T2 先行 · 设计系统/观感** `src/scholarloop/demo/design.py`：**设计令牌**（CSS 变量：色板/间距阶梯/字体阶梯/圆角/阴影/动效时长）；精炼组件（卡片/徽章/表格/输入/按钮/标签页）；**微交互**（hover/focus/平滑过渡，非抖动）；**状态设计全覆盖**（loading/empty/error/timeout）；信息层次+留白；**响应式**（桌面/窄屏）；可访问性（语义标签/对比/键盘焦点）。轻量内联、无框架。
2. **T1 · 实时自主搜索主体验（切题）** `src/scholarloop/demo/studio.py` + `/api/search?q=...`：旗舰页 hero 输入框 → 调 `run_realtime_query` → 展示**拆解子查询 + 排序结果（标题/摘要/理由/分数）+ 成本卡**；**"检索中" loading 状态**；**优雅回退**（disabled/LLM 不可用/超时→显式提示 + 引导如何启用，不编造）；明确"实时·非 verified"标注，与基准 verified 区分。
3. **T3 · 关系图稳定化** `src/scholarloop/demo/graph_layout.py` + `/api/graph_stable`：**确定性布局**（圆形/径向/网格/**种子固定力导向算一次后冻结**皆可，只要确定性+不重叠）→ 输出冻结坐标 → 静态 SVG（viewBox）；边锚定节点中心、语义着色（如 future_fill）；hover 高亮邻居仅切类；数据来自 `gaps_display.json`（M110 边界），缺失空状态。产出 `reports/m130/graph_determinism.json`（两渲染坐标相等、边锚定有效、无 NaN）。
4. **T4 · 整合 + 忠实校验（承重）**：旗舰 `/studio` 统一三块——实时搜索 + 基准查询浏览（含**点即核验**复用 M120 校验）+ 稳定关系图 + 推理轨迹；产出 `reports/m130/studio_fidelity.json`（点即核验 mismatch=0、基准值==verified JSON）。
5. **T5 · 合规 / 可复现 / 复盘**：**复跑 M080 verify + M120 span/trail fidelity 须仍 PASS**；offline 重放一致；无密钥/身份；上游 M010–M120 sha 未变；全量 `pytest tests/ -q` 通过；写 `docs/dev/retrospectives/130-Demo旗舰级全面顶尖化-复盘.md`（调研→落地对照 + 含旗舰截图/交互说明）。

【硬红线（不得改动）】
- §8 承重①**图确定性稳定**（两渲染坐标逐字相等、端侧无模拟、边锚定有效、无 NaN）；②**点即核验/基准忠实**（高亮==char_span==value mismatch=0、基准值==verified JSON）。
- 实时**诚实**（非 verified 标注+成本披露+失败优雅回退不编造）。
- **不破 M080/M120**：既有逻辑/`/`/`/pro`/fidelity 复跑仍 PASS；轻栈无前端框架。
- offline 默认、零密钥、零身份、缺失标"需人工核验"/空状态不补写、不为观感牺牲忠实/稳定。
- 只允许写：`src/scholarloop/demo/{studio.py,graph_layout.py,design.py}`（+ app 路由**新增**端点，不改既有处理）、`tests/test_m130_*.py`（**不改** `test_m010..m120`）、`reports/m130/**`、复盘文件。

【可自行决定（§10 预算内）】设计令牌取值/配色/字体阶梯/动效；旗舰版式与组件；确定性布局算法（确定性+不重叠即可）；微交互轻量 JS；缓存键；`/studio` 信息架构。

【必须停机上报（写 `reports/m130/` 停机报告，交总指挥）】
- 实时**只能靠编造**才能演示（LLM 端点不可用且无法诚实回退）→ 标限制或停机；点即核验某字段 char_span 不符 → 标"需人工核验"不假高亮；关系图**无法做到确定性**（坐标随机/抖动）→ 修到确定性或停机，**绝不交抖动件**；需改 M010–M120 产物 / M080/M120 fidelity / 任何 §8 判据；需引重前端框架；材料无法去身份；任何只能靠虚构填的字段。

【交付】完成后：`src/scholarloop/demo/{studio.py,graph_layout.py,design.py}` + demo 新增端点；`pytest tests/ -q` 通过记录；`reports/m130/{graph_determinism.json,studio_fidelity.json,search_smoke.txt,smoke.txt,secret_scan.json,validation_summary.json}`；**M080 verify + M120 fidelity 复跑 PASS 证据**；写复盘；把 `130` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第十九次初查）。
