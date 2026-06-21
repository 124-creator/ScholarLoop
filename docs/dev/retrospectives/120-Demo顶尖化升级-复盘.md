# 120 · Demo 顶尖化升级 · 执行复盘

- 状态：implemented（Codex 执行完成；待总指挥初查，不自宣 verified）
- 日期：2026-06-21
- 对应计划：`../plans/120-Demo顶尖化升级-计划.md`

## 1. 实际 diff / 文件列表

### 新增

- `src/scholarloop/demo/source_text.py`
- `src/scholarloop/demo/interactive.py`
- `tests/test_m120_interactive_demo.py`
- `reports/m120/span_fidelity.json`
- `reports/m120/trail_fidelity.json`
- `reports/m120/smoke.txt`
- `reports/m120/m080_verify_replay/**`
- `reports/m120/secret_scan.json`
- `reports/m120/upstream_hashes.json`
- `reports/m120/pytest.txt`
- `reports/m120/validation_summary.json`
- `docs/dev/retrospectives/120-Demo顶尖化升级-复盘.md`

### 修改

- `src/scholarloop/demo/app.py`：只新增 `/api/verify_span`、`/api/trail`、`/pro` 路由与导入；既有 `/`、`/healthz`、`/api/demo`、`/api/metrics`、`/api/gaps`、`/api/graph`、`/graph`、`/api/realtime`、`/api/queries`、`/api/queries/{qid}` 逻辑保持原行为。
- `docs/dev/plans/120-Demo顶尖化升级-计划.md`：状态推进到 `implemented`。

## 2. 网络调研 → 落地对照

| 调研结论 | 本轮落地 |
|---|---|
| 顶尖学术搜索 Agent 需要展示证据综合与决策轨迹 | `/api/trail` 与 `/pro` 渐进式展示查询拆解、排序、证据接地、研究空白候选启发 |
| Agent UX 应逐条展示置信与来源 | `/pro` 对 evidence field 展示 status/source_field/confidence，并保留 source path |
| 光有引用不够，用户通常不点开核对 | `/api/verify_span` 做“点即核验”：source_text[char_span] 与 value 逐字相等才高亮 |
| 视觉精炼要服务可信，不喧宾夺主 | `/pro` 使用轻量内联 CSS/JS，无前端框架；M080 baseline 仍在 `/` |

## 3. Green 证据

### T1 · 点即核验证据链

- 产物：`reports/m120/span_fidelity.json`
- 结果：`status=PASS`，`total_checks=1170`，`highlightable_count=989`，`mismatch_count=0`。
- 解释：所有可高亮字段都满足 `source_text[char_span] == value`；char_span 缺失或不可本地核验的字段只进入“需人工核验/不高亮”路径。

### T2 · 推理/决策轨迹

- 产物：`reports/m120/trail_fidelity.json`
- 结果：`status=PASS`，30 个查询 × 4 步 = 120 步，`fabrication=0`，`missing_source_count=0`。
- 轨迹只 surface verified artifact：M040 查询拆解/排序、M020 证据、M070 候选展示、M100/M110 频率边界。

### T3 · 视觉/交互打磨

- 产物：`reports/m120/smoke.txt`
- 结果：`/pro`、`/api/verify_span`、`/api/trail` 均 200；`/pro` 包含点即核验、轨迹与关系图增强；默认 offline 0-LLM。

### T4 · 不破 M080 / 合规 / 可复现

- M080 verify 复跑：`reports/m120/m080_verify_replay/fidelity_audit.json`，`status=PASS`、`runnable=true`、`faithful=true`。
- 全量测试：`reports/m120/pytest.txt`，`50 passed in 98.13s (0:01:38)`。
- secret/identity 扫描：`reports/m120/secret_scan.json`，`findings_count=0`。
- 上游冻结：`reports/m120/upstream_hashes.json`，`changed_count=0`。

## 4. 验收逐项判定

| 验收项 | 判定 | 证据 |
|---|---|---|
| 点即核验忠实 | PASS | `reports/m120/span_fidelity.json`，mismatch=0 |
| 推理轨迹零编造 | PASS | `reports/m120/trail_fidelity.json`，fabrication=0 |
| 增强视图可运行 | PASS | `reports/m120/smoke.txt` |
| 不破 M080 fidelity | PASS | `reports/m120/m080_verify_replay/fidelity_audit.json` |
| offline / 零身份零密钥 | PASS | `/healthz` + `reports/m120/secret_scan.json` |
| 上游未污染 | PASS | `reports/m120/upstream_hashes.json` |
| 全量测试 | PASS | `reports/m120/pytest.txt` |

## 5. 偏差与未决项

- `reports/m120/secret_scan.json` 排除了 `reports/m120/m080_verify_replay/**`，因为 M080 replay 审计文件内部会列出禁用身份词字典；该 replay 是否通过由其自身 `submission_identity_scan` 与 `fidelity_audit` 记录。
- M120 未改 M080 `render.py` / `verify.py`，只在 `app.py` 增加新路由；增强视图是 additive surface。
- `/api/trail` 不透传 M080 assemble 中旧的研究空白指标边界，改为显式展示 M100/M110 频率边界，避免旧口径误导。

## 6. 交付说明

本轮已完成点即核验、决策轨迹、`/pro` 轻量增强、M080 verify 复跑、全量测试与报告收束。当前状态为 `implemented`，等待总指挥第十八次初查；本复盘不宣布 verified。

