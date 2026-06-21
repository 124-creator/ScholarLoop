# 060 · 交给 Codex 的执行提示词（dispatch）· 修订轮次 2

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥，只引用环境变量名。
> 联网授权沿用 M050（Codex 可联网/浏览器控制）。
> **修订轮次 2 背景**：第一次执行在 T0 正当停机（RealScholarQuery 数据文件 401 + 2.67GB 超阈、AstaBench gold 不完整）。人类已拍板：**第二基准锁定 RealScholarQuery**、**豁免 >2GB 阈值**、**经 secrets 提供 HF token**、**放弃 AstaBench**。详见 `060-真泛化跨域评测-计划.md` 修订轮次 2 与决策日志同日审批记录。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次是 **M060 修订轮次 2**：执行**已批准**的计划
`docs/dev/plans/060-真泛化跨域评测-计划.md`（状态 approved，修订轮次 2）——构建**真泛化 / 跨域评测**（第六个业务模块）。第一次在 T0 正当停机，本轮人类已解除两处阻塞并锁定基准。

【唯一真源】先读这些，以它们为准，不要凭会话臆测：
- `docs/dev/plans/060-真泛化跨域评测-计划.md`（**逐条照做**，尤其 §2 范围、§6 任务、§8 验收、§10 决策预算、§11 风险，以及**修订轮次 2 决策块**）
- `docs/dev/000-决策日志.md` 顶部「M060 修订轮次 2」审批记录（人类授权的三项例外与不变红线）
- `docs/dev/spec/015-成功标准校准.md`（S1 公开金标准、S4 泛化）、`02-评审分级.md`（X1 公开金标准、X2 同候选池）
- 上游 verified 产物（**只读复用，不改**）：`reports/m040/results.json`（A-v2 **冻结配置** = `protocol.final_weights={bm25:0.1,dense_v2:0.4,sub_bm25:0.15,sub_dense_v2:0.15,cross_encoder:0.2}` + bge-small-en-v1.5 + ms-marco 重排）、`src/scholarloop/{retrieval/dense_v2.py,rank/rerank.py,rank/fusion_v2.py,eval/run_full_v2.py,corpus/base.py}`、`spike/eval/run_spikes.py`（同候选池/metric/H5/bootstrap）

【本轮第二基准 = 锁定 RealScholarQuery/PaSa（人类已拍板，不再比选）】
- 仓库 `github.com/bytedance/pasa`；数据集 `huggingface.co/datasets/CarlanLark/pasa-dataset`。
- 官方 gold = `RealScholarQuery/test.jsonl`（50 个真实研究查询，专业标注答案）；候选语料 = `paper_database/`（`cs_paper_2nd.zip` + `id2paper.json`，约 2.67GB，**已获豁免**）。
- **AstaBench 已放弃**（semantic 无完整确定性 gold）——不要再投入它，最多在复盘里一句话说明放弃理由。

【HF token（密钥纪律，最高优先级）】
- token 仅经 `secrets/llm.env.local`（gitignored、只读）以 `HF_TOKEN=...` 提供；可能也存在别名 `HF_ACCESS_TOKEN/HUGGINGFACE_TOKEN/HUGGING_FACE_HUB_TOKEN`。
- **T0 第一步**：对 `src/scholarloop/config.py` 做**最小白名单扩展**，让其能从 secrets 透传上述 HF token 变量到 `os.environ`（当前 `_parse_env_line` 仅放行 `REQUIRED_ENV`）。**作为可选项（OPTIONAL，缺失不报错）**，沿用现有「value 存在且 os.environ 未设才设、永不打印」逻辑。只改这一处加载白名单，**不改** LLM 既有行为。
- **绝不**把 token 值写入任何文件（含 `reports/m060/**`、日志、报告、缓存）；**绝不**回显；保存任何 HTTP 快照前**删除/脱敏 `Authorization` 头**与签名 URL 里的 token 参数。异常对 token 脱敏。
- 若 secrets 里没有可用 HF token（import config 后仍不存在）→ 停机上报（不要尝试无 token 暴力下载）。

