# 020 · B-lite 证据矩阵层 · 实施计划（Codex 执行简报）

- 状态：**verified**（2026-06-19 人类终验通过；第五次初查 PASS（零伪造承重墙站住）+ Router 批准，见 `../000-决策日志.md` 审批记录 2026-06-19）
- 修订轮次：1
- 日期：2026-06-19
- 轨道：重型
- 对应问题定义：`../../00-问题描述.md`（= 010，FROZEN，§证据链成功标准「10 项字段 + 4 类证据状态」+ §创新「证据矩阵化组织」）+ `../spec/015-成功标准校准.md`（S3/S4/S5）
- 对应选定路线 / 评审：`../spec/035-选定路线冻结.md`（建造顺序第 2 步 = B-lite）/ `../../02-评审分级.md`
- 对应验证桩：`../spec/040-验证桩结论.md`（= **PASS**，门禁已清除）
- 上游模块：`010-A主干检索排序引擎-计划.md`（= **verified**，2026-06-19 人类终验）
- 关联复盘：`../retrospectives/020-B-lite证据矩阵层-复盘.md`

> **前置（治理）**：本计划初始为 `draft`，**人类批准后**方可转译为 Codex 派工。M010 已 verified，A 主干产出可作上游消费。
> 本计划只建 **B-lite 证据矩阵层**（035 第 2 步），**不**碰 F1 承重墙（M010 已结）、**不**做大规模交互研究图谱 / 研究空白发现（035 第 4 步，条件触发，本轮不做）、不做 C-lite（040 no-go）、不做 Web 前后端、不实接在线学术 API。

---

## 1. 模块目标

- **本模块解决什么**：把 M010 ScholarLoop-A 的「排序后论文 + 拆解判据」组织成**可信、结构化、零伪造**的科研证据链——为每篇推荐论文产出官方要求的 **10 项证据字段**（每项带出处或证据状态），并把「论文 × 判据」组织成**证据矩阵**。这是官方**结构化展示 10%** 与**专家创新分**（「证据矩阵化组织」「综合排序可解释」）的落地件，也是把纯 A「不就是 RAG」质疑挡回去的差异化件。
- **对冻结成功标准的贡献（映射 015 S1–S5）**：
  - **S3（结构化·10%）**：本模块的**主交付**——以列表 + 证据矩阵（论文 × 判据）+ 逐篇 10 字段卡片的结构化形式输出，替代纯文本段落。
  - **S4（专家分·40%）**：创新 = 证据矩阵化组织 + 字段级证据状态区分 + 推荐理由可追溯到信号/判据；落地 = 结构化 JSON 可直接喂 Web Demo（M3+）。
  - **S5（合规·承重）**：每个字段值**要么可在论文原文定位（出处偏移入证据），要么显式标注 4 类证据状态之一**；语料无法落地的官方字段（作者/年份/来源/DOI）一律标「证据不足 / 需人工核验」并指向 A 已预留的在线连接器接口，**绝不伪造**。
  - **S1（F1·70%）不在本模块**：已由 M010 结清，本模块**不得**改动 M010 指标或判据。
  - **S2（效率·20%）**：矩阵构建的增量 Token / 延时入账，证明结构化代价在预算内。

## 2. 范围

- **本轮必须做**：
  1. **证据源适配层**：按 corpusid 从 `corpus_clean` 取 `title/abstract/full_paper/citations`；读 M010 `reports/m010/results.json` 的 `per_query`（`decomposition.subqueries/criteria` + `scholarloop_a` 排序 + reason）作为上游输入。
  2. **10 字段证据卡（EvidenceCard）抽取**：对每篇 Top-N 推荐论文，产出 010 §证据链成功标准的 10 字段；可从原文落地的字段（标题/推荐理由/支持的研究问题/方法/数据场景/主要结论/关联强度）用 **LLM 抽取 + 出处片段（char offset）**；不可落地字段（作者年份/来源 DOI/部分局限性）按 §3 状态规则标注。
  3. **证据状态分类**：每字段标注 4 类之一（已有证据支持 / 证据不足 / 存在争议 / 需人工核验），规则见 §4。
  4. **证据矩阵（论文 × 判据）**：行 = Top-N 论文，列 = 该查询的 `criteria`（取自 A 拆解），格 = `{addresses: 命中?, snippet: 证据片段, status: 状态}`。
  5. **结构化产物**：机器可读 JSON（带 schema）+ 人读渲染（Markdown 表 / CSV）；逐查询落盘。
  6. **零伪造校验桩**：在 dev 抽样上校验「每个有值字段的证据片段可在论文原文逐字定位（偏移命中）」→ `fabrication_rate=0`；不可定位即必须为非「已有证据支持」状态。
