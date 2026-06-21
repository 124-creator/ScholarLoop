# 130 · Demo 旗舰级全面顶尖化 · 执行复盘

- 状态：implemented（待总指挥初查，未自行宣布 verified）
- 日期：2026-06-21
- 执行边界：只新增 M130 Studio/稳定图/报告/测试，并在 `app.py` 增加 `/studio`、`/api/search`、`/api/graph_stable` 三个端点；未回改 M080/M120 既有逻辑与上游冻结产物。

## 落地对照

| 计划要求 | 落地文件/证据 | 结论 |
|---|---|---|
| 旗舰级视觉与轻量设计令牌 | `src/scholarloop/demo/design.py`；`/studio` 内联 CSS/JS，无重前端框架 | implemented |
| 实时自主搜索主体体验 | `src/scholarloop/demo/studio.py`；`/api/search?q=...` 仅包装既有 `run_realtime_query` | implemented |
| 实时诚实披露 | `reports/m130/search_smoke.txt`：默认离线时 `results=0`、`verified_load_bearing=False`、成本为 0 | PASS |
| 关系图稳定化 | `src/scholarloop/demo/graph_layout.py`；`reports/m130/graph_determinism.json` | PASS |
| 点即核验/基准忠实 | 复用 M120 span 校验；`reports/m130/studio_fidelity.json` mismatch=0 | PASS |
| 不破 M080/M120 | `reports/m130/m080_verify_replay/fidelity_audit.json`、`reports/m130/m120_span_fidelity.json`、`reports/m130/m120_trail_fidelity.json` | PASS |
| 全量测试 | `reports/m130/pytest.txt` | 56 passed |

## 关键实现说明

1. **稳定图**：采用确定性 5 列冻结坐标，服务端一次性输出坐标与静态 viewBox SVG；浏览器端不运行力导向/物理模拟，hover/focus 只切 CSS class，不改坐标。
2. **Studio 忠实性**：高亮仍只允许 `source_text[char_span] == value`；作者、年份、DOI 等无法由离线证据定位的字段仍显示需人工核验，不补写。
3. **实时搜索**：默认保持离线关闭。`/api/search` 仅把既有实时路径做成旗舰 UX，明确标注“实时·非确定性·非 verified 承重”，失败/禁用时返回空结果和成本披露，不伪造推荐。
4. **既有面板保留**：`/`、`/pro`、`/graph` 仍可访问；M130 只新增 `/studio` 旗舰视图与两个 API。

## 验证证据

- `reports/m130/graph_determinism.json`：`status=PASS`，坐标与 SVG 两次渲染逐字相等，invalid edge=0，NaN=0，`client_force_simulation=false`。
- `reports/m130/studio_fidelity.json`：`status=PASS`，span mismatch=0，baseline mismatch=0。
- `reports/m130/m080_verify_replay/fidelity_audit.json`：`status=PASS`。
- `reports/m130/m120_span_fidelity.json`：`status=PASS`，mismatch=0。
- `reports/m130/m120_trail_fidelity.json`：`status=PASS`，fabrication=0。
- `reports/m130/secret_scan.json`：通过，未发现密钥/身份信息。
- `reports/m130/pytest.txt`：`56 passed in 118.72s`。

## 剩余风险

- 实时路径仍依赖可选 LLM/检索模型环境；默认关闭时只能演示诚实空态。该路径不是 verified 承重证据。
- Studio 视觉为轻量内联实现，未引入截图级像素回归；当前用 smoke + fidelity + 全量 pytest 保证功能与忠实性。
