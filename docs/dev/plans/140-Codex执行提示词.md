# 140 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥/身份信息。
> 联网授权沿用（实时模式需 LLM 端点）。
> **核心特征**：旗舰二次升级（双语 i18n + shadcn 级设计 + 多角度打磨）。承重 = **精进不回退**（图确定性两渲染坐标仍逐字相等、点即核验仍 mismatch=0、M080/M120 复跑仍 PASS）。i18n 仅译 UI 文案、绝不触 verified 数值。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次执行**已批准**的计划
`docs/dev/plans/140-旗舰双语与顶尖设计精进-计划.md`（状态 approved）——把 M130 旗舰 Demo 从"已顶尖"再推到**多角度无可挑剔的高水准**：双语 + shadcn 级设计 + 实时 UX + 无障碍 + 信任叙事。

【背景 + 调研依据】
人类要求"再次全方位提升、从任何角度达到非常好水准、中英结合、基于 GitHub 顶尖网页"。**GitHub/网络调研**：顶尖高级感来自 **shadcn/ui·Radix·HeroUI 式中性令牌色板 + 柔和阴影 + 一致圆角刻度 + 焦点环 + 深色模式（CSS 变量）+ 无障碍**（克制+一致而非花哨）；premium 模板铁律=「无半成品页/全响应/每个状态都设计过」。**这些为 React/Tailwind，本项目不引框架——把设计原则 port 到原生 CSS。** **中英结合**：评审为中文受众 → **UI 中文为主 + 中/EN 切换（i18n）**，论文内容保持英文、技术术语双语。

【最高优先级 · 红线】
1. **精进不回退（承重）**：M130 旗舰已 implemented+初查 PASS（图确定性稳定 / 点即核验忠实 / 实时诚实）。本轮精进后**必须复验仍 PASS**：①图确定性——精进/换皮后**两次渲染坐标仍逐字相等、端侧仍零力导向模拟、无 NaN**（`graph_layout` 可换视觉皮肤/着色，**不可破确定性冻结坐标**）；②点即核验/基准忠实——高亮**仍逐字等于** char_span 切片且 ==value（mismatch=0）、基准展示值 ==verified JSON；③**M080 verify + M120 span/trail fidelity 复跑仍 PASS**。
2. **i18n 红线**：i18n **只译 UI 文案**（标题/按钮/标签/状态/提示/空态/错误）；**绝不翻译或改动任何 verified 数值、证据原文、char_span、论文标题/摘要内容**；论文内容保持英文原文。
3. **轻栈 + 离线可复现**：**不引重前端框架（React/Vue/Tailwind 构建）、不引外部 CDN、不外链字体**（字体用系统栈或内置）；offline 默认。
4. **实时诚实 + 零密钥零身份**：实时结果标"非 verified 承重"+ 成本披露 + 失败优雅回退不编造；零密钥/身份；缺失标"需人工核验"/空状态不补写。**绝不为观感/动效牺牲忠实/稳定。**

【唯一真源】先读这些，以它们为准：
- `docs/dev/plans/140-旗舰双语与顶尖设计精进-计划.md`（**逐条照做**，§2/§6/§8/§10）
- `docs/dev/000-决策日志.md` 顶部「M140 批准」记录（六支柱 + 红线 + 中英决策）
- **精进对象（M130，未冻结）**：`src/scholarloop/demo/{studio.py,design.py,graph_layout.py}`（端点 `/studio`/`/api/search`/`/api/graph_stable`）
- **冻结只读复用**：`src/scholarloop/demo/{source_text.py,interactive.py,realtime.py,assemble.py,app.py}`（M080/M120 verified 逻辑，**只复用不改**）；`reports/m020|m070|m100|m110`（数据/边界，只读）