- **明确不做**：F1 / 排序判据的任何改动（M010 verified，只读消费）；大规模交互研究图谱与研究空白发现（035 第 4 步，条件触发，本轮不做）；C-lite；在线多源连接器实际调用（仅消费 A 已留接口签名，需要时**标注**而非调用）；Web 前端 / 后端；任何模型训练 / 微调；付费全文 / 未授权数据；自建 50 题集对外指标声称（015 已降级为 dev/demo/错误分析）。
- **允许修改 / 新建的文件**：
  - 新建业务代码：`src/scholarloop/evidence/**`（多小文件：源适配 / 字段抽取 / 状态分类 / 矩阵构建 / 渲染 / 校验）。
  - 新建测试：`tests/**`（新增 `test_m020_*.py`，**不改** `test_m010_core.py`）。
  - 新建产物：`reports/m020/**`（含 `raw/llm/`）。
  - **不得**改动：任何 FROZEN 件、`spike/**`、`reports/m010/**`、`src/scholarloop/{pipeline,eval,rank,retrieval,query,corpus,llm,config,utils}.py` 的既有 M010 行为（可**新增** evidence 子包，不回改 M010）、`010` 计划验收判据、`040`。

## 3. 现状与证据

- **已存在可复用（M010，verified）**：
  - `reports/m010/results.json.per_query[*]`：`gold`、`decomposition`（`subqueries` 3–4 + `criteria` ≤5）、`scholarloop_a.ranked_top20`、各系统 reason。**这是 B-lite 的直接上游输入。**
  - `src/scholarloop/config.py`：凭证 import 时自加载 `secrets/llm.env.local`（M010 已验证生效，三项 env True、真实 DeepSeek 调用成功）——**直接 import 复用，不重建**。
  - `src/scholarloop/corpus/litsearch.py`、`llm.py`（temperature=0/seed=42、读 `message.content`、空响应隔离、密钥脱敏）——**移植/复用其封装**。
- **已确认数据事实（本会话实测语料）**：`corpus_clean` 列 = `['corpusid','title','abstract','citations','full_paper']`；`title` 全有、`abstract` ~93% 非空（均长 ~1.4K 字）、`full_paper` ~99.98% 非空（均长 ~65K 字）、`citations` = 引用 corpusid 数组。**无 `author/year/doi/journal/venue` 列。**
- **由数据事实推出的硬约束（决定 B-lite 边界）**：
  - 可从原文落地：标题(1)、推荐理由(4)、支持的研究问题(5)、方法(6)、数据/实验场景(7)、主要结论(8)、关联强度(10)。
  - **不可从离线语料落地**：作者与年份(2)、来源或 DOI(3)→ 必须标「证据不足 / 需人工核验」+ 指向在线连接器接口（A 已预留 OpenAlex/SemanticScholar/Crossref/Arxiv 签名），**不得伪造**。
  - 局限性(9)：摘要常无，须回退 `full_paper` 检索；找不到即标「证据不足」。
- **仍未知但可在执行中确认**：LLM 字段抽取能否在 dev 抽样上做到 `fabrication_rate=0`（核心风险，见 §11）；逐篇抽取的 Token/延时是否在 S2 预算内（Top-N 与字段数可调）。

## 4. 调研结论

