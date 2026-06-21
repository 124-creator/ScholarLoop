# 020 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥，只引用环境变量名。
> 凭证：M010 已建 `src/scholarloop/config.py`，import 时自加载 `secrets/llm.env.local`；本模块**直接 import 复用**，不重建、不改它。

---

## 端点凭证（沿用 M010，已解决）

本模块的字段抽取需要三项凭证：`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`（DeepSeek，`deepseek-v4-flash`；推理模型，`max_tokens` 给足 ≥512，读 `message.content`，空 / `finish_reason=length` 响应隔离不复用）。

- 注入方式：`src/scholarloop/config.py` 在 import 时若 env 缺失则从 `secrets/llm.env.local` 读 `KEY=VALUE` 注入 `os.environ`。M010 已实测生效（`reports/m010/llm_precheck.json` 三项 True、真实调用成功）。
- 你运行于 IDE 插件 / 桌面 App，外部终端 `$env:` 不进你的进程——三项 env 在你检查时为空是**预期**，**不构成停机理由**；先 `import scholarloop.config` 让它自加载，端点预检在 import 之后做。
- 凭证红线：`secrets/llm.env.local` **只读取、不创建、不修改、不回显、不复制**到任何其它文件 / 日志；异常对密钥脱敏。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循 `020-Codex执行交付指令` / `020` 的执行与停机规范。本次任务是执行**已批准**的计划
`docs/dev/plans/020-B-lite证据矩阵层-计划.md`（状态 approved，修订轮次 1）——构建 **B-lite 证据矩阵层**（第二个业务模块）。

【唯一真源】先读这些文件，以它们为准，不要凭会话臆测：
- `docs/dev/plans/020-B-lite证据矩阵层-计划.md`（**逐条照做**，尤其 §2 范围、§4 调研结论、§6 任务、§8 验收、§10 决策预算、§11 风险）
- `00-问题描述.md` §「证据链成功标准」（10 字段 + 4 类证据状态）、§「创新成功标准」（证据矩阵化组织）
- `docs/dev/spec/015-成功标准校准.md`（S3 结构化 / S4 创新 / S5 合规）、`docs/dev/spec/035-选定路线冻结.md`（B-lite 有界、第 2 步边界）
- M010 verified 产物：`reports/m010/results.json`（消费 `per_query[*]` 的 `decomposition.subqueries/criteria` + `scholarloop_a` 排序）；`src/scholarloop/{config,llm,corpus,utils}.py`（**import / 移植复用，不回改 M010 行为**）

【本次要做（按 §6 顺序）】
0. **凭证复用 + 上游输入适配**：`import scholarloop.config`（不重建 config.py）；建 `src/scholarloop/evidence/source.py`：`load_a_outputs()` 读 M010 `per_query`（A 的排序 + criteria），`get_paper(corpusid)` 取 `title/abstract/full_paper/citations`。env 为空先 import 自加载，不停机。
1. **10 字段证据卡抽取**（`evidence/card.py`）：对每篇 Top-N（建议 10）推荐论文产出 010 的 10 字段；可落地字段（标题/推荐理由/支持的研究问题/方法/数据场景/主要结论/关联强度）用 LLM 从 `abstract`（不足回退 `full_paper` 片段）抽取，**每个抽取值返回 `{value, source_field, char_span, confidence}`**；temperature=0/seed=42，原始响应落 `reports/m020/raw/llm/`。
2. **证据状态分类**（`evidence/status.py`）：每字段标注 4 类之一——证据片段可在原文逐字定位→**已有证据支持**；语料无此字段（**作者/年份/DOI**）或原文检索不到→**证据不足**；置信低 / 官方必填但仅外部可解析→**需人工核验**；同篇内或跨篇相反结论→**存在争议**（有界、可选）。作者/年份/DOI 字段 100% 为非「支持」状态且带 `resolution_hint=online_connector`。
3. **证据矩阵构建**（`evidence/matrix.py`）：每查询构建 行(Top-N 论文)×列(该查询 A 的 `criteria`) 矩阵，格 = `{addresses, snippet(可定位), status}`；判据命中以原文可定位片段为准，**无凭空命中**。【可选】`evidence/graph.py` 仅在 Top-N 集合内部用 `citations` 连边输出有界引用邻接（不做全语料大图）。
4. **结构化渲染（S3 产物）**（`evidence/render.py`）：逐查询 JSON（带 schema 版本）+ Markdown 矩阵表 + 逐篇 10 字段卡片；汇总 `reports/m020/evidence/*.json` + `reports/m020/evidence-matrix-report.md`（含 ≥3 演示样例：LitSearch + 1 个碳价/AI 科研演示查询）。
5. **零伪造校验桩 + dev 评测**（`evidence/verify.py`）：对 dev 抽样（≥30 条 LitSearch + 演示查询）逐字段校验 `char_span` 可在原文定位；统计 `fabrication_rate`（标「支持」却定位失败占比，**目标 0**）、状态覆盖、作者/年份/DOI 合规率、确定性（run1==run2）、增量 Token / P50·P95 延时。产出 `reports/m020/verification.json` + `reports/m020/grounding-report.md`。
6. **合规 / 可复现 / 复盘**：全仓 grep 无密钥落盘；两次端到端一致；写 `docs/dev/retrospectives/020-B-lite证据矩阵层-复盘.md`。

