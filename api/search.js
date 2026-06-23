const DEEPSEEK_BASE_URL = process.env.DEEPSEEK_BASE_URL || "https://api.deepseek.com";
const DEEPSEEK_MODEL = process.env.DEEPSEEK_MODEL || process.env.LLM_MODEL || "deepseek-v4-flash";
const DEEPSEEK_API_KEY = process.env.DEEPSEEK_API_KEY || process.env.LLM_API_KEY || "";

function setCors(res) {
  res.setHeader("Access-Control-Allow-Origin", process.env.ALLOWED_ORIGIN || "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
  res.setHeader("Cache-Control", "no-store");
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function cleanText(value, limit = 800) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
}

function isCarbonTopic(query) {
  return /碳|carbon|emission|emissions|ets/i.test(query || "");
}

function isMachineLearningTopic(query) {
  return /机器学习|machine learning|\bml\b|统计学习|监督学习|无监督学习|强化学习/i.test(query || "");
}

function fallbackQueries(query) {
  if (isCarbonTopic(query)) {
    return [
      "carbon price forecasting",
      "carbon market price prediction machine learning",
      "emissions trading scheme carbon price volatility",
      "carbon pricing policy impact carbon market",
    ];
  }
  if (isMachineLearningTopic(query)) {
    return [
      "machine learning survey",
      "supervised learning evaluation",
      "machine learning model selection",
      "machine learning interpretability",
      "机器学习",
    ];
  }
  return [query, `${query} survey`, `${query} review`, `${query} machine learning`, `${query} research challenges`].filter(Boolean);
}

function topicTokens(value) {
  const stop = new Set(["the", "and", "for", "with", "from", "into", "using", "based", "about", "under", "over", "large", "small", "model", "models", "language"]);
  return String(value || "").toLowerCase().match(/[a-z][a-z0-9-]{2,}/g)?.filter((t) => !stop.has(t)) || [];
}

function abstractFromInvertedIndex(index, limit = 900) {
  if (!index || typeof index !== "object") return "";
  let max = -1;
  for (const positions of Object.values(index)) {
    if (Array.isArray(positions)) {
      for (const pos of positions) max = Math.max(max, Number(pos));
    }
  }
  if (max < 0) return "";
  const words = new Array(max + 1).fill("");
  for (const [word, positions] of Object.entries(index)) {
    if (!Array.isArray(positions)) continue;
    for (const pos of positions) {
      const i = Number(pos);
      if (Number.isInteger(i) && i >= 0 && i < words.length) words[i] = word;
    }
  }
  return words.filter(Boolean).join(" ").slice(0, limit);
}

function openalexUrl(work) {
  return work?.primary_location?.landing_page_url || work?.doi || work?.id || "";
}

function authors(work) {
  return asArray(work?.authorships).map((a) => a?.author?.display_name).filter(Boolean).slice(0, 6);
}

function venue(work) {
  return work?.primary_location?.source?.display_name || work?.host_venue?.display_name || "";
}

function relevanceScore(query, work, abstract) {
  const title = cleanText(work?.title || work?.display_name || "", 500).toLowerCase();
  const text = `${title} ${String(abstract || "").toLowerCase()}`;
  const queryText = String(query || "").toLowerCase();
  const tokens = topicTokens(queryText);
  let score = Math.min(Number(work?.cited_by_count || 0), 1000) / 1000;
  if (abstract) score += 3;
  if (queryText && title.includes(queryText)) score += 5;
  else if (queryText && text.includes(queryText)) score += 2;
  if (tokens.length) {
    const titleHits = tokens.filter((t) => title.includes(t)).length;
    const textHits = tokens.filter((t) => text.includes(t)).length;
    score += (titleHits / tokens.length) * 5;
    score += (textHits / tokens.length) * 3;
    if (textHits === 0) score -= 3;
  }
  if (/compression/.test(queryText) && !/compress|compression/.test(text)) score -= 3;
  if (isCarbonTopic(queryText)) {
    if (/carbon/.test(text)) score += 3;
    if (/(price|pricing|market|trading|emission|emissions|ets)/.test(text)) score += 2;
    if (/(forecast|forecasting|prediction|predict|volatility|policy|scheme)/.test(text)) score += 1.5;
    if (!/carbon/.test(text)) score -= 6;
  }
  return score;
}

async function fetchOpenAlex(searchQuery, maxResults = 25) {
  const url = new URL("https://api.openalex.org/works");
  url.searchParams.set("search", searchQuery);
  url.searchParams.set("per-page", String(maxResults));
  url.searchParams.set("sort", "relevance_score:desc");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: { "user-agent": "ScholarLoop realtime demo (public portfolio)" },
    });
    if (!response.ok) throw new Error(`OpenAlex ${response.status}`);
    const data = await response.json();
    return asArray(data.results);
  } finally {
    clearTimeout(timer);
  }
}