- **来源**：`00-问题描述.md` §证据链成功标准（10 字段 + 4 状态）、§创新成功标准（证据矩阵化组织）；`015` S3/S4/S5；`035` §1.2/§2（B-lite 有界、第 2 步）；M010 verified 产物与本会话语料实测。
- **可直接落地的结论**：
  1. **矩阵列 = A 的 `criteria`**（拆解判据已是查询的可检验子条件），矩阵行 = A 的 Top-N 推荐；天然把「综合排序」升格为「按判据的证据矩阵」。
  2. **零伪造的可操作判据**：字段值若标「已有证据支持」，则其证据片段必须能在该论文 `title+abstract+full_paper` 中逐字（或规范化后）定位，记录 `source_field + char_offset`；否则只能是其余 3 状态之一。这把 S5 从口号变成可机检指标（类比 M010 的 H5）。
  3. **证据状态 4 类规则**：可定位片段 → 已有证据支持；语料根本无此字段（作者/年份/DOI）或原文检索不到 → 证据不足；抽取置信低 / 官方必填但仅外部可解析 → 需人工核验；同一论文内或跨论文出现相反结论 → 存在争议（有界、可选）。
  4. **有界引用关系（可选·S4 加分）**：仅在 Top-N 推荐集合**内部**，用 `citations` 数组连边，输出小型引用邻接（≤N×N），**不**做全语料大图——符合 035「B-lite 不做大规模交互图谱」。
- **对本计划的影响**：T2（字段抽取）+ T6（零伪造校验）是 make-or-break；若抽取无法 grounding，须停机上报（§11），**不得**靠编造方法/结论/作者填满矩阵制造「好看」。

## 5. skills 选型与执行简报

- **选择的 skills**：无（结构化抽取 + 校验为确定性工程任务，M010 已给可移植 LLM/语料骨架；不把 skill 名抛给执行方）。
- **未选其它 skills 的理由**：引入额外 skill 增加不确定性且无收益；字段抽取的关键不是「更聪明的 agent」而是**严格 grounding 校验**，靠校验桩而非更复杂的编排保证。
- **转译后的普通执行步骤（硬要求标【硬】 / 建议标【议】）**：
  1. 【硬】`import scholarloop.config` 先于任何 LLM 调用；端点预检在 import 之后；env 在写代码前为空不构成停机理由（同 M010 T0）。
  2. 【硬】所有 LLM 抽取 temperature=0、seed=42、原始响应落 `reports/m020/raw/llm/`、Token/延时入账；读 `message.content`，空/`length` 响应隔离不复用。
  3. 【硬】任何标「已有证据支持」的字段值必须附 `source_field + char_offset` 且可在原文定位；定位失败一律降级为非「支持」状态并计入校验。
  4. 【硬】语料无 `author/year/doi` → 对应字段固定标「证据不足 / 需人工核验」并写 `resolution_hint=online_connector`，**不调用、不编造**。
  5. 【硬】矩阵列严格取自该查询 A 的 `criteria`，行取自 A 的 `scholarloop_a` Top-N，不得改 A 的排序或编造未被 A 召回的论文。
  6. 【议】Top-N、每篇字段抽取的原文窗口（abstract 优先、full_paper 回退片段）、是否启用有界引用图，可在 §10 预算内决定，依据与最终配置落盘。

## 6. 任务拆解

- [ ] **T0（不确定度：低）复用凭证自加载 + 上游输入适配**
  - 动作：`import scholarloop.config`（复用，不重建）；新建 `src/scholarloop/evidence/source.py`，提供 `load_a_outputs(results_path)`（读 M010 `per_query`：decomposition + scholarloop_a 排序）与 `get_paper(corpusid)`（取 title/abstract/full_paper/citations）。
  - 产出：`src/scholarloop/evidence/source.py`。
  - 完成判据：能按 corpusid 取回论文文本；能枚举 M010 全部 597 查询的 A 排序与判据；单测覆盖「上游 corpusid 全部可在语料解析」。
  - 红线：只读 `reports/m010/**` 与语料，不改 M010 产物。

- [ ] **T1（不确定度：中）10 字段证据卡抽取**
  - 动作：`evidence/card.py`，对每篇 Top-N 论文产出 10 字段；可落地字段用 LLM 从 `abstract`（不足回退 `full_paper` 片段）抽取，**每个抽取值返回 `{value, source_field, char_span, confidence}`**；不可落地字段（作者/年份/DOI）按 §4 状态规则置位。
  - 产出：`src/scholarloop/evidence/card.py` + 抽取 prompt；原始响应落 `reports/m020/raw/llm/`。
  - 完成判据：每篇产出 10 字段；每个「已有证据支持」字段带可定位 `char_span`；空/无效响应隔离不复用。

