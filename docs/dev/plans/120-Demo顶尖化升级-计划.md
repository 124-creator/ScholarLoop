# 120 · Demo 顶尖化升级（可信交互）· 实施计划（Codex 执行简报）

- 状态：verified（2026-06-21 Router 人类终验 implemented→verified，依据第十八次初查 PASS：总指挥直接读 M020 原始 JSON+源文本独立重算 mismatch=0、亲起服务打 LIVE /api/verify_span 确认服务端高亮==M020 value 6/6 全对、轨迹零编造、M080 verify 复跑 PASS 未破、上游零污染。**Demo 达顶尖"可核验可信"水准：点证据即高亮原文那一句**）
- 修订轮次：1
- 日期：2026-06-21
- 轨道：重型
- 对应问题定义：`../../00-问题描述.md`（= 010，FROZEN）+ `../../00-赛题/...txt`（§3.1.4 结构化展示、§4 落地/专家分）
- 对应成功标准：`../spec/015-成功标准校准.md`（**S3 结构化 10% / S4 落地 15% / S5 合规**）
- 对应选定路线 / 评审：`../../02-评审分级.md`（H5 零虚构）
- 对应验证桩：`../spec/040-验证桩结论.md`（= PASS）
- 上游模块（**全部 verified/冻结只读**）：`020`（证据 char_span，点即核验底座）、`080`（demo 框架 + fidelity 承重，**扩展不改**）、`100`（关系图/实时，扩展）、`040/050/060/070`（排序/出处/泛化/空白候选数据）
- 关联复盘：`../retrospectives/120-Demo顶尖化升级-复盘.md`（待建）

> **前置（治理）**：本计划初始为 `draft`，**人类批准后**方可交 Codex。
> **网络调研依据（2026-06）**：顶尖学术搜索 Agent（Ai2 Paper Finder/Elicit/Consensus/Undermind）共性 = **展示完整推理轨迹 + 证据综合 + 结构化抽取**；AI Agent UX 黄金法则 = **渐进式披露推理、逐条置信、事实挂引用**；关键反直觉发现 = **「用户嘴上信引用却几乎不点开核对」→ 光有引用不够，要让证据真正可核验**；竞赛获奖差异 = **「人人能搭能跑的原型，差异在呈现 + 凭什么信它」**。**我们的杀手锏正是行业最缺的**：M020 字符级原文定位证据（fabrication=0）——别人的引用没人点，我们的证据点一下高亮到原文那一句。
> **诚实红线**：所有增强**忠实呈现零伪造**（高亮 span 必等于 M020 char_span、值必等于源文本切片）；推理轨迹**只 surface 流水线已做的事，零编造**；M010–M110 verified 产物冻结只读，新增走新文件、不改 M080 既有面板/fidelity；offline 默认、实时可选。

---

## 1. 模块目标

- **本模块解决什么**：把 Demo 从"忠实但朴素的查看器"提升到**顶尖的"可核验可信"交互体验**——以**点即核验的证据链**为中心（行业最缺、我们最强），加**Agent 推理/决策轨迹**与**视觉/交互打磨**，让评审一眼看懂、且**亲手点一下就信**。
- **对冻结成功标准的贡献**：
  - **S4 落地（15%）**：从"能跑"升到"可信且好用"，直击竞赛"凭什么信它"。
  - **S3 结构化（10%）**：推理轨迹 + 关系图 + 证据矩阵的渐进式结构化呈现。
  - **S5 / H5**：交互增强不破忠实——点即核验**本身就是 fabrication=0 的可视化证明**。
- **诚实性要求**：增强**不得**引入任何超 verified 证据的展示；高亮/轨迹/置信全部溯源 verified JSON；缺失仍标"需人工核验"。

## 2. 范围

- **本轮必须做（三支柱，均守忠实零伪造）**：
  1. **T1 · 点即核验证据链（杀手锏）**：交互——点任一证据字段 → 展开其**源论文对应字段文本**并**高亮 M020 `char_span` 那一段**；旁注 `status`（已有证据支持/需人工核验/存在争议）+ `source_field` + `confidence`。**核验断言**：高亮文本 == 源文本[char_span] == 字段 value（三者逐字相等，即 M020 fabrication=0 的现场可视化）。源文本来自 LitSearch 语料 title/abstract（只读）。
  2. **T2 · Agent 推理/决策轨迹面板**：渐进式披露一条查询的全链路——①查询拆解（M010 子查询）②检索/排序策略与理由（M040 排序 + 相关性标注）③证据接地（M020）④研究空白候选启发（M070，按 M110 口径标频率边界）。**每步数据溯源 verified 产物、零编造推理**（不是让 LLM 现编一段"思考"，而是把流水线真实做过的步骤结构化展示）。
  3. **T3 · 视觉/交互打磨**：精炼版式与信息层次、状态/置信视觉编码（色彩+图标一致语义）、关系图交互升级（hover/点选聚焦）、响应式；**轻栈不引重前端框架**（守 035 视觉红线，不喧宾夺主）。
  4. **合规 / 可复现 / 复盘**。