【判据补充 · 双口径 gold 评测（rev2 续，人类已裁定，必照做）】
T0 已知事实（总指挥独立双路核查坐实）：RealScholarQuery 共 **791 个官方 gold**，其中 **52 个（涉 22 查询）不在官方候选池**——其 arxiv_id 不在 `paper_database/id2paper.json`（56.9万键）**且** 归一化标题不在 `cs_paper_2nd.zip`（55.5万键），两路皆 miss，系 PaSa 抽样子集固有属性（**非** 你的 bug，亦**非**可补救的缺文件）。人类裁定：**不补库、不改官方 corpus，采"双口径"评测**——
- **gold 可达性判定（取并集，最大化可达）**：某 gold 视为"在库/可达" ⟺ 其 `answer_arxiv_id` 命中 `id2paper.json` **或** 其标题归一化命中 `cs_paper` 键。预期可达 ≈ **739**。落盘实际可达数。
- **主指标（承重墙）**：在**可达 gold**上算 P@10/R@20/F1/NDCG；A-v2 vs BM25 配对 bootstrap(≥10000)/置换，显著即承重达成。
- **稳健性对照**：把**全部 791**（52 不可达当作**所有系统等同 miss**，即计入 recall 分母）再算一遍 F1，**同样验证 A-v2>BM25** 并如实报告（两口径结论须一并呈现）。
- **全透明落盘**：`data-sources.md` + 评测报告显式写出 52 不可达清单（arxiv_id+标题）、22 受影响查询、每查询丢失 gold 数、双路核查方法，并声明"按官方语料构造判定、非人工挑选"。
- **这 52 个不再触发"gold 不可解析→停机"**；但若**可达 gold 占比异常崩塌（可达<60%）**或出现**新的、上述之外的不可解析原因**，仍须停机上报。

【本轮要做（按 §6 顺序）】
0. **T0 获取 + 合规核验（联网，多数已完成可复用缓存）**：HF token 拉取/缓存 RealScholarQuery `test.jsonl` + `paper_database/`（已在 `reports/m060/raw/pasa-dataset/`，可直接复用）；落数据源/许可/gold 协议 + **上面的双口径可达性核查结果**到 `reports/m060/data-sources.md`。**【仍须停机的情形】** token 无效/数据撤下/许可禁止评测用途/**可达 gold<60%**/出现 52 个之外的新不可解析原因。**这 52 个按判据补充处理，不停机。**
1. **基准适配器**（`src/scholarloop/benchmarks/realscholarquery.py` 等）：复用 M010 `CorpusRepository` 接口，加载 RealScholarQuery 语料/查询/官方 gold；单测覆盖加载完整性与 gold 命中（`tests/test_m060_*.py`）。
2. **索引**：用 A-v2 **冻结**的 bge-small + bm25 对 RealScholarQuery 语料编码/索引；确定性、缓存。语料约 2.67GB，**CPU 体积/时间受阻 → 停机上报**（含已尝试的子集化方案说明，不擅自缩小评测集冒充全量）。
3. **冻结迁移评测 + 显著性（双口径）**（`src/scholarloop/eval/run_benchmark2.py`）：用 **A-v2 的 M040 冻结配置（不重调）** + 基线（关键词/BM25/Embedding/单轮LLM）在 RealScholarQuery 上**同候选池**算 P@10/R@20/F1/NDCG。**按上面【判据补充】双口径出两组数**：主指标=可达 gold（739）；稳健对照=全 791（52 当等同 miss）。A-v2 vs BM25 在**主指标**上配对 bootstrap(≥10000)/置换（=承重墙），稳健对照同样报 ΔF1 与显著性；效率记账。产出 `reports/m060/results.json`（含 `resolvable` 与 `full791` 两套 metrics + 可达性核查明细）+`significance.json`+`评测报告.md`。
4. **（仅当冻结不显著）诚实并列重调**：在 RealScholarQuery train/子集重调，结果**明确标注为非零样本**，与冻结结果并列；**不**以重调冒充零样本泛化。
5. **合规 / 可复现 / 复盘**：无密钥泄露；缓存重放一致（缓存须可在**无 token**下离线重放，即评测阶段读缓存不再联网）；写 `docs/dev/retrospectives/060-真泛化跨域评测-复盘.md`（泛化成立/不成立都如实，含放弃 AstaBench 一句说明）。

