# 020 · B-lite 证据矩阵层 · 执行复盘

- 模块：M020 B-lite 证据矩阵层
- 执行方：Codex
- 日期：2026-06-19
- 计划状态：implemented（待总指挥初查 / 人类终验；本复盘不宣布 verified）

## 1. 执行范围

按 `docs/dev/plans/020-B-lite证据矩阵层-计划.md` rev1 执行 T0–T6：

- T0：复用 `scholarloop.config` 自加载凭证；只读加载 `reports/m010/results.json` 与 LitSearch 语料。
- T1：实现 10 字段 EvidenceCard；LLM 候选抽取后必须通过 char_span grounding 才能标「已有证据支持」。
- T2：实现 4 类证据状态；作者/年份、来源/DOI 固定为非支持状态并带 `online_connector` resolution hint。
- T3：实现论文 × criteria 证据矩阵；命中格必须带可定位 snippet。
- T4：输出逐查询 JSON 与 Markdown 矩阵报告。
- T5：完成 dev 抽样 30 查询 × Top-3 论文零伪造校验。
- T6：完成 pytest、可复现复跑、密钥扫描与本复盘。

## 2. 关键结果

- Status：**PASS**
- dev 查询数：`30`；Top-N：`3`
- fabrication_rate：`0.0`
- matrix_fabrication_rate：`0.0`
- 官方缺失字段合规率：`1.0`（作者/年份、来源/DOI 均非支持 + resolution_hint）
- 字段齐备：`True`
- 可复现 run1==run2：`True`
- M010 上游 hash 未变：`True`
- 密钥扫描命中：`0`

## 3. 状态分布

- 已有证据支持: 673
- 证据不足: 1
- 存在争议: 46
- 需人工核验: 180

## 4. 效率账

- API calls：`90`（每查询 `3.0`）
- total_tokens：`145796`
- P50 / P95 query seconds：`36.46` / `65.76`
- first_run_query_seconds_sum：`1,164.07`

## 5. 证据文件

- 端点预检：`reports/m020/llm_precheck.json`
- 逐查询证据 JSON：`reports/m020/evidence/*.json`（30 个）
- 矩阵报告：`reports/m020/evidence-matrix-report.md`
- grounding：`reports/m020/grounding-report.md`
- 校验汇总：`reports/m020/verification.json`
- 原始 LLM 响应：`reports/m020/raw/llm/`
- pytest：`reports/m020/pytest_console.txt`
- config 自加载：`reports/m020/config_present.txt`

## 6. 失败模式与处理

- LLM 抽取只作为候选；凡 quote 无法在 `title/abstract/full_paper` 精确定位，一律不提升为「已有证据支持」。
- 离线 LitSearch 语料没有作者/年份/来源/DOI 列；对应字段固定为「需人工核验」+ `online_connector_required_for_author_year_source_doi`，未编造。
- 原始响应中存在若干 `.bad-*` 隔离文件，均未复用；最终结果来自可解析响应或确定性 fallback 且全部经 char_span 校验。
- Top-N 当前取 3，是为了在本轮验证中控制 LLM token/延时；代码入口支持扩大到 Top-N=10 复跑。

## 7. 结论

M020 执行完成，零伪造承重墙通过，状态可由 `approved` 推进为 `implemented`。不得由执行方宣布 `verified`；请总指挥基于本轮证据做初查。