- **明确不做**：改 M010–M110 任何产物/源码行为/判据；改 M080 既有 demo 面板/`render.py`/`verify.py` 与其 fidelity（**新增**增强视图/端点）；编造证据/推理/置信；引重前端框架；把交互增强当超 verified 主张；放身份信息；为视觉牺牲忠实。
- **允许修改 / 新建的文件**：
  - 新建：`src/scholarloop/demo/interactive.py`（增强视图渲染 + 点即核验 + 轨迹）、`src/scholarloop/demo/source_text.py`（只读加载源论文文本供高亮）、demo 路由**新增**端点（如 `/pro`、`/api/verify_span`、`/api/trail`），可新增内联 CSS/JS（轻量、无框架）。
  - 新建测试：`tests/test_m120_*.py`（**不改** `test_m010..m110`）。
  - 新建产物：`reports/m120/**`（点即核验 fidelity、轨迹 fidelity、烟测、secret/identity 扫描、validation_summary）。
  - **不得**改动：FROZEN 件、`spike/**`、`reports/m010..m110/**`、M010–M110 源码、M080 既有 demo 面板/`render.py`/`verify.py`、各模块验收判据。

## 3. 现状与证据

- **点即核验底座已核实**：M020 `reports/m020/evidence/*.json` 每字段含 `value`/`status`/`source_field`/`char_span[start,end]`/`confidence`；`value == 源文本[char_span]`（M020 fabrication=0 已 verified）。源文本（title/abstract）在 LitSearch 语料只读可得。
- **轨迹数据已存**：查询拆解（M010/M080 assemble）、A-v2 排序 + 相关性标注（M040）、证据（M020）、空白候选（M070 + M110 频率边界口径）。
- **现状 Demo**：M080 忠实查看器（六面板）+ M100 关系图/实时；缺**交互核验、推理轨迹、视觉精炼**——正是顶尖差距。

## 4. 调研结论

- **来源**：Ai2 Paper Finder/Elicit/Consensus/Undermind 产品调研、AI Agent UX 2025-26 最佳实践、竞赛获奖 Demo 要素（见 §头部网络调研依据）。
- **可直接落地的结论**：
  1. **可核验 > 可引用**：点即核验把我们 fabrication=0 的优势变成评审亲手可验的体验。
  2. **渐进式披露推理轨迹**是顶尖 Agent 的标配信任手段。
  3. 视觉精炼降低认知负荷，但**不得喧宾夺主/牺牲忠实**。
- **对本计划的影响**：承重 = 点即核验忠实（高亮==char_span==value）+ 轨迹零编造 + 不破 M080 fidelity。

## 5. skills 选型与执行简报

- **选择的 skills**：无（交互前端 + 忠实校验）。
- **未选其它 skills 的理由**：承重在忠实呈现协议，不靠编排。
- **转译后的普通执行步骤（硬要求标【硬】 / 建议标【议】）**：
  1. 【硬】点即核验高亮 span **逐字等于** M020 char_span 且 == value；不匹配则不高亮、标"需人工核验"。
  2. 【硬】推理轨迹每步**溯源 verified 产物，零编造**。
  3. 【硬】M010–M110 + M080 既有面板/fidelity 冻结只读；新增走新文件/端点。
  4. 【硬】offline 默认、零密钥、零身份；缺失标"需人工核验"不补写。
  5. 【议】版式/配色/交互细节/JS 实现，在 §10 预算内定（轻栈无框架）。

## 6. 任务拆解

- [ ] **T1（不确定度：中·承重）点即核验证据链**：`demo/interactive.py`+`demo/source_text.py`+`/api/verify_span`；点字段→高亮源文本 char_span；产出 `reports/m120/span_fidelity.json`（高亮==char_span==value 的全量校验，mismatch=0）。
- [ ] **T2（不确定度：中）推理/决策轨迹面板**：`/api/trail` + 视图，渐进式披露拆解/检索/证据/空白；产出 `reports/m120/trail_fidelity.json`（每步溯源 verified，编造=0）。
- [ ] **T3（不确定度：中）视觉/交互打磨**：增强视图 `/pro`，版式/状态编码/关系图交互/响应式；烟测可运行。
- [ ] **T4（不确定度：低）合规 / 可复现 / 复盘**：offline 重放一致、无密钥/身份、上游 sha 未变、复盘含调研→落地对照。

