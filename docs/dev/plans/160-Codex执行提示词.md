# 160 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息。
> 联网授权沿用（但本模块**不需要**新发在线调用——真值只读 M050 已 verified 缓存）。
> **核心特征**：纯呈现层精修——把"工程顶尖"翻译成"评委一眼眼前一亮·一等奖水准"。**承重 = ①呈现不破忠实/确定性 ②M050 真值接入零新增伪造 ③去黑话不改 verified 语义。** 绝不碰任何已 verified 的 F1/数据/承重判据。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/160-旗舰评委级呈现精修-计划.md`（状态 approved）——把旗舰 `/studio` 从"工程师视角的透明调试页"升级为"评委一眼眼前一亮的可信检索作品"，**且不改任何 verified 数值/数据/承重判据**。

【背景（人类实测旗舰 demo 后指出 + 总指挥读码定位）】
当前 `/studio` 工程底子顶尖（确定性/零伪造/冻结评测零变化都已独立验证为真），但**面向评委的呈现漏出大量开发者内部细节**，对不懂技术的评委像调试输出，拉低专家分：
1. **dev 黑话**：`i18n.py:26`(`realtime_desc`=端点/api/search?q=...+函数名 run_realtime_query)、`:31`(`field_hint`=source_text[char_span]==value)、`:42`(`span_contract`)、`:37`(`stable_graph_desc`=viewBox/零力导向)、`:33`(`trail_desc`=artifact 路径)；`studio.py:189`(裸模块码 `M020·M040·M060…`)、`:206`(`Endpoint: /api/graph_stable`)、`:208`(`client_force_simulation=false`)。
2. **满屏「需人工核验」+ 机器串**：`studio.py:_verified_fields_html`(L122-149) 把 `field.resolution_hint`(机器串 `online_connector_required_for_author_year_source_doi`)直接显示。
3. **裸 JSON + Windows 路径**：`studio.py:_trail_html`(L152-162) `<pre>{_json_preview}</pre>` + `source_paths` 文件路径 pill(`reports\m040\results.json`)。
4. **关系图字号过小**：`graph_layout.py:176` `font-size="12"`，viewBox 1180px 缩到 ~500px 卡片 ≈ 5px 不可读。

【最高优先级 · 红线】
1. **呈现不破忠实/确定性（承重）**：`build_studio_fidelity` 复跑仍 PASS——span_mismatch=0、baseline_mismatch=0、trail_fabrication=0、**图两次渲染坐标逐字相等**（图字号/视觉改后用 `verify_graph_determinism` 复验逐字相等、NaN=0）。
2. **M050 真值接入零新增伪造（承重）**：证据卡 `authors_year`/`source_or_doi` 的真值**只取** `reports/m050/enriched/<query_id>.json` 已 verified 缓存（按 `(query_id, corpusid)` 匹配，status「经外部来源支持」、带 OpenAlex 出处、fabricated_count=0）；**显示值必须逐字等于该缓存**；**M050 未匹配/未解析的字段保持诚实「需人工核验」（友好产品文案，不显示机器串）**；**绝不新发任何在线调用、绝不编造作者/年份/DOI**；fabricated 必须仍=0。
3. **去黑话不改 verified 语义**：文案改产品语言，但 **verified 数值（0.1312/0.0964/0.1972 等）、证据原文、char_span、论文标题/摘要逐字不变**；技术契约（端点/函数名/`source_text[char_span]==value`）**折叠进可展开的"给技术评审"附录**——保留透明但不占主画面。
4. **轻栈 + 离线 + 零密钥零身份**：不引重前端框架/外部 CDN/外链字体（字体系统栈/内置）；offline 默认；零密钥/身份；i18n 数值未被译、a11y 状态完整（loading/empty/error/skeleton/深色/reduced-motion）。**绝不为观感牺牲忠实/确定性。**

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/160-旗舰评委级呈现精修-计划.md`（**逐条照做**，§2/§6/§8/§10）
- `docs/dev/000-决策日志.md` 顶部「M160 批准」记录（动因 + 三承重 + 红线 + 停机条件）
- **精修对象（未冻结的呈现层）**：`src/scholarloop/demo/{studio.py, i18n.py, design.py, graph_layout.py}`（端点 `/studio`/`/api/search`/`/api/graph_stable`）
- **真值来源（已 verified · 只读）**：`reports/m050/enriched/<query_id>.json`（`cards[].corpusid` + `cards[].fields.authors_year/source_or_doi.value` 真值 + status + 出处；M050=verified，**只读不改**）
- **冻结只读复用**：`src/scholarloop/demo/{source_text.py, interactive.py, realtime.py, assemble.py, app.py}`（M080/M120/M130/M150 verified 逻辑，**只复用不改**）；`reports/m010..m150`（数据/边界，只读）

