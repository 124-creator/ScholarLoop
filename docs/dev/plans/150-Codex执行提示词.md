# 150 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息。
> 联网授权沿用（实时模式需 LLM 端点）。
> **核心特征**：版本兼容热修——修通实时"问任意问题"搜索。**最高承重红线 = 冻结评测行为完全保持（一个 verified 数字都不许变）。** 触碰 M040 冻结文件 `dense_v2.py`，纪律从严。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/150-实时搜索路径热修-计划.md`（状态 approved）——修通实时自主搜索（§3.1 切题主体验），且**一个冻结评测数字都不许变**。

【根因（总指挥已定位，先懂再修）】
人类点旗舰"运行实时搜索"得 `AttributeError`（系统诚实空态、未编造）。根因 = `src/scholarloop/retrieval/dense_v2.py:63`：
```
dim = getattr(self.model, "get_sentence_embedding_dimension", self.model.get_embedding_dimension)()
```
Python `getattr(obj, name, 默认)` 的**默认值被 eager 求值**；环境升级到 `sentence-transformers 5.1.2`（**只有 `get_sentence_embedding_dimension`、无旧 `get_embedding_dimension`**）后，eager 求值默认值 `self.model.get_embedding_dimension` 即抛 AttributeError。离线评测走缓存从不触发；实时给新问题**现场编码**才命中。

【最高优先级 · 红线】
1. **冻结评测行为完全保持（最高承重）**：修后 `_model_version()` 返回的 dim 仍 **384**（bge-small）、`_fingerprint`/**缓存键逐字不变**、`reports/m040/results.json` sha 仍 **6eb81c8304a80f53…**、A-v2 F1 仍 **0.1312/0.1972**、A-v2 离线排序**逐查询不变**。**任一冻结评测数值变化 → 立即停机，绝不交改了 F1 的修复。**
2. **修复严格限版本兼容**：只改版本兼容点（eager-default / 改名的 API），**绝不改检索逻辑/融合权重/缓存键/任何 verified 数值**。
3. **实时真可用且诚实**：修通后对新问题真返回拆解+top结果（标题/摘要/理由/分数）+成本；**非 verified 承重标注**；失败/超时**仍优雅回退不编造**。
4. **不破 demo + 零密钥零身份**：M080/M120/M130/M140 demo 承重（图确定性 + 点即核验忠实）复跑仍 PASS；零密钥/身份。

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/150-实时搜索路径热修-计划.md`（**逐条照做**，§2/§6/§8/§10）
- `docs/dev/000-决策日志.md` 顶部「M150 批准」记录（根因 + 最高承重红线）
- **修复对象**：`src/scholarloop/retrieval/dense_v2.py`（第 63 行同类兼容点）；**实时路径** `src/scholarloop/demo/realtime.py`（`run_realtime_query`）；必要时 `src/scholarloop/retrieval/bm25.py`/`src/scholarloop/rank/rerank.py`（**仅版本兼容**）
- **冻结基准**：`reports/m040/results.json`（sha 6eb81c83、A-v2 F1 0.1312/0.1972，**修后须逐字不变**）

【本轮要做（按 §6/§7 顺序）】
1. **T1 · 修 eager-default（dense_v2.py:63）**：改为**惰性安全取词**——优先 `get_sentence_embedding_dimension`，缺失再退 `get_embedding_dimension`，**不 eager 求值缺失属性**（如 `getter = getattr(m,"get_sentence_embedding_dimension",None) or getattr(m,"get_embedding_dimension",None); dim = getter()`）。**单测断言**：修前后 `_model_version()` 返回值、`_fingerprint`、dense 缓存键**逐字相等**（dim=384 不变）。
2. **T2 · 端到端跑通实时**：`SCHOLARLOOP_REALTIME_ENABLED=1` 实跑 `run_realtime_query('large language model compression')`，修掉**沿途所有版本兼容 bug**（编码/重排/接口签名等）直到真返回 top 结果；**仅版本兼容修复、不改检索逻辑/权重**。产出 `reports/m150/realtime_run.json`（真实拆解+top结果+成本，标注非 verified）。
3. **T3 · 冻结评测行为保持复验（最高承重）**：证明 M040/M060 评测**完全不变**——重核 `reports/m040/results.json` sha=6eb81c83、A-v2 F1=0.1312/0.1972、dense 缓存键/dim 不变、A-v2 离线排序逐查询不变（可用现有 A-v2 评测/缓存比对）。产出 `reports/m150/frozen_eval_invariance.json`（全项 unchanged=true）。**任一项变 → 停机。**
4. **T4 · 实时诚实 + demo 复验**：实时真结果诚实标注 + 成本披露 + 失败优雅回退不编造；复跑 M080 verify + M120 span/trail + M130/M140 图确定性 + studio fidelity 仍 PASS。产出 `reports/m150/demo_replay.json`。
5. **T5 · 合规 / 可复现 / 复盘**：无密钥/身份；上游 reports/m010..m140 sha 未变；全量 `pytest tests/ -q` 通过；写 `docs/dev/retrospectives/150-实时搜索路径热修-复盘.md`（根因→修复→冻结评测零变化证据 + 实时端到端结论 + 记录 sentence-transformers 升级的环境漂移）。

【硬红线（不得改动）】
- §8 最高承重**冻结评测行为保持**（sha/F1/dim/缓存键/逐查询排序逐字不变）；②实时真可用且诚实；③demo 承重复跑 PASS。
- 修复**仅限版本兼容**，绝不改检索逻辑/权重/缓存键/verified 数值；零密钥零身份。
- 只允许写：`src/scholarloop/retrieval/dense_v2.py`（仅兼容点）、必要时 `src/scholarloop/retrieval/bm25.py`/`src/scholarloop/rank/rerank.py`/`src/scholarloop/demo/realtime.py`（仅兼容）、`tests/test_m150_*.py`（**不改** `test_m010..m140`）、`reports/m150/**`、复盘文件。**不改** A-v2 逻辑/权重/缓存键、离线评测产物、各模块判据。

【可自行决定（§10 预算内）】安全取词写法；端到端版本兼容修复细节（仅兼容）；实时结果展示细节。

【必须停机上报（写 `reports/m150/` 停机报告，交总指挥）】
- 修复**只能靠改检索逻辑/权重/缓存键/verified 数值**才能跑通 → 停机，绝不改冻结评测；任一冻结评测数值（sha/F1/dim/缓存键/逐查询排序）变化 → 停机；实时**只能靠编造**才能返回结果 → 标限制或停机；需改 M010–M140 产物或判据；材料无法去身份。

【交付】完成后：版本兼容修复 `dense_v2.py`（+ 必要兼容点）；`pytest tests/ -q` 通过记录；`reports/m150/{realtime_run.json,frozen_eval_invariance.json,demo_replay.json,smoke.txt,secret_scan.json,validation_summary.json}`；**m040 sha=6eb81c83 不变 + A-v2 F1 不变证据**；写复盘；把 `150` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第二十一次初查）。