- [ ] **T2（不确定度：高）证据状态分类** ← 与 T6 共同 make-or-break
  - 动作：`evidence/status.py`，实现 4 类状态规则（§4.3）；对每字段判定状态；对官方必填但语料缺失字段固定「证据不足/需人工核验」+ `resolution_hint`。
  - 产出：`src/scholarloop/evidence/status.py`。
  - 完成判据：每字段恰好一个状态；作者/年份/DOI 字段 100% 为非「支持」状态且带 `resolution_hint`；状态分布写入报告。

- [ ] **T3（不确定度：中）证据矩阵构建**
  - 动作：`evidence/matrix.py`，对每查询构建 行(Top-N 论文)×列(A 的 criteria) 矩阵，格 = `{addresses, snippet(可定位), status}`；判据命中以原文可定位片段为准；【议】可选 `evidence/graph.py` 输出 Top-N 内部有界引用邻接。
  - 产出：`src/scholarloop/evidence/matrix.py`（+ 可选 `graph.py`）。
  - 完成判据：矩阵维度 = N×|criteria|；每个「命中」格带可定位 snippet；无凭空命中。

- [ ] **T4（不确定度：低）结构化渲染（S3 产物）**
  - 动作：`evidence/render.py`，输出逐查询 JSON（带 schema 版本）+ Markdown 矩阵表 + 逐篇 10 字段卡片；汇总 `reports/m020/evidence/*.json` 与 `reports/m020/evidence-matrix-report.md`。
  - 产出：`src/scholarloop/evidence/render.py` + `reports/m020/**`。
  - 完成判据：JSON 通过自带 schema 校验；Markdown 含矩阵表 + ≥3 个跨域演示样例（含 LitSearch + 1 个碳价/AI 科研演示查询）。

- [ ] **T5（不确定度：高）零伪造校验桩 + dev 评测** ← make-or-break 证据
  - 动作：`evidence/verify.py`，对 dev 抽样（≥30 条 LitSearch 查询 + 演示查询）逐字段校验 `char_span` 可在原文定位；统计 `fabrication_rate`（标「支持」却定位失败的占比）、状态覆盖、作者/年份/DOI 合规率、确定性（run1==run2）、增量 Token/延时。
  - 产出：`reports/m020/verification.json`、`reports/m020/significance_or_grounding.md`（B-lite 用 grounding 而非显著性）。
  - 完成判据：见 §8 验收（`fabrication_rate=0` 为承重）。
  - 【停机】若标「已有证据支持」的字段无法做到 100% 可定位（即 `fabrication_rate>0` 且无法靠收紧 grounding/降级状态消除）→ 停机上报，**不得**放宽定义把编造算作支持。

- [ ] **T6（不确定度：低）合规 / 可复现 / 复盘**
  - 动作：全仓 grep 无密钥落盘；两次端到端一致；写复盘。
  - 产出：`../retrospectives/020-B-lite证据矩阵层-复盘.md`。
  - 完成判据：reproducible=True；零密钥；复盘含失败模式（哪些字段最易 grounding 失败）与诚实结论。

## 7. 执行顺序与依赖

T0 → T1 → T2（依赖 T1 抽取出处）→ T3（依赖 T1/T2）→ T4（依赖 T3）→ T5（依赖 T1–T4）→ T6 收尾。T1 与 T2 的状态规则可并行迭代，但 T5 校验是闸门。

## 8. 验收标准与证据映射

| 验收项 | 阈值 / 预期 | 验证命令或证据 | 对应任务 |
|---|---|---|---|
| **零伪造（S5·承重）** | dev 抽样 `fabrication_rate = 0`（每个「已有证据支持」字段的 `char_span` 100% 在原文可定位） | `reports/m020/verification.json` | T1/T2/T5 |
| 官方字段合规（S5） | 作者/年份/DOI 字段 100% 标非「支持」状态 + `resolution_hint`，0 编造 | `verification.json`、全仓 grep | T2/T5 |
| 10 字段齐备 | 每篇 Top-N 论文输出全部 10 字段（含状态） | `reports/m020/evidence/*.json` | T1 |
| 证据矩阵结构化（S3） | 逐查询输出 行×列(=criteria) 矩阵 + 渲染表 + 逐篇卡片；JSON 过 schema | `evidence-matrix-report.md`、schema 校验 | T3/T4 |
| 上游一致（不污染 M010） | 行 = A 的 Top-N、列 = A 的 criteria，未改 M010 排序/产物 | diff `reports/m010/**` 未变 | T0/T3 |
| 证据状态区分（S5） | 4 类状态均可出现且规则确定；状态分布入报告 | `verification.json` | T2 |
| 效率增量（S2） | 报告矩阵构建增量 Token / P50·P95 延时，且在 `015` S2 预算内 | `verification.json.efficiency` | T5 |
| 可复现 | 两次端到端字段/状态/矩阵一致 | 复盘 run1==run2 | T5/T6 |
| 合规 | 全仓无密钥落盘；未改 FROZEN/spike/m010 | grep 证据 + mtime | T6 |

