# 010 · 交给 Codex 的执行提示词（dispatch）

> 用法：在**已设置好 LLM 端点环境变量**的终端启动 Codex，把下面「提示词正文」整段交给它。
> 本文件不含任何密钥，只引用环境变量名。

---

## 端点凭证（两种注入方式，二选一；勿写入仓库受控区）

本模块的查询拆解 / 可选 LLM 重排需要三项凭证：
- `LLM_BASE_URL` = `https://api.deepseek.com`
- `LLM_API_KEY`（`sk-` 开头；第三次初查实测有效）
- `LLM_MODEL` = `deepseek-v4-flash`（实测可用；**非** `deepseek-chat`。备选 `deepseek-v4-pro`）

**方式 A（推荐·稳健，与启动方式无关）— 本地凭证文件**：人类把 `secrets/llm.env.local.example` 复制为 `secrets/llm.env.local` 并填入真实 key。Codex 启动时**若三项 env 缺失，则从 `secrets/llm.env.local` 读取 `KEY=VALUE` 注入 `os.environ`**，随后照常预检与调用。
> 因 rev2 与 M010 两次都因「`$env:` 未被 Codex 进程继承」停机，本方式绕开环境继承问题（Codex 能读本地磁盘即可）。

**方式 B — 环境变量**：人类在**启动 Codex 的同一进程环境**中设三项 env（继承得到才有效）。

> 凭证红线（对 `secrets/llm.env.local` 同样适用）：**只读取、不创建、不修改、不回显、不复制到任何其它文件 / 日志**；异常信息对密钥脱敏。
> 注意：deepseek-v4 为**推理模型**，会先产生 reasoning tokens；`max_tokens` 须给足（建议 ≥512），读取 `message.content`（忽略 `reasoning_content`），空 / `finish_reason=length` 响应须隔离不复用。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循 `020-Codex执行交付指令` 的执行与停机规范。本次任务是执行**已批准**的计划
`docs/dev/plans/010-A主干检索排序引擎-计划.md`（状态 approved，修订轮次 1）——构建 **A 主干检索排序引擎**（首个业务模块）。

【唯一真源】先读这些文件，以它们为准，不要凭会话臆测：
- `docs/dev/plans/010-A主干检索排序引擎-计划.md`（**逐条照做**，尤其 §2 范围、§6 任务、§8 验收、§10 决策预算、§11 风险）
- `docs/dev/spec/015-成功标准校准.md`（S1 承重墙阈值 + S2 效率）、`docs/dev/spec/035-选定路线冻结.md`（建造顺序 + 不可跨越边界）、`docs/dev/spec/040-验证桩结论.md`（PASS + 前进路径）
- `spike/eval/run_spikes.py`（已验证的拆解 prompt、同候选池协议、`metric_for_ranking`、`normalize_ranked_ids`、LLM 封装）——**移植复用，不要重写、不要修改 `spike/**`**

【本次要做（按 §6 顺序）】
0. **凭证以代码自加载，不在写代码前卡 env 预检而停机**（重要：你运行于 IDE 插件 / 桌面 App，外部终端的 `$env:` 不会进你的进程；三项 env 在你检查时为空是**预期**，**不构成停机理由**）：
   - **第一步先建** `src/scholarloop/config.py`，让它在 import 时把 `secrets/llm.env.local` 加载进 `os.environ`（运行时读文件，绕过编辑器层的文件读限制）：
     ```python
     # src/scholarloop/config.py
     import os, pathlib
     def load_credentials() -> dict:
         keys = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
         if not all(os.environ.get(k) for k in keys):
             for base in (pathlib.Path("secrets/llm.env.local"),
                          pathlib.Path(__file__).resolve().parents[2] / "secrets" / "llm.env.local"):
                 if base.exists():
                     for line in base.read_text(encoding="utf-8").splitlines():
                         line = line.strip()
                         if line and not line.startswith("#") and "=" in line:
                             k, v = line.split("=", 1)
                             os.environ.setdefault(k.strip(), v.strip())
                     break
         return {k: bool(os.environ.get(k)) for k in keys}
     PRESENT = load_credentials()   # 在 import 时执行
     ```
   - **所有调用 LLM 的代码（T3 拆解、T5 单轮 LLM）必须先 `import scholarloop.config`**，再做端点预检与调用。
   - **端点预检在 import config 之后做**，不在你刚启动、还没写代码时做。
   - **只有当**：跑了 `load_credentials()` 后三项仍为 False（文件缺失/解析失败），**或**预检时端点真的拒绝凭证/网络失败 → 才写停机报告，并附 `PRESENT` 与 `secrets/llm.env.local` 是否存在。
   - 该文件**只读**：不创建 / 不修改 / 不回显其值 / 不复制到任何其它文件或日志。
   - 自检：先跑 `python -c "import sys; sys.path.insert(0,'src'); import scholarloop.config as c; print(c.PRESENT)"`，应打印三项均 True 再继续。