async function paperRows(query, queries, limit = 8) {
  const seen = new Set();
  const candidates = [];
  const used = [];
  for (const searchQuery of queries.slice(0, 4)) {
    const works = await fetchOpenAlex(searchQuery, Math.max(limit * 3, 25));
    used.push(searchQuery);
    works.forEach((work, localRank) => {
      const title = cleanText(work?.title || work?.display_name || "Untitled", 500);
      const key = work?.doi || work?.id || title.toLowerCase();
      if (!key || seen.has(key)) return;
      seen.add(key);
      const abstract = abstractFromInvertedIndex(work?.abstract_inverted_index);
      const score = relevanceScore(searchQuery, work, abstract) - (localRank + 1) * 0.01;
      candidates.push({ work, title, abstract, score, searchQuery, localRank: localRank + 1 });
    });
  }
  candidates.sort((a, b) => b.score - a.score || Number(b.work?.cited_by_count || 0) - Number(a.work?.cited_by_count || 0));
  const rows = candidates.slice(0, limit).map((item, index) => {
    const work = item.work;
    const url = openalexUrl(work);
    return {
      rank: index + 1,
      corpusid: String(work?.id || "").split("/").pop() || `openalex-${index + 1}`,
      external_id: work?.id || "",
      score: Math.max(0.1, item.score / 14),
      title: item.title,
      abstract_preview: item.abstract.slice(0, 360),
      abstract_status: item.abstract ? "openalex_abstract" : "missing_in_openalex",
      reason: `OpenAlex live search; query='${item.searchQuery}'; local_rank=${item.localRank}; topic_score=${item.score.toFixed(3)}; abstract=${item.abstract ? "yes" : "no"}; citations=${work?.cited_by_count || 0}; year=${work?.publication_year || ""}`,
      authors: authors(work),
      year: work?.publication_year || null,
      venue: venue(work),
      doi: work?.doi || null,
      url,
      source: "openalex",
      citation_count: work?.cited_by_count || 0,
      authors_year: { status: "openalex_metadata", value: `${authors(work).slice(0, 3).join(", ")}${work?.publication_year ? ` (${work.publication_year})` : ""}` },
      source_or_doi: { status: work?.doi || url ? "openalex_metadata" : "manual_review", value: work?.doi || url },
    };
  });
  return { rows, used };
}

function seedWebResearch(query, queries) {
  const results = [];
  if (isCarbonTopic(query)) {
    results.push(
      { title: "World Bank State and Trends of Carbon Pricing", url: "https://carbonpricingdashboard.worldbank.org/", snippet: "Authoritative policy and market dashboard for carbon pricing mechanisms." },
      { title: "ICAP ETS Allowance Price Explorer", url: "https://icapcarbonaction.com/en/ets-prices", snippet: "Tracks emissions trading system allowance prices and policy context." },
      { title: "Climate Focus carbon market review", url: "https://climatefocus.com/", snippet: "Public market commentary that should be treated as non-verified web context." },
    );
  } else if (isMachineLearningTopic(query)) {
    results.push(
      { title: "OpenAlex 机器学习论文元数据", url: "https://openalex.org/", snippet: `实时发现机器学习论文：${queries.slice(0, 3).join(" | ")}` },
      { title: "Papers with Code: Machine Learning", url: "https://paperswithcode.com/methods", snippet: "观察机器学习方法、任务、数据集和基准榜单；需回到论文核验。" },
      { title: "scikit-learn User Guide", url: "https://scikit-learn.org/stable/user_guide.html", snippet: "核对经典机器学习流程、模型选择、交叉验证和特征处理实践。" },
    );
  } else {
    results.push({ title: "OpenAlex 实时论文元数据", url: "https://openalex.org/", snippet: `实时学术元数据检索：${queries.slice(0, 3).join(" | ")}` });
  }
  return { search_provider: "serverless_seed_sources", queries, results, page_excerpts: [] };
}