【本轮要做（六支柱 · 按 §6/§7 顺序）】
1. **T2 先行 · 设计系统精进** `design.py`：重构令牌——中性色板（background/foreground/muted/border/primary/accent，明确对比度）、间距阶梯（4/8 节奏）、字体阶梯+配对（系统 sans 正文 + mono 数字/代码）、圆角刻度、柔和阴影刻度、**焦点环**；**深色模式**（CSS 变量 light/dark 切换 + 尊重 `prefers-color-scheme`）；统一组件（卡片/徽章/输入/按钮/标签页/表格/骨架）。
2. **T1 · 双语 i18n** `src/scholarloop/demo/i18n.py`：`zh`/`en` 字典 + 取词函数 + **中/EN 切换**（`?lang=zh|en`，默认 zh，确定性无外部依赖）；旗舰 UI chrome 全部走 i18n；技术术语双语并排；产出 `reports/m140/i18n_coverage.json`（无硬编码漏译、**断言 verified 数值/证据未被译**）。
3. **T3 · 实时搜索 UX 精进** `studio.py` + `/api/search`：**示例问题 chips**（点击填入 hero 输入）、**渐进式"思考"状态/骨架屏**（拆解→检索→排序可视）、结果卡优雅排版（标题/摘要/理由/分数/成本）、空/错/超时态；实时诚实标注。
4. **T4 · onboarding/无障碍/响应式/动效** `studio.py`：清晰 hero（价值主张+怎么用）+ 首次引导 + **全状态设计（无半成品）**；可访问性（语义/ARIA/键盘焦点/对比）；响应式（桌面/平板/窄屏）；**克制动效**（CSS 过渡、尊重 `prefers-reduced-motion`、**零抖动**）；产出 `reports/m140/a11y_check.json`。
5. **T5 · 信任叙事前置 + 承重复验**：旗舰显著位呈现**点即核验**（fabrication=0 现场可验）+ **自我证伪方法论**（M100 频率消融，按 M110 边界）；**复验承重**——产出 `reports/m140/graph_determinism.json`（两渲染坐标相等、零模拟、无 NaN）+ `reports/m140/studio_fidelity.json`（点即核验 mismatch=0、基准值==verified）+ M080/M120 复跑 PASS。
6. **T6 · 合规 / 可复现 / 复盘**：无密钥/身份/外链；offline 重放一致；上游 M010–M130 sha 未变；全量 `pytest tests/ -q` 通过；写 `docs/dev/retrospectives/140-旗舰双语与顶尖设计精进-复盘.md`（GitHub 调研→落地 + 截图说明 + 承重不回退证据）。

【硬红线（不得改动）】
- §8 承重①**图确定性不回退**（两渲染坐标逐字相等、端侧零模拟、无 NaN）；②**点即核验/基准忠实不回退**（mismatch=0、基准值==verified JSON）；③M080/M120 复跑仍 PASS。
- i18n 仅译 UI 文案、**绝不触 verified 数值/证据**；轻栈无框架/CDN/字体外链；实时诚实；零密钥零身份；不为观感牺牲忠实/稳定。
- 只允许写：`src/scholarloop/demo/{studio.py,design.py,graph_layout.py,i18n.py}`（**不改** `source_text.py`/`interactive.py`/`realtime.py`/`assemble.py` 既有逻辑；app 路由仅**新增** `?lang` 透传不改既有处理）、`tests/test_m140_*.py`（**不改** `test_m010..m130`）、`reports/m140/**`、复盘文件。

【可自行决定（§10 预算内）】令牌取值/配色/深色调色/字体阶梯/动效时长；i18n 切换方式与字典措辞；示例问题选取；版式/组件/微交互细节；关系图视觉皮肤（不破确定性）。

【必须停机上报（写 `reports/m140/` 停机报告，交总指挥）】
- i18n **只能靠改 verified 数值/证据**才能做 → 上报；设计/动效精进**破坏图确定性或点即核验忠实** → 修到不破或停机；需引重前端框架/外部 CDN/字体外链才能达成 → 上报；需改 M010–M120 产物或 M080/M120/M130 承重判据；材料无法去身份；任何只能靠虚构填的字段。

【交付】完成后：精进后 `demo/{studio.py,design.py,graph_layout.py}` + `demo/i18n.py`（+`?lang` 参数）；`pytest tests/ -q` 通过记录；`reports/m140/{graph_determinism.json,studio_fidelity.json,i18n_coverage.json,a11y_check.json,smoke.txt,secret_scan.json,validation_summary.json}`；**M080 verify + M120 fidelity 复跑 PASS 证据**；写复盘；把 `140` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查（第二十次初查）。
