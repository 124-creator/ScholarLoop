# 170 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息。
> 联网授权沿用（实时模式需 LLM 端点；凭证仅经 `secrets/llm.env.local` 注入，绝不回显/写入仓库）。
> **核心特征**：实时演示可用性硬化（缓存提速 + 不丢已算结果）+ 实时结果卡/点即核验面板中文友好化。**承重 = ①实时稳定可用且结果等价 ②冻结评测零变化 ③点即核验忠实不破 + 中文化不改 verified 语义。** 绝不碰已 verified 的 F1/数据/检索逻辑/忠实逻辑。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/170-实时演示可用性与中文友好化-计划.md`（状态 approved）——让实时"问任意问题"**稳定快速可用** + 实时结果卡/点即核验面板**中文友好**，且**不改任何 verified 数值/数据/检索逻辑/点即核验忠实逻辑**。

【背景（人类实测旗舰 demo 后指出 + 总指挥读码定位）】
1. **实时"问任意问题"时好时坏**（非检索/语料问题，检索引擎与 6.4 万篇语料正常）：根因 `src/scholarloop/demo/realtime.py`——`:55` `timeout_s=45.0`；`:119-120` `if elapsed > timeout_s: return unavailable("...超过预算阈值...")` **把已算好的结果丢弃**；`:75` 每次调用 `BM25Retriever(docs)` **现场重建 6.4 万篇 BM25 索引**、`:76/:95` 每次重载 Dense/CrossEncoder 模型，冷启动/网络稍慢即 >45s 被误杀（总指挥实测：流水线真返 10 条、~30s 压线、评委点下去半数概率见"不可用"）；`unavailable()`（`:29-39`）**硬编码 cost=0** 显示误导。
2. **实时结果卡 + 点即核验面板满屏英文/黑话**（M140 双语/M160 去黑话只覆盖**已验证证据卡**，这两个 **JS 现场渲染面板没动到**）：`design.py:133`（`Question was decomposed into`）、`:134`（`#N · paper X · score Y` / `Ranking signal: bm25=1.000*0.10...` / `Authors/year/DOI stay for manual verification unless an offline verified cache is available`）、`:147`（`Manual verification required.` / `If the source sentence cannot be matched exactly, ScholarLoop does not highlight or guess`）；状态码 `source_text.py:62`（`manual_review_reason="source_field missing or not locally verifiable"`）。**人类裁定：论文标题/摘要保留英文（SCI），旁边 UI 解释必须中文。**