function fallbackSummary(query, rows, webResearch) {
  const titles = rows.slice(0, 6).map((r) => r.title).filter(Boolean);
  const ml = isMachineLearningTopic(query);
  const carbon = isCarbonTopic(query);
  const topic = cleanText(query, 80) || "当前主题";
  return {
    prior_issues: ml ? [
      { issue: "机器学习范围很大，必须先限定任务类型：分类、回归、聚类、推荐、预测或异常检测。", evidence: titles.slice(0, 2), verification: "由 OpenAlex 实时元数据归纳；需打开全文核验。" },
      { issue: "常见问题不是模型不够复杂，而是数据泄露、特征工程不稳、评价指标选错和样本外泛化差。", evidence: titles.slice(1, 3), verification: "候选问题；需结合具体数据和实验设计验证。" },
      { issue: "网络讨论容易过度强调模型名，忽视数据质量、可解释性、可复现性和部署成本。", evidence: webResearch.results.slice(0, 3).map((r) => r.title), verification: "网页来源只作为背景线索。" },
    ] : [
      { issue: carbon ? "碳价序列通常存在非线性、非平稳和政策冲击，直接套模型容易过拟合。" : "先明确研究边界，否则容易把综述、方法比较和实验复现混在一起。", evidence: titles.slice(0, 2), verification: "由 OpenAlex 实时元数据归纳；需打开全文核验。" },
      { issue: "数据来源、时间范围、基线方法和评价指标会显著影响结论。", evidence: titles.slice(1, 3), verification: "候选问题；需人工核验。" },
      { issue: "不能只优化单一指标，需要补充鲁棒性、误差分析和失败样例。", evidence: titles.slice(2, 4), verification: "方法层面的风险提醒。" },
    ],
    reading_route: ml ? [
      { stage: "第 1 轮：先读综述和经典方法", goal: "建立监督学习、无监督学习、集成学习、模型选择和泛化误差框架。", papers: titles.slice(0, 3) },
      { stage: "第 2 轮：按任务拆分阅读", goal: "选择分类/回归/时序预测/异常检测中的一个具体任务，比较数据集、特征、模型和指标。", papers: titles.slice(3, 6) },
      { stage: "第 3 轮：转成作品集实验", goal: "做可复现实验：数据清洗、特征工程、切分、基线、调参、解释和误差分析。", papers: titles.slice(0, 6) },
    ] : [
      { stage: "第 1 轮：快速定方向", goal: "先读最相关综述或高被引论文，统一术语和问题范围。", papers: titles.slice(0, 3) },
      { stage: "第 2 轮：做文献矩阵", goal: "按数据、方法、指标、局限和可复现性建立对比表。", papers: titles.slice(3, 6) },
      { stage: "第 3 轮：形成可执行选题", goal: "选择一个可复现、可展示、能做实验或 Demo 的研究空白。", papers: titles.slice(0, 6) },
    ],
    research_plan: ml ? [
      { step: 1, title: "收敛主题", actions: ["把机器学习缩小到一个任务", "确定数据集和业务目标", "选择主指标和辅助指标"], output: "任务定义和检索词表" },
      { step: 2, title: "整理论文和方法矩阵", actions: ["按传统模型、集成模型、深度模型分组", "记录数据集、特征、指标和局限", "标注是否可复现"], output: "机器学习文献矩阵" },
      { step: 3, title: "构建工程基线", actions: ["清洗数据", "完成特征工程", "跑 Logistic Regression、Random Forest、XGBoost/LightGBM 等基线"], output: "可复现实验报告" },
      { step: 4, title: "补强作品集展示", actions: ["加入 SHAP/特征重要性解释", "做错误样本分析和消融实验", "封装成 Demo 或 Notebook 报告"], output: "面试可讲的机器学习项目闭环" },
    ] : [
      { step: 1, title: "Clarify the task", actions: ["Define topic scope", "List variables/data sources", "Choose evaluation metrics"], output: "Problem definition and keyword table" },
      { step: 2, title: "Read and compare papers", actions: ["Summarize methods", "Record datasets and limits", "Mark unverifiable claims"], output: "Literature matrix" },
      { step: 3, title: "Build a baseline", actions: ["Prepare data", "Run simple baselines", "Track errors"], output: "Reproducible baseline report" },
      { step: 4, title: "Improve and present", actions: ["Add one clear improvement", "Run ablation", "Package the evidence chain"], output: "Portfolio-ready demo" },
    ],
    network_research_experience: [
      { title: "发现信息和承重证据分离", detail: "OpenAlex/Web snippets are useful for discovery, but load-bearing claims need full-text verification.", evidence: webResearch.results.slice(0, 3).map((r) => r.title) },
      { title: "中文主题需要英文检索词扩展", detail: "短中文主题通常需要扩展为英文论文检索词，才能召回更完整的国际论文。", evidence: [] },
    ],
    web_reputation: [
      { view: ml ? "机器学习在网络上常被讨论为通用能力，但真正落地时更看重数据质量、评估设计、可解释性和部署成本。" : "公开网页资料适合作为背景线索，不适合直接当作最终证据。", evidence: webResearch.results.slice(0, 3).map((r) => r.title), verification: "引用前打开来源并记录访问日期。" },
    ],
    caution_points: ["不要在静态网页中暴露 DeepSeek 或其他 LLM API 私钥。", "实时元数据会随时间变化，建议记录检索日期和查询词。", "承重结论必须打开论文全文或官方数据源核验。"],
    deepseek_cn_summary: ml ? {
      title: "DeepSeek 中文调研摘要：机器学习",
      summary: "机器学习主题过宽，建议先收敛到分类、回归、时序预测或异常检测等具体任务。作品集展示应突出数据清洗、特征工程、训练验证切分、基线模型、调参、解释和误差分析闭环。",
      findings: ["优先选择一个小任务，避免主题过大。", "重点控制数据泄露、交叉验证、样本外表现和可解释性。", "面试时讲清楚数据来源、处理流程、指标选择和失败样例。"],
      evidence: webResearch.results.slice(0, 3).map((r) => r.title),
    } : {
      title: `DeepSeek 中文调研摘要：${topic}`,
      summary: `围绕“${topic}”的调研应先完成论文发现和问题拆解，再把候选论文按方法、数据、指标和局限做矩阵化比较，最后选择一个可复现的小切口。`,
      findings: ["先读综述和高相关论文，建立术语表。", "用文献矩阵记录数据、方法、指标、局限和可复现性。", "选择一个小改进做实验，避免选题过大。"],
      evidence: webResearch.results.slice(0, 3).map((r) => r.title),
    },
  };
}

