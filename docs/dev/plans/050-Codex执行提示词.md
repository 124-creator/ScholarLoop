# 050 · 交给 Codex 的执行提示词（dispatch）

> 用法：把下面「提示词正文」整段交给 Codex。本文件不含任何密钥，只引用环境变量名。
> 人类已确认：**Codex 可联网（含浏览器控制）执行**——优先用直连 HTTP REST（更干净、可缓存）；浏览器控制可作受限时的取数后备。某些 API 若需 key，仅经 `secrets/`，只读、不写仓库、不回显。

---

## 提示词正文（整段交给 Codex）

你是本项目的执行方（Codex），遵循既有执行与停机规范。本次任务是执行**已批准**的计划
`docs/dev/plans/050-真实学术API连接器-计划.md`（状态 approved，修订轮次 1）——构建 **真实学术 API 连接器**（第五个业务模块，**首个联网模块**）。

【唯一真源】先读这些文件，以它们为准，不要凭会话臆测：
- `docs/dev/plans/050-真实学术API连接器-计划.md`（**逐条照做**，尤其 §2 范围、§4 调研结论、§6 任务、§8 验收、§10 决策预算、§11 风险）
- `00-问题描述.md`（§证据链字段、§落地「对接真实学术 API」、§out-of-scope「不爬墙/不付费」）、`02-评审分级.md` X3（数据源点名 + 许可/字段/频率）、`docs/dev/spec/015-成功标准校准.md`（S4）
- 上游 verified 产物（**只读消费**）：M010 `src/scholarloop/corpus/connectors.py`（接口签名）、`reports/m020/evidence/*.json`（作者/年份/DOI 的「需人工核验」字段 = 本模块解析目标）、`src/scholarloop/config.py`（备用源 key 仅经 secrets）

【本次要做（按 §6 顺序）】
0. **连接器基座 + 缓存 + 配置**（`src/scholarloop/connectors/base.py`、`cache.py`）：限速、礼貌 UA（含联系方式占位）、重试、超时；响应落 `reports/m050/cache/` 带时间戳；`import scholarloop.config`（备用源 key）。
1. **OpenAlex 连接器**（`connectors/openalex.py`，**联网**）：按标题/DOI 查询，解析 `authors/year/venue/doi/oa_status/citation_count`，每值带 `source+external_id+fetched_at+license`。真实调用≥1 次成功并缓存；离线**录制夹具**单测通过。
2. **备用源**（`crossref.py`/`semantic_scholar.py`/`arxiv.py`）：DOI/期刊/预印本补充，同样带出处、缓存（至少 Crossref DOI 可用或明确降级）。
3. **零伪造解析器**（`connectors/resolver.py`）：读 M020「需人工核验」字段 → 标题**强匹配**解析；过阈值落真实值+出处，**不过阈值保留「需人工核验」**；增强证据写 `reports/m050/enriched/*.json`（**新层，不改 M020 原件**）。
4. **X3 合规落盘**（`reports/m050/data-sources.md`）：四源**点名** + 许可（OpenAlex CC0、Crossref、S2、arXiv 条款）+ 字段 + 频率/限速。
5. **有界校验桩**（`connectors/verify.py` 或等价）：抽样断言解析值==缓存外部记录、带出处、0 伪造；未过阈值仍「需人工核验」；统计解析覆盖率。产出 `reports/m050/verification.json`。
6. **合规 / 可复现 / 复盘**：全仓无密钥；缓存离线重放一致；写 `docs/dev/retrospectives/050-真实学术API连接器-复盘.md`。

【硬红线（不得改动）】
- §8 承重：**(C1) 真实连接器可用**——OpenAlex 真实调用成功并缓存、离线夹具单测通过；**(C2) 零伪造解析**——每个解析值==缓存外部记录、带 `source+external_id+fetched_at`；**标题匹配置信不足一律保留「需人工核验」，绝不伪造**作者/年份/期刊/DOI。
- **仅开放免费 API**：OpenAlex/Crossref/Semantic Scholar/arXiv；**不**用付费/受限数据、**不**爬全文/绕墙；限速 + 礼貌 UA。
- **可复现靠缓存快照**：所有响应落缓存可离线重放；在线数据会变须明确声明，评测以缓存为准。
- **上游冻结只读**：不得改 `reports/m010|m020|m030|m040/**`、M010–M040 既有源码行为、各模块验收判据、`040 结论`、FROZEN 件、`spike/**`；M020 增强写**新层** `reports/m050/enriched/`。
- 只允许写 `src/scholarloop/connectors/**`、`tests/**`（新增 `test_m050_*.py`，**不改** `test_m010/m020/m030/m040`）、`reports/m050/**`。
- **绝不把密钥写入任何文件**；如某源需 key 仅经 `secrets/` 读取；异常对密钥脱敏。

【可自行决定（§10 预算内）】取数方式（直连 HTTP 优先，浏览器控制作后备）；标题匹配阈值与算法；备用源启用顺序；字段映射；缓存键；限速参数；`connectors/` 内文件组织与局部命名。

【必须停机上报（写 `reports/m050/` 停机报告，交总指挥，不自行扩范围）】
- 某源需付费/受限/key 超免费额度；标题匹配无法在不伪造前提下达到可用覆盖（则保留「需人工核验」并说明覆盖率）；联网被环境彻底阻断（交付代码+录制夹具+离线单测，停机上报"真实可用"判据）；需改 M010–M040 产物或任何 §8 判据；任何只能靠虚构才能填的字段。

【交付】完成后：`src/scholarloop/connectors/**`（多小文件）+ `reports/m050/data-sources.md` + 说明；`pytest tests/ -q` 通过记录；缓存快照 + `reports/m050/{enriched/,verification.json}`；写复盘 `docs/dev/retrospectives/050-真实学术API连接器-复盘.md`；把 `050` 状态推进为 `implemented`。
**不要自行宣布 verified**——交给总指挥用新鲜上下文做初查。