【最高优先级 · 红线】
1. **实时稳定可用且结果等价（承重）**：缓存复用后实时**稳定快速返回**真实排序结果；**断言缓存 vs 未缓存对同一 query 结果逐条相同**（相同 corpusid/score/排序/reason）——**提速只缓存复用，绝不改检索逻辑/融合权重/结果**。
2. **冻结评测零变化（承重）**：`reports/m040/results.json` sha 仍 **6eb81c83…**、`reports/m060/results.json` sha 仍 **bb309155…**；A-v2 检索逻辑/权重/缓存键不变；**realtime 改动绝不触碰 m040/m060 评测产物或缓存键**（cross-encoder 实时缓存写 `reports/m100` 为 M150 已标 volatile，不得外溢到 m040/m060）。
3. **点即核验忠实不破 + 中文化不改 verified 语义（承重）**：`build_studio_fidelity` 复跑 PASS（span_mismatch=0、baseline_mismatch=0、trail_fabrication=0、图确定性两渲染逐字相等）；中文化**只在 JS 显示层 + i18n**，**绝不改** `source_text.py`/`interactive.py` 点即核验忠实逻辑、**绝不翻译/改动** verified 数值、证据原文、char_span、论文标题/摘要。
4. **实时诚实 + 轻栈 + 零密钥零身份**：实时仍标"非 verified 承重"、真失败/超时**优雅回退不编造**、显示真实耗时/调用数（不再硬编码 0）；不引重前端框架/外链字体；offline 默认；零密钥/身份。

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/170-实时演示可用性与中文友好化-计划.md`（**逐条照做**，§2/§6/§8/§10）
- `docs/dev/000-决策日志.md` 顶部「M170 批准」记录（根因 + 三承重 + 红线 + 停机条件）
- **提速对象（非 verified 演示路径）**：`src/scholarloop/demo/realtime.py`（`run_realtime_query`）
- **中文化对象（呈现层）**：`src/scholarloop/demo/{design.py（studio_js 第 133/134/147 行）, i18n.py（zh/en 字典 + EXAMPLE_QUESTIONS）, studio.py（仅扩充传给 JS 的 window.SL_I18N 键）}`
- **冻结只读复用**：`src/scholarloop/demo/{source_text.py, interactive.py, assemble.py, enrich_view.py}`（点即核验/真值忠实逻辑，**只复用不改**）；`src/scholarloop/retrieval/`、`src/scholarloop/rank/`（检索类逻辑/权重，**只调用缓存、不改**）；`reports/m010..m160`（数据只读，m040/m060 评测+缓存键冻结）

【本轮要做（按 §6/§7 顺序）】
1. **T1 · 实时缓存提速** `realtime.py`：把 `BM25Retriever`/`DenseV2Retriever`/`CrossEncoderReranker`/语料 **跨调用缓存复用**（模块级或惰性单例，首次构建后续秒级，自行决定实现）；**仅缓存复用、不改检索逻辑/权重**。产出 `reports/m170/cache_equivalence.json`（缓存 vs 未缓存对同一 query 结果逐条相同）。
2. **T2 · 预算放宽 + 不丢已算结果 + 诚实成本** `realtime.py`：放宽/重构 `timeout_s`（如 45→180）使**已算完的结果不被丢弃**；真超时/失败仍优雅回退、且**显示真实耗时/调用数（不再硬编码 cost=0）**；可选服务启动预热一次。产出 `reports/m170/realtime_examples.json`（示例查询稳定返回 ≥5 条 + 真实成本）。
3. **T3 · 实时结果卡中文友好化** `design.py(133/134)` + `i18n.py` + `studio.py(传键)`：`Question was decomposed into`→"已将问题拆解为"；`#N · paper X · score Y`→"第N名 · 论文X · 综合得分Y"；`Ranking signal: bm25=1.000*0.10...`→中文"排序依据"标签（原始权重串折叠进"技术细节"或简化中文化）；`Authors/year/DOI stay for manual verification...`→中文"作者/年份/DOI 需人工核验（除非有离线已核验缓存）"；**保留英文论文标题/摘要**；走 i18n 使 EN 版仍可用。
4. **T4 · 点即核验面板中文化** `design.py(147)` + `i18n.py`：`Manual verification required. ... does not highlight or guess`→中文解释（把"零幻觉：本地找不到可精确匹配的原句时，绝不高亮、绝不猜测"讲清楚）；`manual_review_reason` 等后端状态码**在 JS 显示层映射为中文**，**不改 `source_text.py`/`interactive.py`**。
5. **T5 · 示例查询稳定可检索** `i18n.py EXAMPLE_QUESTIONS`：校验每个 chip 提速后**稳定返回 ≥5 条真实结果**，替换任何不稳定项为 LitSearch 域内稳定项；可加简短中文提示。
6. **T6 · 承重复验 + 合规 + 复盘**：产出 `reports/m170/{frozen_eval_invariance.json,studio_fidelity.json,localization.json,demo_replay.json,smoke.txt,secret_scan.json,validation_summary.json}`——证明 m040/m060 sha 不变、点即核验 fidelity PASS、中文化后 verified 数值/证据未被译、M080/M120 复跑 PASS；无密钥/身份；上游 m010–m160 非 volatile 未变；全量 `pytest tests/ -q` 通过；写 `docs/dev/retrospectives/170-实时演示可用性与中文友好化-复盘.md`（提速前后耗时/稳定性→中文化清单→冻结评测零变化→承重不回退证据）。

【硬红线（不得改动）】
- §8 三承重：①**实时稳定可用且结果等价**（缓存 vs 未缓存逐条相同）；②**冻结评测零变化**（m040 sha=6eb81c83 / m060 sha=bb309155 / A-v2 逻辑/权重/缓存键不变）；③**点即核验忠实不破 + 中文化不改 verified 语义**（span_mismatch=0、忠实逻辑不改、verified 数值/证据/标题摘要不被译）。
- 实时提速**只缓存复用**，绝不改检索逻辑/权重/结果；中文化**只改显示层**；实时诚实非 verified + 真失败优雅回退不编造；轻栈无框架/外链；零密钥零身份。
- 只允许写：`src/scholarloop/demo/{realtime.py, design.py, i18n.py, studio.py}`（studio 仅扩 window.SL_I18N 键、不改 verified 渲染语义）、`tests/test_m170_*.py`（**不改** `test_m010..m160`）、`reports/m170/**`、复盘文件。**不改** `demo/{source_text,interactive,assemble,enrich_view}.py` 既有逻辑、`retrieval/`/`rank/` 检索类逻辑/权重、m040/m060 评测产物/缓存键、各模块判据、任何 verified 数值。

【可自行决定（§10 预算内）】缓存复用实现（模块级/惰性单例）；预算阈值与预热策略；中文措辞；"排序依据"折叠/简化方式；示例查询选取与中文提示。

【必须停机上报（写 `reports/m170/` 停机报告，交总指挥）】
- 缓存后实时结果与未缓存**不一致** → 停机；任一冻结评测 sha（m040/m060）变化 → 停机；中文化**只能靠改忠实逻辑或 verified 值**才能做 → 停机；实时**只能靠编造**才能返回 → 标限制或停机；需改 M010–M160 产物或承重判据；材料无法去身份。

【交付】完成后：`demo/{realtime,design,i18n,studio}.py`；`pytest tests/ -q` 通过记录；`reports/m170/{realtime_examples.json,cache_equivalence.json,frozen_eval_invariance.json,studio_fidelity.json,localization.json,demo_replay.json,smoke.txt,secret_scan.json,validation_summary.json}`；**m040/m060 sha 不变 + 缓存等价 + verified 不被译证据**；写复盘；把 `170` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第二十三次初查）。