function valueList(value) {
  if (Array.isArray(value)) return value.filter((v) => v !== null && v !== undefined && v !== "");
  if (value === null || value === undefined || value === "") return [];
  if (typeof value === "object") return Object.values(value).flatMap((v) => Array.isArray(v) ? v : [v]).filter((v) => v !== null && v !== undefined && v !== "");
  return [value];
}

function evidenceItems(value) {
  if (Array.isArray(value)) return value.flatMap(evidenceItems).filter((v) => v !== null && v !== undefined && v !== "");
  if (value === null || value === undefined || value === "") return [];
  if (typeof value === "object") return Object.values(value).flatMap(evidenceItems).filter((v) => v !== null && v !== undefined && v !== "");
  return [value];
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function evidenceList(value) {
  return evidenceItems(value).map((item) => {
    if (typeof item === "string" || typeof item === "number") return cleanText(item, 500);
    if (item && typeof item === "object") {
      return cleanText(item.title || item.paper || item.name || item.url || item.snippet || JSON.stringify(item), 500);
    }
    return cleanText(item, 500);
  }).filter(Boolean);
}

function normalizeCardList(items, normalizer, fallbackItems = []) {
  const source = valueList(items).length ? valueList(items) : valueList(fallbackItems);
  return source.map(normalizer).filter((item) => Object.values(item).some((value) => Array.isArray(value) ? value.length : Boolean(value)));
}

function sanitizeSummary(summary, fallback) {
  const src = objectValue(summary);
  const fb = objectValue(fallback);
  const briefSrc = objectValue(src.deepseek_cn_summary || fb.deepseek_cn_summary);
  return {
    prior_issues: normalizeCardList(src.prior_issues, (item) => {
      const obj = objectValue(item);
      return {
        issue: cleanText(obj.issue || obj.title || obj.view || item, 700),
        evidence: evidenceList(obj.evidence || obj.papers || obj.sources),
        verification: cleanText(obj.verification || "manual verification required", 400),
      };
    }, fb.prior_issues),
    reading_route: normalizeCardList(src.reading_route, (item) => {
      const obj = objectValue(item);
      return {
        stage: cleanText(obj.stage || obj.title || item, 500),
        goal: cleanText(obj.goal || obj.summary || obj.detail, 800),
        papers: evidenceList(obj.papers || obj.evidence || obj.sources),
      };
    }, fb.reading_route),
    research_plan: normalizeCardList(src.research_plan, (item) => {
      const obj = objectValue(item);
      return {
        step: obj.step || "",
        title: cleanText(obj.title || obj.stage || item, 500),
        actions: evidenceList(obj.actions || obj.action || obj.evidence),
        output: cleanText(obj.output || obj.deliverable || obj.result, 500),
      };
    }, fb.research_plan),
    network_research_experience: normalizeCardList(src.network_research_experience, (item) => {
      const obj = objectValue(item);
      return {
        title: cleanText(obj.title || obj.view || item, 500),
        detail: cleanText(obj.detail || obj.summary || obj.verification, 900),
        evidence: evidenceList(obj.evidence || obj.sources),
      };
    }, fb.network_research_experience),
    web_reputation: normalizeCardList(src.web_reputation, (item) => {
      const obj = objectValue(item);
      return {
        view: cleanText(obj.view || obj.title || item, 800),
        evidence: evidenceList(obj.evidence || obj.sources),
        verification: cleanText(obj.verification || "open sources manually before citing", 400),
      };
    }, fb.web_reputation),
    caution_points: evidenceList(src.caution_points || fb.caution_points),
    deepseek_cn_summary: {
      title: cleanText(briefSrc.title || "DeepSeek research summary", 200),
      summary: cleanText(briefSrc.summary || "", 1200),
      findings: evidenceList(briefSrc.findings),
      evidence: evidenceList(briefSrc.evidence),
    },
  };
}

function parseJsonContent(text) {
  const raw = cleanText(text, 8000).replace(/^```json\s*/i, "").replace(/```$/i, "");
  return JSON.parse(raw);
}

async function deepseekSummary(query, rows, webResearch) {
  if (!DEEPSEEK_API_KEY || !rows.length) return { summary: fallbackSummary(query, rows, webResearch), meta: { calls: 0, tokens: 0, cached: false } };
  const paperPayload = rows.slice(0, 8).map((r) => ({ title: r.title, year: r.year, venue: r.venue, citations: r.citation_count, abstract_preview: r.abstract_preview }));
  const webPayload = (webResearch.results || []).slice(0, 6).map((r) => ({ title: r.title, url: r.url, snippet: r.snippet }));
  const response = await fetch(`${DEEPSEEK_BASE_URL.replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${DEEPSEEK_API_KEY}` },
    body: JSON.stringify({
      model: DEEPSEEK_MODEL,
      temperature: 0.2,
      max_tokens: 2200,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: "你是谨慎的中文科研调研助手。只返回 JSON。只能使用提供的 OpenAlex 论文和网页片段，不得编造论文、URL、指标、价格或网络观点。" },
        { role: "user", content: `主题: ${query}\nOpenAlex 候选论文: ${JSON.stringify(paperPayload)}\n网页/背景片段: ${JSON.stringify(webPayload)}\n请用中文返回 JSON，键包括：prior_issues:[{issue,evidence,verification}], reading_route:[{stage,goal,papers}], research_plan:[{step,title,actions,output}], network_research_experience:[{title,detail,evidence}], web_reputation:[{view,evidence,verification}], caution_points:[string], deepseek_cn_summary:{title,summary,findings,evidence}.` },
      ],
    }),
  });
  if (!response.ok) throw new Error(`DeepSeek ${response.status}`);
  const data = await response.json();
  const content = data?.choices?.[0]?.message?.content || "{}";
  return { summary: parseJsonContent(content), meta: { calls: 1, tokens: data?.usage?.total_tokens || 0, cached: false } };
}