## 9. 测试策略

- **代码任务是否采用 TDD**：是（T0 源适配、T2 状态规则、T5 校验桩先写测试）。
- **Red checkpoint 如何保留**：测试先于实现，首次失败输出留复盘。
- **Green 验证命令**：`pytest tests/ -q`；端到端 `python -m scholarloop.evidence.verify`（或等价入口）。
- **非代码任务等价证据**：`verification.json` + 渲染矩阵 + raw 抽取响应落盘。
- **不得由执行方自行修改的验收测试**：§8「零伪造」`char_span` 定位逻辑、官方字段合规判定、4 类状态规则、上游只读约束、效率统计口径。

## 10. 执行方有界决策预算

### 可自行决定
- `src/scholarloop/evidence/` 内部文件组织与局部命名；Top-N（建议 10）与字段抽取原文窗口；是否启用有界引用图；抽取 prompt 具体措辞（须保 temperature=0 + 出处返回）；JSON schema 字段顺序。

### 必须停机上报
- `fabrication_rate` 无法降到 0（T5 核心风险）；填充任一官方字段只能靠在线连接器实调用或编造；逐篇抽取 Token/延时超 `015` S2 预算；需要改 M010 产物 / 排序 / 任何 §8 判据；需要 >2GB 模型或 GPU；需接入在线付费 / 受限数据；LLM 端点失效 / 凭证问题。

## 11. 风险、边界与回滚

- **核心风险（T1/T2/T5）**：LLM 字段抽取易把摘要里没有的方法/结论「脑补」出来——一旦标成「已有证据支持」即构成伪造，直接踩 S5 红线。缓解 = **强制 `char_span` 可定位才算支持，定位失败一律降级状态**；校验桩把 `fabrication_rate` 做成可机检闸门。**若做不到 0**，是真实的数据/方法信号——停机上报，由总指挥/人类决定（收紧 grounding、缩字段集、或把不可落地字段彻底转为「需在线连接器」展示），**绝不**伪造。
- **边界（035 §1.2/§4 继承）**：B-lite 有界——只做证据矩阵 / 结构化展示，不做大规模交互图谱、不做研究空白发现（留 035 第 4 步条件触发）、不做黑箱、不伪造引用。
- **回滚**：本模块代码独立于 M010 与 FROZEN 件；失败仅废弃 `src/scholarloop/evidence/**` 与 `reports/m020/**`，不污染 M010 verified 证据与验证桩。

## 12. 文档与治理同步

- **需要新建目录**：`src/scholarloop/evidence/`、`reports/m020/`（含 `raw/llm/`、`evidence/`）。
- **对应 AGENTS.md / CLAUDE.md**：在 `src/scholarloop/evidence/` 下新建或在现有 `src/scholarloop/AGENTS.md`/`CLAUDE.md` 追加：声明 evidence 子包职责（证据矩阵层）、上游 = M010 verified 产物（只读）、禁写密钥、禁回改 M010/FROZEN。
- **需更新的项目约定**：完成并经初查后，在 `000-决策日志.md` 追加 M020 交付与初查记录。

## 13. 交付要求

- **代码 / 文档**：`src/scholarloop/evidence/**`（多小文件）+ 子包 AGENTS/CLAUDE 说明。
- **测试输出**：`pytest tests/ -q` 通过记录；端到端 `reports/m020/**` 产物（含 `verification.json`、渲染矩阵、raw 抽取响应）。
- **复盘文件**：`../retrospectives/020-B-lite证据矩阵层-复盘.md`（含字段级 grounding 失败模式、效率账、诚实结论；**不得自行宣布 verified**，交总指挥用新鲜上下文做初查）。