【本轮要做（五支柱 · 按 §6/§7 顺序）】
1. **T1 · 去 dev 黑话 → 产品语言** `i18n.py` + `studio.py`：把 `realtime_desc`/`field_hint`/`span_contract`/`stable_graph_desc`/`trail_desc` 与 studio 硬编码的 `Endpoint:`/`client_force_simulation=false`/裸模块码 `M020·M040…` 改写为**讲价值的产品文案**（例：实时区改"输入任意研究问题，系统实时拆解并检索 6.4 万篇文献给出排序推荐；服务不可用时诚实留空、绝不编造"；点即核验改"点任意证据字段，高亮原文中支撑它的那一句，对不上则诚实标注待核验"）；技术契约/端点/函数名折叠进**可展开的"给技术评审"附录**（`<details>`）。产出 `reports/m160/presentation_polish.json`（断言主画面无端点/函数名/裸模块码/裸 JSON 路径、附录可展开、verified 数值未变）。
2. **T2 · 证据卡接 M050 真值（核心）** 新建 `src/scholarloop/demo/enrich_view.py`（**只读** `reports/m050/enriched/`，按 (query_id,corpusid) 取真作者/年份/出处）+ 改 `studio.py:_verified_fields_html`：`authors_year`/`source_or_doi` 若 M050 有真值 → 显示**真实值 + 来源徽章（经 OpenAlex 核验）**；否则显示**友好「需人工核验」产品文案**（不显示机器串）。产出 `reports/m160/fabrication_zero.json`（每卡每字段：显示值逐字==M050 缓存值 / 或诚实占位；fabricated=0；真值覆盖数 vs 诚实占位数）。
3. **T3 · 轨迹去裸 JSON → 可读化** `studio.py:_trail_html` + `design.py`：拆解子查询 → 干净标签列表；溯源 → 人话标签（"来自 M040 检索结果 / M020 证据卡"）；**原始 JSON 与文件路径折叠进 `<details>` "查看原始证据"**（技术评审可查、默认不占画面）。
4. **T4 · 关系图可读** `graph_layout.py` + `design.py`：放大 viewBox 内标签字号（如 12→18~22）、加大图卡尺寸、加图例、防标签重叠（仅视觉/布局参数，**不改坐标确定性算法**）。产出 `reports/m160/graph_determinism.json`（`verify_graph_determinism` 两渲染坐标逐字相等、SVG 逐字相等、NaN=0）。
5. **T5 · premium 信任叙事前置 + 承重复验** `studio.py` + `design.py`：hero 用产品语言讲价值主张 + **信任数据条（只用 verified 数字**：fabrication=0 / 6.4 万篇语料 / 两公开基准官方 gold 显著胜 BM25）+ 把点即核验做成醒目引导式主交互（复用 M120 verified `verify_value_span`，不改其逻辑）。复验产出 `reports/m160/{studio_fidelity.json, i18n_coverage.json, a11y_check.json, demo_replay.json}` 全 PASS（M080 verify + M120 span/trail 复跑 PASS）。
6. **T6 · 合规 / 可复现 / 复盘**：无密钥/身份/外链；offline 重放一致；上游 `reports/m010..m150` sha 未变；全量 `pytest tests/ -q` 通过；写 `docs/dev/retrospectives/160-旗舰评委级呈现精修-复盘.md`（黑话清理清单→M050 真值覆盖率→零伪造证据→承重不回退证据 + 截图说明）。

【硬红线（不得改动）】
- §8 三承重：①**呈现不破忠实/确定性**（studio_fidelity PASS + 图两渲染坐标逐字相等）；②**M050 真值接入零新增伪造**（显示值逐字==M050 缓存、未解析诚实占位、fabricated=0、绝不新发在线调用/编造）；③**去黑话不改 verified 语义**（数值/原文/char_span/标题摘要逐字不变）。
- 纯呈现层——**绝不改任何 verified F1/数据/冻结评测/承重判据**；i18n 数值未被译；轻栈无框架/CDN/外链字体；零密钥零身份；不为观感牺牲忠实/确定性。
- 只允许写：`src/scholarloop/demo/{studio.py, i18n.py, design.py, graph_layout.py}`（graph_layout 仅视觉/字号、不破确定性）、新建 `src/scholarloop/demo/enrich_view.py`（只读 m050 enriched）、`tests/test_m160_*.py`（**不改** `test_m010..m150`）、`reports/m160/**`、复盘文件。**不改** `demo/{source_text,interactive,realtime,assemble,app}.py` 既有逻辑、M010–M150 数据产物（含 m050 enriched 只读）、各模块判据、任何 verified 数值。

【可自行决定（§10 预算内）】产品文案措辞；premium 版式/视觉层级；信任数据条选取（仅 verified 数字）；附录折叠/"查看原始证据"交互；图例样式/字号取值；来源徽章样式。

【必须停机上报（写 `reports/m160/` 停机报告，交总指挥）】
- 证据卡真值**只能靠新发在线调用/编造**才能填 → 保持诚实占位，绝不编造；任一显示值 ≠ M050 已 verified 缓存 → 停机；去黑话/重排**破坏图确定性或点即核验忠实** → 修到不破或停机；需引重前端框架/外部 CDN/外链字体；需改 M010–M150 产物或承重判据或任何 verified 数值；材料无法去身份。

【交付】完成后：精修后 `demo/{studio,i18n,design,graph_layout}.py` + 新建 `demo/enrich_view.py`；`pytest tests/ -q` 通过记录；`reports/m160/{presentation_polish.json, fabrication_zero.json, studio_fidelity.json, graph_determinism.json, i18n_coverage.json, a11y_check.json, demo_replay.json, smoke.txt, secret_scan.json, validation_summary.json}`；**M050 真值零伪造证据 + 上游 m010..m150 sha 不变证据**；写复盘；把 `160` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第二十二次初查）。