【硬红线（不得改动）】
- §8 验收，尤其**承重墙（零伪造 S5）**：dev 抽样 `fabrication_rate = 0`——凡标「已有证据支持」的字段值，其 `char_span` 必须 100% 在论文原文可定位；定位失败一律降级为非「支持」状态，**不得**放宽定义把编造算作支持。
- **作者/年份/DOI 三字段**：离线语料无此列，必须标「证据不足 / 需人工核验」+ `resolution_hint`，**绝不伪造**作者/年份/期刊/DOI（踩 S5 红线即作废）。
- **上游只读**：行=A 的 Top-N、列=A 的 criteria；**不得**改 M010 的排序 / 产物 / 任何 §8 判据；矩阵不得出现 A 未召回的论文。
- 只允许写 `src/scholarloop/evidence/**`、`tests/**`（新增 `test_m020_*.py`，**不改** `test_m010_core.py`）、`reports/m020/**`（含 `raw/llm/`）；**不得**改任何 FROZEN 件、`spike/**`、`reports/m010/**`、既有 M010 源码行为、本计划验收判据、`040`。
- **绝不把密钥写入任何文件**；只经 config 读取；异常对密钥脱敏。

【可自行决定（§10 预算内）】Top-N 与字段抽取原文窗口；是否启用有界引用图；抽取 prompt 措辞（须保 temperature=0 + 出处返回）；JSON schema 字段顺序；`evidence/` 内部文件组织与局部命名。

【必须停机上报（写 `reports/m020/` 停机报告，交总指挥，不自行扩范围）】
- **`fabrication_rate` 压不到 0**（核心风险）——停机上报，不得放宽 grounding 定义制造好看的矩阵；
- 填充任一官方字段只能靠在线连接器实调用或编造；逐篇抽取 Token/延时超 `015` S2 预算；需改 M010 产物 / 排序 / 任何 §8 判据；需 >2GB 模型 / GPU；需接入在线付费 / 受限数据；LLM 端点失效 / 凭证问题；任何只能靠虚构才能填的字段。

【交付】完成后：`src/scholarloop/evidence/**` + 子包 AGENTS/CLAUDE 说明（声明证据矩阵层职责、上游 M010 只读、禁写密钥、禁碰 FROZEN/m010）；`pytest tests/ -q` 通过记录；`reports/m020/**` 产物（含 `verification.json`、渲染矩阵、raw 抽取响应）；写复盘 `docs/dev/retrospectives/020-B-lite证据矩阵层-复盘.md`；把 `020` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查。
