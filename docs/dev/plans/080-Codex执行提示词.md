# 080 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息，只引用环境变量名与 verified 产物路径。
> 联网授权沿用 M050/M060（Codex 可联网/浏览器控制）。
> **核心特征**：全路线**收束件**，**不新增 F1 承重墙**（只引用 verified 数值），承重转为「整合可运行 + 忠实呈现零伪造 + 提交物料零夸大可溯源」。M010–M070 + M030 `web/` **冻结只读**，整合层**新建**。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/080-整合Demo与提交物料收束-计划.md`（状态 approved）——这是 ScholarLoop 全路线**最后一块（收束件）**：把七个 verified 模块整合为单命令可运行的可信 Web 闭环 + 收束官方初赛提交物料。

【最高优先级 · 三条不可越的红线（先读再动手）】
1. **不新增任何 F1/指标承重墙，不做出超过已 verified 证据的任何主张**——提交物料里每一条指标/结论都必须**引用 verified 产物**（`reports/m020|m040|m050|m060|m070`），宁缺毋虚，**绝不夸大、绝不外推**。
2. **冻结只读**——M010–M070 全部产物/源码行为/验收判据/A-v2 配置、以及 M030 的 `src/scholarloop/web/**`（已 verified 基线），**一律只读不改**；整合层**新建**在 `src/scholarloop/demo/**`（复刻 M040 新建 dense_v2/rerank 不改 M010 的纪律）。
3. **合规红线（官方明令 + 项目纪律）**——提交材料**不得含学校/学院/导师等身份信息**（官方公平性要求）；M050 礼貌 UA 邮箱在**提交版脱敏**；**零密钥落盘/回显**；offline 0-LLM 确定性可复现。

【唯一真源】先读这些，以它们为准，不要凭会话臆测：
- `docs/dev/plans/080-整合Demo与提交物料收束-计划.md`（**逐条照做**，尤其 §2 范围、§6 任务、§7 顺序、§8 验收、§10 决策预算、§11 风险）
- `docs/dev/000-决策日志.md` 顶部「2026-06-20 · M080 批准」审批记录（授权范围 + 红线 + 携带项处理）
- `00-赛题/科研场景下复杂学术查询的智能论文搜索与推荐.txt`（官方赛题：§3.1 四大核心功能、§4 评分、作品要求与初赛交付清单——事实源）
- `docs/dev/spec/015-成功标准校准.md`（S2 效率 / S3 结构化 / S4 落地+泛化+创新 / S5 合规）
- M030 忠实呈现范式（只读参考）：`src/scholarloop/web/verify.py`（`sha256_file`/`hash_dir`/`scan_for_secrets`/逐字段相等校验写法）、`src/scholarloop/web/{app.py,render.py,data.py}`

【要整合的 verified 产物（只读消费，路径已核实）】
- **A-v2 检索排序**（M040）：`reports/m040/results.json` → `per_query`（每查询 A-v2 `ranked_top20`，区分高度/部分相关）、`by_system`、`aggregate`、`efficiency`（成本口径）、`protocol`（含 final_weights + 实测模型 **bge-small-en-v1.5**）。
- **B-lite 证据矩阵**（M020）：`reports/m020/evidence/litsearch_*.json`（逐条证据卡 + char_span 溯源 + 4 类证据状态）。
- **真实学术 API 富化**（M050）：`reports/m050/enriched/litsearch_*.json`（连接器解析的作者/年份/DOI + `external_provenance`）；`reports/m050/enriched_replay/`（**离线重放**，评测/演示读此不再联网）；`reports/m050/data-sources.md`（X3 数据源/许可）。
- **跨基准泛化**（M060）：`reports/m060/{results.json,significance.json}`（A-v2 F1≈0.197 vs BM25≈0.106，双口径，配对显著）。
- **研究空白发现**（M070）：`reports/m070/gaps_display.json`（`items`：concept_a/b、score、evidence_status、counts、historical_evidence_ids、future_fill_example_ids、narration；`concept_nodes`；`matrix_edges`）+ `reports/m070/{results.json,significance.json}`（预测性承重 + 抗泄漏协议）。

【本轮要做（按 §6/§7 顺序）】
0. **T0 · 整合数据装配** `src/scholarloop/demo/assemble.py`：只读加载上述五类产物，按查询组装统一不可变视图 DTO（排序 / 证据矩阵 / 真实出处 / 研究空白）；缺失字段**显式占位标注**（不补写）；确定性。
1. **T1 · 整合 Web 层** `src/scholarloop/demo/app.py`：单命令起服务（沿用 M030 后端选型与轻栈），四层面板——①查询拆解 ②A-v2 排序（高度/部分相关）③逐条证据矩阵 ④真实连接器富化的作者/年份/DOI（带出处；未解析标「需人工核验」）⑤研究空白（列表 + 关系矩阵）；展示**效率/成本口径**（引 M040/M060 `efficiency` 记账）；offline 0-LLM 基准路径（确定性、零成本、可复现）。覆盖官方 §3.1 四大核心功能的可见呈现。
2. **T2 · 整合忠实校验（承重）** `src/scholarloop/demo/verify.py` + `tests/test_m080_*.py`：每个面板展示值**逐字等于**其后端 verified JSON（A-v2 排序值、M020 证据值、M050 enriched 值、M070 gaps 值）；`fabrication=0`、`out_of_pool=0`、缺失字段标注正确；产出 `reports/m080/fidelity_audit.json`。**【停机】** 任一面板无法在不伪造前提下忠实呈现 → 标注「不补写」或停机说明，**绝不编造**。
3. **T3 · 官方提交物料收束** `docs/submission/**`：①**作品简介**（≤300 字中文，无身份信息）；②**项目文档**（标准模板式详述，覆盖官方 §3 全要点：问题/方法/系统架构/创新点/落地/泛化/评测结果/复现/合规）；③**项目视频脚本 + 演示走查脚本**（脚本与分镜；**实际录制由人类完成，本模块只交脚本**）；④**指标汇总表**（跨两基准 F1/效率/结构化，**每格挂 verified 产物引用**）；⑤**复现说明**（单命令运行 + 数据源/许可 + 冻结配置 sha）；⑥**创新叙事**（研究空白可证伪性 + 跨基准泛化，挂证据，对标 PaSa/SPAR/Ai2 定位差异化）；⑦**数据源/许可汇总**（汇 M050 data-sources）。**每条主张挂 verified 引用，零夸大；零身份信息。**
4. **T4 · 携带项收束**（全部如实落材料/复盘）：(a) 「BGE-base」措辞**订正为实测 bge-small-en-v1.5**；(b) M040 cross-encoder 边际贡献据 NDCG 给**诚实保留/可砍说明**；(c) M070 频率混杂——主张精确表述为「**(高活跃·零历史共现)组合空白填补率显著高于随机概念对**」，**频率配平基线消融按「可选·时间允许则做」**（做了则作为更硬证据并列，不做则在材料中如实标注此口径边界，**不得**因此夸大）；(d) M060 cross-encoder 第二基准未单独消融的诚实标注；(e) M050 UA 邮箱提交版脱敏。
5. **T5 · 合规 / 可复现 / 复盘**：单命令运行核对；`secret_scan` 0 命中；上游 M010–M070 + `web/` sha/diff 未变；写 `docs/dev/retrospectives/080-整合Demo与提交物料收束-复盘.md`（含整合忠实 + 零夸大结论 + **全路线七承重墙总账**）。

【硬红线（不得改动）】
- §8 承重①**整合可运行**：单命令起服务、四层面板全可见、覆盖官方 3.1 四功能。
- §8 承重②**整合忠实呈现零伪造**：每面板值逐字==后端 verified JSON、fabrication=0、越界=0、缺失标注不补写。
- **零夸大可溯源**：提交物料每条指标/主张挂 verified 产物引用，**不外推、不做超 verified 主张**。
- **零身份信息**：材料无学校/学院/导师；M050 UA 邮箱脱敏。
- **冻结只读**：M010–M070 产物/源码行为/判据/A-v2 配置 + M030 `web/**` 全只读；整合层新建。
- offline 0-LLM 确定性可复现；**零密钥**落盘/回显。
- 只允许写：`src/scholarloop/demo/**`、`docs/submission/**`、`tests/test_m080_*.py`（**不改** `test_m010..m070`）、`reports/m080/**`、复盘 `docs/dev/retrospectives/080-整合Demo与提交物料收束-复盘.md`。

【可自行决定（§10 预算内）】整合页面布局与组件；项目文档模板字段组织（须覆盖官方 §3 全要点）；视频分镜脚本；后端框架沿用 M030 选型；`demo/` 文件组织与局部命名；指标汇总表式样；频率配平消融是否在本轮时间内做（可选）。

【必须停机上报（写 `reports/m080/` 停机报告，交总指挥，不自行扩范围）】
- 任一面板**无法在不伪造前提下**忠实呈现某 verified 产物（缺字段等）→ 标注不补写或停机，**绝不编造**；
- 需改 M010–M070 产物 / `web/` / 任何 §8 判据才能整合；
- 需做出**超过 verified 证据的指标主张**才能满足模板；
- 材料无法去除学校/导师/身份信息；
- 任何只能靠**虚构**才能填的字段。

【交付】完成后：`src/scholarloop/demo/**` + `docs/submission/**`（全套提交物料）；`pytest tests/ -q` 通过记录；忠实校验 `reports/m080/fidelity_audit.json`；烟测 `reports/m080/smoke.txt`；`reports/m080/{secret_scan.json,validation_summary.json}`；写复盘 `docs/dev/retrospectives/080-整合Demo与提交物料收束-复盘.md`（含全路线七承重墙总账）；把 `080` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第十三次初查）。
