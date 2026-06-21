# 005 · 交给 Codex 的执行提示词（dispatch）

> 用法：在**已设置好 T2b 端点环境变量**的终端启动 Codex，把下面「提示词正文」整段交给它。
> 本文件不含任何密钥，只引用环境变量名。

---

## 端点环境变量（由人类在终端先设置，勿写入仓库）

T2b 需要以下三个环境变量（值不在本文件，见本地设置）。**必须在启动 Codex 的同一进程环境中设置**，否则 precheck 报 MissingEnvironment（rev2 即因此停机）：

- `LLM_BASE_URL` = `https://api.deepseek.com`
- `LLM_API_KEY`（`sk-` 开头；总指挥 2026-06-18 实测有效）
- `LLM_MODEL` = `deepseek-v4-flash`（实测可用；**非** `deepseek-chat`。备选 `deepseek-v4-pro`）

> 注意：deepseek-v4 为**推理模型**，会先产生 reasoning tokens；调用 `max_tokens` 须给足（建议 ≥512），读取 `message.content`（忽略 `reasoning_content`），否则输出可能为空。

备用火山方舟 Ark：`LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/coding`、`LLM_API_KEY`（`ark-` 开头）、`LLM_MODEL`=推理接入点 ID（如 `ep-xxxx`，用户未提供则停机索取）。

> T2a 已完成（无需凭证）。本次只需补跑 T2b → T5 → T6。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循 `020-Codex执行交付指令` 的执行与停机规范。本次任务是执行**已批准**的计划
`docs/dev/plans/005-验证桩执行-计划.md`（状态 approved，修订轮次 2）的 **§16 rev2** 部分。

【唯一真源】先读这些文件，以它们为准，不要凭会话臆测：
- `docs/dev/plans/005-验证桩执行-计划.md`（尤其 §2 范围、§9 测试策略、§10 决策预算、§16 rev2）
- `docs/dev/spec/040-验证桩规格.md`、`docs/dev/spec/015-成功标准校准.md`
- `spike/AGENTS.md`、`spike/eval/run_spikes.py`（已有 T1/T3/T4 实现，**不要重做**）

【本次要做（按序）】
1. **T2a（无 LLM，先跑）**：按 §16.1 构建评测桩，加载已落盘的 LitSearch 语料/查询/金标准；实现关键词、BM25(`rank_bm25`)、Embedding（本地小型开源模型如 `all-MiniLM-L6-v2`）三基线；固定协议（同语料、同候选上限 K、共享候选池）；算 P@10/R@20/F1；两次运行结果一致。产出 `spike/x1a-评测桩与无LLM基线.md` + 结果表。
2. **T2b（开源端点）**：用 OpenAI SDK 连 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` 做凭证预检；通过后实现「单轮 LLM 检索」基线与 A-min（查询拆解+多源召回+重排），temperature=0、固定种子、记录模型名+版本+token+延时、原始响应落盘 `spike/raw/llm/`；并入 T2a 同候选池重算指标。产出 `spike/x1b-LLM基线与Amin.md`。
3. **T5（C-lite 三臂）**：按 §6-T5/§16.3 跑 单轮 / 多轮 / 多轮+确定性质检（质检=DOI 在 Crossref/OpenAlex 可解析且作者年份匹配，非 LLM 自评），每臂 N=3 报告 mean±std + 效率。产出 `spike/c-消融闸门.md`，给明确 go/no-go。
4. **T6**：按 `040` §0 总判据汇总 T1–T5，产出 `docs/dev/spec/040-验证桩结论.md`（PASS/FAIL + 逐 spike 证据 + 前进路径）。

【硬红线（不得改动）】
- §8 + §16.4 全部阈值、`040` §0 总判据、H5「0 虚构」红线、temperature=0 与可复现、原始响应落盘。
- 单轮 LLM 基线虚构的论文（无法在语料解析）一律计为不相关，不得豁免。
- 只允许写 `spike/**` 与 `docs/dev/spec/040-验证桩结论.md`；不得改任何 FROZEN 件，不得实现 Web/后端业务。
- **绝不把密钥写入任何文件**；只从环境变量读取。

【可自行决定】具体开源嵌入模型 / BM25 库；端点内具体模型名（在给定 env 范围内）；`spike/` 文件组织；候选池上限 K。

【必须停机上报（写 `spike/reports/` 停机报告，交总指挥，不自行扩范围）】
- 端点未配置 / 凭证无效 / 端点不兼容 OpenAI schema；火山方舟落备用且缺 `LLM_MODEL`；
- 需要改 §8/§16/040 判据；需要新架构或重依赖；无法避免虚构才能填字段；
- token/延时明显超出 `015` S2 预算；涉及安全/隐私/许可/不可逆操作。

【交付】完成后：更新 `spike/x1a-*.md`、`x1b-*.md`、`c-消融闸门.md`、`040-验证桩结论.md`；写复盘
`docs/dev/retrospectives/005-验证桩执行-复盘.md`（追加 rev2 执行段）；把 `005` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做第二次初查。
