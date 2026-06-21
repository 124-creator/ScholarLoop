# M050 · 数据源 / 许可 / 字段 / 频率说明（X3）

- 生成日期：2026-06-20
- 模块：050 真实学术 API 连接器
- 原则：只用开放免费学术元数据 API；不爬全文、不绕墙、不使用付费/受限数据；所有响应缓存到 `reports/m050/cache/`，离线评测以缓存快照为准。
- 礼貌 UA：`ScholarLoop-M050/0.1 (mailto:no-public-email@example.com; academic metadata connector)`（项目真实联系邮箱）。

## 1. OpenAlex（主源）

- API：`https://api.openalex.org/works`
- 本模块用途：按标题 / DOI 查询论文元数据；M050 resolver 的主解析源。
- 字段：`id`、`doi`、`title/display_name`、`authorships.author.display_name`、`publication_year`、`primary_location.source.display_name`、`open_access.oa_status`、`cited_by_count`。
- 许可 / 开放性：OpenAlex 数据 CC0；网站、API、数据快照免费可用。官方价格页说明免费层 API limit 为 100k/day、max 10/second；新开发者文档也说明 API 为 freemium，免费 key 每日有免费额度。本实现支持可选 `OPENALEX_API_KEY`，但 2026-06-20 smoke 以无 key GET 成功。
- 本模块限速：默认每源 ≥0.25s 间隔；缓存命中不联网。
- 证据文件：`reports/m050/cache/openalex/*.json`。
- 官方参考：
  - https://help.openalex.org/hc/en-us/articles/24397762024087-Pricing
  - https://developers.openalex.org/api-reference/authentication

## 2. Crossref（备用 DOI / 期刊源）

- API：`https://api.crossref.org/works/{doi}`、`https://api.crossref.org/works?query.title=...`
- 本模块用途：DOI 与 venue 补充；M050 verification 已用一个 DOI 做真实 smoke。
- 字段：`DOI`、`title`、`author`、`published/issued/created`、`container-title`、`is-referenced-by-count`。
- 许可 / 开放性：Crossref REST API 公开可访问；无需注册。官方建议 polite 访问（`mailto` 或可识别 User-Agent）、缓存响应、处理 429 并退避。Crossref 文档页内容为 CC BY 4.0；具体成员元数据/许可按记录而异。
- 官方频率：public pool 5 req/s、并发 1；polite pool 10 req/s、并发 3；429 时应降低速率。
- 本模块限速：默认每源 ≥0.35s 间隔；`CROSSREF_MAILTO` 可选从环境/只读 secrets 读取，否则使用占位邮箱。
- 证据文件：`reports/m050/cache/crossref/*.json`。
- 官方参考：https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/

## 3. Semantic Scholar Academic Graph（备用源）

- API：`https://api.semanticscholar.org/graph/v1/paper/search`、`/graph/v1/paper/DOI:{doi}`
- 本模块用途：备用标题/DOI 解析源；当前 M050 主解析未依赖 S2，以避免无 key 共享池不稳定。
- 字段：`paperId`、`title`、`authors.name`、`year`、`venue`、`externalIds.DOI`、`citationCount`、`openAccessPdf`。
- 许可 / 开放性：Semantic Scholar API 有 License Agreement；需遵守归因与 rate limits，不得规避限制。部分端点/更高限额需要 API key；key 只允许经 `SEMANTIC_SCHOLAR_API_KEY` / `S2_API_KEY` 从环境或只读 secrets 读取。
- 官方频率：带 API key 的 introductory rate limit 为 1 RPS；无 key 用户受共享匿名流量影响。本模块默认 ≥1.1s 间隔。
- 证据文件：仅在启用备用查询时写 `reports/m050/cache/semantic_scholar/*.json`。
- 官方参考：
  - https://www.semanticscholar.org/product/api
  - https://www.semanticscholar.org/product/api/license

## 4. arXiv API（预印本备用源）

- API：`https://export.arxiv.org/api/query`
- 本模块用途：预印本标题检索备用源；返回 Atom XML，本模块缓存为 JSON envelope `{ "xml": ... }`。
- 字段：Atom `entry/id/title/published/author`、arXiv extension `doi`。
- 许可 / 开放性：arXiv API 公开；需遵守 arXiv API Terms of Use，不得暗示 arXiv 背书，并应按官方建议致谢 arXiv 数据使用。
- 官方频率：arXiv manual 建议连续请求时加入 3 秒 delay；本模块默认 ≥3.1s 间隔。
- 证据文件：仅在启用备用查询时写 `reports/m050/cache/arxiv/*.json`。
- 官方参考：
  - https://info.arxiv.org/help/api/index.html
  - https://info.arxiv.org/help/api/user-manual.html

## 本轮真实调用记录

- OpenAlex：成功；`reports/m050/cache/openalex/` 中有缓存快照。
- Crossref：成功；`reports/m050/verification.json.crossref_smoke.status = ok`。
- Semantic Scholar：连接器已实现；未作为本轮主解析源调用，避免无 key 匿名池不稳定。
- arXiv：连接器已实现；未作为本轮主解析源调用，因 OpenAlex 覆盖已足够，且 arXiv 只覆盖预印本。

## 零伪造执行口径

1. `authors_year` 与 `source_or_doi` 只有在 OpenAlex 返回标题强匹配（normalized score ≥0.94 且 token Jaccard ≥0.80，或规范化标题完全相同）时才填入。
2. 每个填入字段均带 `external_provenance = {source, external_id, fetched_at, license, cache_path}`。
3. 未过阈值的卡片保留 M020 的「需人工核验」，并附 `m050_resolution_attempt`，不强填作者/年份/DOI/期刊。
4. 在线数据会变化；M050 验证以 `reports/m050/cache/` 快照为准。