【硬红线（不得改动）】
- §8 承重：**A-v2 冻结配置**在 RealScholarQuery **可达 gold 主指标**上 F1 **配对显著优于 BM25**（CI(ΔF1) 不含 0 或置换 p<0.05）；稳健对照（全 791）一并报告。
- **X1**：只用 RealScholarQuery **官方 gold**，**绝不自标注**；数据源/许可落盘。
- **零样本诚实**：A-v2 用 M040 **冻结配置**迁移（`reports/m040` 的 final_weights + 同模型），**不在新基准重调**；若重调，结果只能**并列、明确标注非零样本**。
- **冻结配置在 RealScholarQuery 不显著>BM25 → 停机上报**，如实承认"单基准强、跨基准弱"，**不得**自标注 gold / 用重调冒充零样本 / 挑样本 / 改判据。
- 同候选池（A-v2 与所有基线在 RealScholarQuery **同一候选池**内排序）、H5「0 虚构」、temperature=0/seed、原始落盘、可复现——继承 M040 不放宽。
- **密钥纪律**：见上「HF token」段——绝不落盘/回显，缓存脱去 auth 头。
- **上游冻结只读**：不得改 `reports/m010|m020|m030|m040|m050/**`、M010–M050 既有源码行为（A-v2 配置只读复用；`config.py` **仅允许** HF token 白名单扩展，不改 LLM 行为）、各模块验收判据、FROZEN 件、`spike/**`。
- 只允许写 `src/scholarloop/benchmarks/**`、`src/scholarloop/eval/run_benchmark2.py`、`src/scholarloop/config.py`（**仅** HF token 白名单一处）、`tests/**`（`test_m060_*.py`，**不改** `test_m010..m050`）、`reports/m060/**`、复盘文件。

【可自行决定（§10 预算内）】RealScholarQuery 语料的加载/索引实现与缓存键；评测子集策略（若全量受阻须停机说明，不擅自缩量冒充全量）；`benchmarks/` 内文件组织与局部命名；config 白名单扩展的具体写法（满足"可选、永不回显"）。

【必须停机上报（写 `reports/m060/` 停机报告，交总指挥，不自行扩范围）】
- HF token 无效/缺失；RealScholarQuery 撤下/许可禁止评测；**可达 gold<60% 或出现 52 个之外的新不可解析原因**（已知 52 个按判据补充双口径处理，**不**停机）；语料 CPU/体积/时间受阻无法完成全量（须给子集化建议，不冒充全量）；A-v2 冻结配置在**可达 gold 主指标**不显著>BM25（真实泛化信号）；需自标注 gold 才能评测（X1 红线）；需改 M010–M050 产物或任何 §8 判据；任何只能靠虚构才能填的字段。

【交付】完成后：`src/scholarloop/benchmarks/**` + `eval/run_benchmark2.py` + `config.py`（仅 token 白名单）+ `reports/m060/data-sources.md`；`pytest tests/ -q` 通过记录；`reports/m060/**` 评测产物（含 `results.json`、`significance.json`、是否零样本的协议标记、可离线重放缓存）；写复盘 `docs/dev/retrospectives/060-真泛化跨域评测-复盘.md`；把 `060` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第十次初查）。
