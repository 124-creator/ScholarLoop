# 030 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥，只引用环境变量名。
> 凭证仅**可选实时模式**（T4）需要；默认离线基准模式 **0 LLM 调用**，不需要凭证。需要时沿用 M010 已建的 `src/scholarloop/config.py`（import 时自加载 `secrets/llm.env.local`），只读、不改、不回显。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次任务是执行**已批准**的计划
`docs/dev/plans/030-Web闭环演示-计划.md`（状态 approved，修订轮次 1）——构建 **Web 闭环演示（科研证据链 Demo）**（第三个业务模块）。

【唯一真源】先读这些文件，以它们为准，不要凭会话臆测：
- `docs/dev/plans/030-Web闭环演示-计划.md`（**逐条照做**，尤其 §2 范围、§4 调研结论、§6 任务、§8 验收、§10 决策预算、§11 风险）
- `00-问题描述.md`（§技术形态「Web 智能系统」、§比赛展示成功标准、§out-of-scope「不做只返回标题列表 / 不做只好看缺证据链」）、`docs/dev/spec/015-成功标准校准.md`（S3/S4）、`docs/dev/spec/035-选定路线冻结.md`（§4 边界「不把页面视觉置于证据链之上」）
- 上游 verified 产物（**只读消费**）：`reports/m010/results.json`（拆解 + scholarloop_a 排序 + reason + 效率）、`reports/m020/evidence/*.json`（cards 10 字段+status+char_span、matrix 论文×判据、citation_graph）；`src/scholarloop/{config,corpus,evidence,llm}`（实时模式才用，**不改其行为**）

【本次要做（按 §6 顺序）】
0. **后端骨架 + 只读数据层**（`src/scholarloop/web/data.py`）：`list_queries()`（枚举有 M020 证据的查询 + 演示查询）、`get_query_doc(qid)`（合并 M010 拆解/排序 + M020 证据为一个视图模型）、`get_paper_meta(corpusid)`。只读 `reports/m010|m020/**` 与语料。
1. **API 路由**（`src/scholarloop/web/app.py`）：`GET /api/queries`、`GET /api/queries/{qid}`、`GET /healthz`；**预计算优先、基准请求 0 LLM**。
2. **前端页面**（`web/templates/**` + `web/static/**`，服务端模板或原生 JS，**不引重框架**）：查询输入/选择 → 拆解（子查询+判据）→ 排序清单（score+reason）→ 证据矩阵表（论文×判据，✅+可定位片段）→ 逐篇 10 字段卡（**4 类证据状态徽标醒目**）。
3. **忠实呈现 / 零伪造渲染保证**（与承重 W2）：渲染层断言「页面/接口暴露的字段值 == M020 JSON 对应值」，**无新增字段**；作者/年份/来源/DOI **固定**显示「需人工核验 + 在线连接器提示」，**页面绝不出现未在源 JSON 中的字段值**。
4. **限额实时模式（可选）**：开关**默认 off**；开启时新查询走 pipeline+evidence，带缓存 + token/延时上限，超 `015` S2 预算即**拒绝并提示**。需 import `scholarloop.config`（env 为空先自加载，不构成停机理由）。**若无法在预算内有界 → 保留离线模式并停机上报**。
5. **跨域演示数据**：用既有离线 pipeline+evidence 为 ≥1 个碳价/AI 科研演示查询生成证据文档（有界，落 `reports/m030/demo/`），纳入前端演示集；结构与基准一致、零伪造。
6. **忠实呈现校验桩 + smoke/e2e + 复现**：对抽样查询断言渲染负载 == M020 JSON、状态徽标齐全、无伪造字段；两次启动渲染一致。产出 `reports/m030/web-verification.json` + `reports/m030/smoke_console.txt`。
7. **合规 / 复盘**：全仓 grep 无密钥落盘；写 `docs/dev/retrospectives/030-Web闭环演示-复盘.md`；如确定技术栈，回填 `AGENTS.md` §命令（启动/测试命令）。

【硬红线（不得改动）】
- §8 承重：**(W1) 单命令可运行**（基准查询全部可访问，smoke 端点 200）；**(W2) 忠实呈现零伪造**——抽样查询渲染负载字段值逐字等于 M020 JSON，无新增/臆造字段，author/year/DOI 恒为「需人工核验+hint」。
- **默认离线 0-LLM**：基准集每请求 0 LLM 调用、确定性；实时模式默认关闭、限额。
- **上游只读**：不得改 `reports/m010/**`、`reports/m020/**`、`src/scholarloop/{evidence,pipeline,eval,rank,retrieval,query,corpus,llm,config,utils}` 既有行为，不得改 `010`/`020` 验收判据、`040`、任何 FROZEN 件、`spike/**`。
- **不把视觉置于证据链之上**（035 §4）；不做鉴权/数据库/部署基建；页面任何形式的伪造一律禁止。
- 只允许写 `src/scholarloop/web/**`、`tests/**`（新增 `test_m030_*.py`，**不改** `test_m010_*`/`test_m020_*`）、`reports/m030/**`。
- **绝不把密钥写入任何文件**；只经 config 读取（仅实时模式）；异常对密钥脱敏。

【可自行决定（§10 预算内）】后端框架（FastAPI / Flask）与端口；前端模板/样式与组织；是否提供 citation_graph 极简可视化（有界、Top-N 内部）；演示查询选题；`src/scholarloop/web/` 内部文件组织与局部命名。

【必须停机上报（写 `reports/m030/` 停机报告，交总指挥，不自行扩范围）】
- 实时模式无法在 `015` S2 预算内有界（T4）；需要鉴权/数据库/部署基建才能「可运行」；需要在线付费/受限 API 实调用才能填字段；忠实呈现校验无法通过（页面与 M020 JSON 不一致且无法对齐）；需改 M010/M020 任何产物或 §8 判据；任何只能靠虚构才能填的展示字段。

【交付】完成后：`src/scholarloop/web/**`（多小文件）+ 子目录 AGENTS/CLAUDE 说明 + 启动命令；`pytest tests/ -q` 通过记录；smoke/e2e 端点记录；`reports/m030/**`（含 `web-verification.json`、`demo/`）；写复盘 `docs/dev/retrospectives/030-Web闭环演示-复盘.md`；把 `030` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查。