1. **T1 语料 / 检索接口层 + 离线 LitSearch 适配器**：`CorpusRepository` 接口 + `LitSearchCorpus`（复用 `spike/raw/datasets/litsearch/corpus_clean/` 的 64,183 篇与 `.../hf/query/` 金标准）；为 OpenAlex/SemanticScholar/Crossref/Arxiv 预留**接口签名但不实现在线调用**。
2. **T2 神经稠密检索（LSA→神经升级）**：开源句向量模型（地板 `all-MiniLM-L6-v2`，可升级 `bge-small-en`/`e5-small-v2`）编码语料 + 查询，余弦召回；编码确定性，模型名+版本入证据；neural≠LSA。
3. **T3 查询拆解**：移植 A-min 拆解，temperature=0、seed=42、原始响应落 `reports/m010/raw/llm/`。
4. **T4 混合召回 + 可解释综合排序**：对（原查询 + 子查询）跑 BM25 + 神经召回 → 共享候选池 → 分数融合排序，可选 LLM 重排 Top-N；**每条结果输出 `corpusid + score + reason`**（理由可追溯到信号，杜绝黑箱）。
5. **T5 全量 LitSearch 评测 + 显著性检验**：全量查询集、5 系统（关键词/BM25/神经Embedding/单轮LLM/ScholarLoop-A）同候选池算 P@10/R@20/F1；对 **ScholarLoop-A vs BM25 做配对 bootstrap（≥10000 重采样）或配对置换检验**；记录效率（API 次数/Token/P50·P95 延时）。产出 `reports/m010/results.json`+`.csv`、`significance.json`、`A主干评测报告.md`。
6. **T6 合规 / 可复现 / 复盘**：全仓无密钥落盘；两次端到端跑结果一致；写 `docs/dev/retrospectives/010-A主干检索排序引擎-复盘.md`。

【硬红线（不得改动）】
- §8 全部验收，尤其**承重墙 S1**：ScholarLoop-A F1 须**配对显著**优于 BM25（bootstrap 95% CI(ΔF1) 不含 0 或置换 p<0.05），且 ≥ 其余三基线均值。
- H5「0 虚构」：推荐 ID 必须可在语料解析，池外 / 不可解析一律计不相关并记录；不得豁免。
- 同候选池协议（各基线 Top-K 并集，所有系统同池打分）、temperature=0、seed 固定、可复现、原始响应落盘。
- 只允许写 `src/scholarloop/**`、`tests/**`、`reports/m010/**`（含 `raw/llm/`）；**不得**改任何 FROZEN 件、`spike/**`、`040`、本计划验收判据。
- **绝不把密钥写入任何文件**；只从环境变量读取；异常信息对密钥脱敏。

【可自行决定（§10 预算内）】具体开源 embedding 模型；融合权重与是否启用 LLM 重排；候选池上限 K；向量索引实现（numpy/FAISS）；`src/scholarloop/` 内部文件组织与局部命名。

【必须停机上报（写 `reports/m010/` 停机报告，交总指挥，不自行扩范围）】
- **ScholarLoop-A 未显著优于 BM25**（核心风险）——停机上报，**不得**挑样本 / 改判据 / 关基线制造胜利；
- 需要 GPU / 重依赖 / >2GB 模型下载受阻；需改任何 §8 判据或同候选池协议；
- LLM 端点失效 / 凭证问题；Token/延时超 `015` S2 预算；需接入在线付费 / 受限数据；任何只能靠虚构才能填的字段。

【交付】完成后：交付 `src/scholarloop/**` + `src/scholarloop/AGENTS.md`/`CLAUDE.md`（声明本目录职责、禁写密钥、禁碰 FROZEN）；`pytest tests/ -q` 通过记录；`reports/m010/**` 评测产物；写复盘 `docs/dev/retrospectives/010-A主干检索排序引擎-复盘.md`；把 `010` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查。