## 7. 执行顺序与依赖

T1 点即核验（承重）→ T2 轨迹 → T3 打磨 → T4 收束。**T1 高亮与 char_span 不符且无法忠实呈现 → 标"需人工核验"或停机，绝不假高亮。**

## 8. 验收标准与证据映射

| 验收项 | 阈值 / 预期 | 验证命令或证据 | 对应任务 |
|---|---|---|---|
| **点即核验忠实（承重）** | 高亮文本逐字==M020 char_span==字段 value；mismatch=0 | `reports/m120/span_fidelity.json` | T1 |
| 推理轨迹零编造 | 每步数据溯源 verified 产物；编造=0 | `reports/m120/trail_fidelity.json` | T2 |
| 增强视图可运行 | 单命令起服务、`/pro` 可见、交互生效 | 烟测 `reports/m120/smoke.txt` | T3 |
| 不破 M080 fidelity | M080 既有面板/端点/fidelity 仍 PASS | 复跑 M080 verify | 全程 |
| offline / 零身份零密钥 | 默认离线 0-LLM；无学校/导师/密钥 | 扫描 | T4 |
| 上游未污染 | M010–M110 产物/源码未变 | sha/diff | 全程 |

## 9. 测试策略

- **代码任务是否采用 TDD**：是（T1 span 忠实、T2 轨迹溯源先写测试）。
- **Green 验证命令**：`pytest tests/ -q`；端到端起服务打 `/pro`、`/api/verify_span`、`/api/trail`；复跑 M080 verify 确认未破。
- **非代码任务等价证据**：span_fidelity + trail_fidelity + 烟测。
- **不得由执行方自行修改的验收测试**：点即核验忠实（高亮==char_span==value）、轨迹零编造、M080 fidelity 不破、上游冻结。

## 10. 执行方有界决策预算

### 可自行决定
- 版式/配色/图标语义/交互细节；轻量 JS 实现（无框架）；关系图交互方式；`/pro` 布局；source_text 加载与缓存。

### 必须停机上报
- 某证据字段**无法在不假高亮下**核验（char_span 与源文本不符）→ 标"需人工核验"或停机，绝不假高亮；推理轨迹**只能靠编造**才能填 → 上报；需改 M010–M110 产物 / M080 fidelity / 任何 §8 判据；需引重前端框架才能达成；材料无法去身份；任何只能靠虚构填的字段。

## 11. 风险、边界与回滚

- **核心风险（假可信）**：交互可能**伪造**核验（高亮一段不等于 char_span 的文本）。**红线** → 高亮严格等于 char_span 且 ==value，不符则不高亮 + 标"需人工核验"；`span_fidelity.json` mismatch=0。
- **轨迹编造红线**：只 surface 流水线真实步骤，不让 LLM 现编"思考"。
- **不破 fidelity 红线**：M080 既有面板/fidelity 复跑仍 PASS。
- **视觉红线**：轻栈不喧宾夺主（035），不为炫牺牲忠实/性能/可复现。
- **回滚**：本模块新增增强视图；失败仅废弃 `demo/{interactive,source_text}.py` 与 `reports/m120/**`，M080 demo 与所有 verified 证据不受影响。

## 12. 文档与治理同步

- **需要新建目录**：`reports/m120/`；`src/scholarloop/demo/` 下新增 `interactive.py`/`source_text.py`。
- **对应 AGENTS.md / CLAUDE.md**：更新 demo 说明（点即核验 + 轨迹 + 打磨：忠实零伪造、与 M080 baseline 分离）。
- **需更新的项目约定**：完成并经初查后，在 `000-决策日志.md` 追加 M120 交付与初查记录；提交物料/视频脚本可据此升级（后续）。

## 13. 交付要求

- **代码 / 文档**：`src/scholarloop/demo/{interactive.py,source_text.py}` + demo 新增端点。
- **测试输出**：`pytest tests/ -q` 通过；`reports/m120/{span_fidelity.json,trail_fidelity.json,smoke.txt}`；M080 verify 复跑 PASS。
- **复盘文件**：`../retrospectives/120-Demo顶尖化升级-复盘.md`（含网络调研→落地对照 + 忠实交互结论；**不得自行宣布 verified**，交总指挥初查）。