async function buildPayload(query) {
  const started = Date.now();
  const queries = fallbackQueries(query).slice(0, 6);
  const { rows, used } = await paperRows(query, queries, 8);
  const webResearch = seedWebResearch(query, used.length ? used : queries);
  const fallback = fallbackSummary(query, rows, webResearch);
  const { summary: rawSummary, meta } = await deepseekSummary(query, rows, webResearch).catch(() => ({ summary: fallback, meta: { calls: 0, tokens: 0, fallback: true } }));
  const summary = sanitizeSummary(rawSummary, fallback);
  return {
    schema_version: "m130.search_response.v1",
    label: DEEPSEEK_API_KEY ? "后端实时：OpenAlex + DeepSeek" : "后端实时：OpenAlex only",
    verified_load_bearing: false,
    deterministic: false,
    source_contract: "实时结果只用于调研发现，不作为承重证据；失败时显示明确回退。",
    status: rows.length ? "ok" : "empty",
    enabled: true,
    reason: DEEPSEEK_API_KEY ? "serverless 后端已使用 OpenAlex 元数据和 DeepSeek 中文归纳。" : "serverless 后端仅使用 OpenAlex 元数据；尚未配置 DeepSeek key。",
    fallback_reason: null,
    query,
    decomposition: { subqueries: queries, criteria: ["topic relevance", "metadata availability", "manual verification required"] },
    results: rows,
    cost: { llm_calls: meta.calls || 0, tokens: meta.tokens || 0, latency_s: (Date.now() - started) / 1000 },
    notice: "实时主题调研只是发现草稿；论文和网页结论需人工核验。",
    raw_mode: "serverless_topic_research",
    source: { corpus: "OpenAlex live metadata", ranker: "serverless_topic_research" },
    topic_research: {
      intent: `围绕“${query}”进行后端实时主题调研。`,
      searched_queries: used,
      recommended_papers: rows,
      prior_issues: summary.prior_issues || [],
      reading_route: summary.reading_route || [],
      research_plan: summary.research_plan || [],
      network_research_experience: summary.network_research_experience || [],
      web_reputation: summary.web_reputation || [],
      caution_points: summary.caution_points || [],
      deepseek_cn_summary: summary.deepseek_cn_summary || fallbackSummary(query, rows, webResearch).deepseek_cn_summary,
      web_research: webResearch,
      deepseek_api_note: {
        role: DEEPSEEK_API_KEY ? "Summarizes supplied paper/web evidence on the server side" : "Not configured on this deployment",
        base_url: DEEPSEEK_BASE_URL,
        limitation: "DeepSeek is called only from the serverless backend; keys are never exposed to the browser.",
      },
      limitations: ["Live metadata changes over time.", "This is not verified load-bearing evidence.", "Open full papers before citing or claiming."],
    },
  };
}

module.exports = async function handler(req, res) {
  setCors(res);
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "GET") return res.status(405).json({ status: "error", reason: "GET only" });
  const query = cleanText(req.query?.q || req.query?.query || "", 200);
  if (!query) return res.status(400).json({ status: "empty", reason: "Missing q parameter", results: [] });
  try {
    const payload = await buildPayload(query);
    return res.status(200).json(payload);
  } catch (error) {
    return res.status(200).json({
      schema_version: "m130.search_response.v1",
      label: "Serverless realtime unavailable",
      status: "unavailable",
      enabled: true,
      reason: `${error && error.name ? error.name : "Error"}: ${cleanText(error && error.message, 200)}`,
      query,
      decomposition: { subqueries: [query] },
      results: [],
      cost: { llm_calls: 0, tokens: 0, latency_s: 0 },
      raw_mode: "serverless_unavailable",
      topic_research: { recommended_papers: [], prior_issues: [], reading_route: [], research_plan: [], network_research_experience: [], web_research: { results: [] } },
    });
  }
};
