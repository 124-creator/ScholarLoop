const fs = require("fs");
const path = require("path");

const DEEPSEEK_BASE_URL = process.env.DEEPSEEK_BASE_URL || "https://api.deepseek.com";
const DEEPSEEK_MODEL = process.env.DEEPSEEK_MODEL || process.env.LLM_MODEL || "deepseek-v4-flash";
const DEEPSEEK_API_KEY = process.env.DEEPSEEK_API_KEY || process.env.LLM_API_KEY || "";
const OPENALEX_API_KEY = process.env.OPENALEX_API_KEY || "";
const OPENALEX_CONTACT_EMAIL = process.env.OPENALEX_CONTACT_EMAIL || process.env.CONTACT_EMAIL || "";
const OPENALEX_REQUESTS_PER_SEARCH = Math.max(1, Math.min(4, Number(process.env.OPENALEX_REQUESTS_PER_SEARCH || 3)));
const CACHE_TTL_MS = Math.max(60_000, Number(process.env.SCHOLARLOOP_CACHE_TTL_MS || 30 * 60 * 1000));
const CACHE_VERSION = "m141_planned_openalex_local";
const LOCAL_INDEX_PATH = process.env.LITSEARCH_INDEX_PATH || path.join(__dirname, "..", "data", "litsearch_seed_index.json");
const openAlexCache = new Map();
const payloadCache = new Map();
let localIndexCache = null;

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
  return /\u78b3|\u78b3\u4ef7|\u78b3\u4ef7\u683c|\u78b3\u5e02\u573a|carbon|emission|emissions|ets/i.test(query || "");
}

function isMachineLearningTopic(query) {
  return /\u673a\u5668\u5b66\u4e60|machine learning|\bml\b|\u7edf\u8ba1\u5b66\u4e60|\u76d1\u7763\u5b66\u4e60|\u65e0\u76d1\u7763\u5b66\u4e60|\u5f3a\u5316\u5b66\u4e60/i.test(query || "");
}

function isRagTopic(query) {
  return /\brag\b|retrieval[-\s]?augmented generation|\u68c0\u7d22\u589e\u5f3a\u751f\u6210|\u68c0\u7d22\u589e\u5f3a|\u5fe0\u5b9e\u5ea6|faithfulness|context precision|answer relevancy|RAGAS|ARES/i.test(query || "");
}

function isCompressionTopic(query) {
  return /compression|\u538b\u7f29|distillation|\u77e5\u8bc6\u84b8\u998f|pruning|\u526a\u679d|quantization|\u91cf\u5316|efficient\s+(llm|language model)/i.test(query || "");
}

function uniqueStrings(items, limit = 12) {
  const seen = new Set();
  const out = [];
  asArray(items).forEach((item) => {
    const text = cleanText(item, 160);
    const key = text.toLowerCase();
    if (!text || seen.has(key)) return;
    seen.add(key);
    out.push(text);
  });
  return out.slice(0, limit);
}

function staticQueryPlan(query) {
  const topic = cleanText(query, 120);
  if (isCarbonTopic(topic)) {
    return {
      planner: "static_topic_rules",
      intent_cn: `围绕“${topic}”检索碳价格/碳市场预测与政策影响论文。`,
      openalex_queries: [
        "carbon price forecasting",
        "carbon market price prediction machine learning",
        "emissions trading scheme carbon price volatility",
        "carbon pricing policy impact carbon market",
      ],
      local_queries: ["carbon price", "carbon market", "emissions trading", "price forecasting"],
      must_terms: ["carbon", "price", "pricing", "market", "emissions trading", "forecasting", "volatility"],
      reject_if_missing_any: ["carbon"],
      exclude_terms: [],
      strict_topic_gate: true,
    };
  }
  if (isRagTopic(topic)) {
    return {
      planner: "static_topic_rules",
      intent_cn: `围绕“${topic}”检索 RAG / 检索增强生成评测论文。`,
      openalex_queries: [
        "retrieval augmented generation evaluation",
        "RAG evaluation benchmark",
        "RAGAs automated evaluation retrieval augmented generation",
        "ARES automated evaluation framework retrieval augmented generation",
        "faithfulness context precision answer relevancy RAG evaluation",
      ],
      local_queries: ["retrieval augmented generation", "RAG evaluation", "question answering retrieval", "faithfulness benchmark"],
      must_terms: ["retrieval augmented generation", "rag", "faithfulness", "context precision", "answer relevancy", "benchmark", "question answering", "retriever"],
      reject_if_missing_any: ["retrieval augmented generation", "rag", "question answering", "retriever"],
      exclude_terms: ["soil", "orchard", "cadmium", "lead", "zinc", "philosophy"],
      strict_topic_gate: true,
    };
  }
  if (isCompressionTopic(topic)) {
    return {
      planner: "static_topic_rules",
      intent_cn: `围绕“${topic}”检索模型压缩、蒸馏、剪枝、量化与高效 LLM 论文。`,
      openalex_queries: [
        "large language model compression survey",
        "knowledge distillation language model compression",
        "LLM pruning quantization evaluation",
        "efficient transformer model compression benchmark",
      ],
      local_queries: ["language model compression", "knowledge distillation", "model pruning", "quantization"],
      must_terms: ["compression", "distillation", "pruning", "quantization", "efficient", "language model"],
      reject_if_missing_any: ["compression", "distillation", "pruning", "quantization"],
      exclude_terms: [],
      strict_topic_gate: true,
    };
  }
  if (isMachineLearningTopic(topic)) {
    return {
      planner: "static_topic_rules",
      intent_cn: `围绕“${topic}”检索机器学习综述、评估、模型选择与可解释性论文。`,
      openalex_queries: [
        "machine learning survey",
        "supervised learning evaluation",
        "machine learning model selection",
        "machine learning interpretability",
      ],
      local_queries: ["machine learning", "model selection", "supervised learning", "interpretability"],
      must_terms: ["machine learning", "supervised", "model selection", "interpretability", "classification", "regression"],
      reject_if_missing_any: [],
      exclude_terms: [],
      strict_topic_gate: false,
    };
  }
  return {
    planner: "static_generic",
    intent_cn: `围绕“${topic}”进行主题检索，优先扩展为英文论文检索词。`,
    openalex_queries: [topic, `${topic} survey`, `${topic} review`, `${topic} benchmark`, `${topic} research challenges`].filter(Boolean),
    local_queries: [topic],
    must_terms: topicTokens(topic),
    reject_if_missing_any: [],
    exclude_terms: [],
    strict_topic_gate: false,
  };
}

function fallbackQueries(query) {
  return staticQueryPlan(query).openalex_queries;
}

function cacheGet(cache, key) {
  const hit = cache.get(key);
  if (!hit) return null;
  if (hit.expiresAt <= Date.now()) {
    cache.delete(key);
    return null;
  }
  return hit.value;
}

function cacheSet(cache, key, value, ttlMs = CACHE_TTL_MS) {
  if (cache.size > 200) {
    const firstKey = cache.keys().next().value;
    if (firstKey) cache.delete(firstKey);
  }
  cache.set(key, { value, expiresAt: Date.now() + ttlMs });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function topicTokens(value) {
  const stop = new Set(["the", "and", "for", "with", "from", "into", "using", "based", "about", "under", "over", "large", "small", "model", "models", "language"]);
  return String(value || "").toLowerCase().match(/[a-z][a-z0-9-]{2,}/g)?.filter((t) => !stop.has(t)) || [];
}

function queryPlanTerms(queryPlan, query = "") {
  const terms = [
    ...topicTokens(query),
    ...topicTokens(asArray(queryPlan?.openalex_queries).join(" ")),
    ...topicTokens(asArray(queryPlan?.local_queries).join(" ")),
    ...topicTokens(asArray(queryPlan?.must_terms).join(" ")),
  ];
  return uniqueStrings(terms, 40);
}

function textHasAny(text, terms) {
  const haystack = String(text || "").toLowerCase();
  return asArray(terms).some((term) => {
    const needle = String(term || "").toLowerCase().trim();
    if (!needle) return false;
    if (/^[a-z0-9-]{2,4}$/.test(needle)) {
      return new RegExp(`\\b${needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(haystack);
    }
    return haystack.includes(needle);
  });
}

function passesTopicGate(queryPlan, text) {
  if (!queryPlan?.strict_topic_gate) return true;
  if (textHasAny(text, queryPlan.exclude_terms)) return false;
  const required = asArray(queryPlan.reject_if_missing_any);
  if (required.length && !textHasAny(text, required)) return false;
  return true;
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

function relevanceScore(query, work, abstract, queryPlan = null) {
  const title = cleanText(work?.title || work?.display_name || "", 500).toLowerCase();
  const text = `${title} ${String(abstract || "").toLowerCase()}`;
  const queryText = String(query || "").toLowerCase();
  const tokens = uniqueStrings([...topicTokens(queryText), ...queryPlanTerms(queryPlan)], 50);
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
  if (queryPlan?.strict_topic_gate && !passesTopicGate(queryPlan, text)) score -= 20;
  if (isRagTopic(`${queryText} ${asArray(queryPlan?.must_terms).join(" ")}`)) {
    if (/(retrieval[-\s]?augmented generation|\brag\b|faithfulness|context precision|answer relevancy|ragas|benchmark|retriever|question answering)/i.test(text)) score += 6;
    if (/(soil|orchard|cadmium|lead|zinc|philosophy)/i.test(text)) score -= 12;
  }
  if (isCarbonTopic(queryText)) {
    if (/carbon/.test(text)) score += 3;
    if (/(price|pricing|market|trading|emission|emissions|ets)/.test(text)) score += 2;
    if (/(forecast|forecasting|prediction|predict|volatility|policy|scheme)/.test(text)) score += 1.5;
    if (!/carbon/.test(text)) score -= 6;
  }
  return score;
}

async function fetchOpenAlex(searchQuery, maxResults = 16) {
  const cacheKey = `${searchQuery}::${maxResults}::${OPENALEX_API_KEY ? "key" : "anon"}`;
  const cached = cacheGet(openAlexCache, cacheKey);
  if (cached) return cached;

  const url = new URL("https://api.openalex.org/works");
  url.searchParams.set("search", searchQuery);
  url.searchParams.set("per-page", String(Math.max(5, Math.min(25, maxResults))));
  url.searchParams.set("sort", "relevance_score:desc");
  url.searchParams.set("select", "id,doi,title,display_name,publication_year,cited_by_count,authorships,primary_location,abstract_inverted_index");
  if (OPENALEX_API_KEY) url.searchParams.set("api_key", OPENALEX_API_KEY);
  if (OPENALEX_CONTACT_EMAIL) url.searchParams.set("mailto", OPENALEX_CONTACT_EMAIL);

  const userAgent = OPENALEX_CONTACT_EMAIL
    ? `ScholarLoop realtime demo (${OPENALEX_CONTACT_EMAIL})`
    : "ScholarLoop realtime demo (public portfolio)";

  for (let attempt = 0; attempt < 2; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(url, { signal: controller.signal, headers: { "user-agent": userAgent } });
      if (response.status === 429) {
        const retryAfter = Number(response.headers.get("retry-after") || 0);
        const error = new Error("OpenAlex 429");
        error.status = 429;
        error.retryAfter = retryAfter;
        error.rateLimitRemaining = response.headers.get("x-ratelimit-remaining") || "";
        error.rateLimitLimit = response.headers.get("x-ratelimit-limit") || "";
        if (attempt === 0 && retryAfter > 0 && retryAfter <= 2) {
          clearTimeout(timer);
          await sleep(retryAfter * 1000);
          continue;
        }
        throw error;
      }
      if (!response.ok) {
        const error = new Error(`OpenAlex ${response.status}`);
        error.status = response.status;
        throw error;
      }
      const data = await response.json();
      const works = asArray(data.results);
      cacheSet(openAlexCache, cacheKey, works);
      return works;
    } finally {
      clearTimeout(timer);
    }
  }
  return [];
}
async function paperRows(query, queries, limit = 8, queryPlan = null) {
  const seen = new Set();
  const candidates = [];
  const used = [];
  const errors = [];
  for (const searchQuery of queries.slice(0, OPENALEX_REQUESTS_PER_SEARCH)) {
    try {
      const works = await fetchOpenAlex(searchQuery, Math.max(limit * 2, 16));
      used.push(searchQuery);
      works.forEach((work, localRank) => {
        const title = cleanText(work?.title || work?.display_name || "Untitled", 500);
        const key = work?.doi || work?.id || title.toLowerCase();
        if (!key || seen.has(key)) return;
        seen.add(key);
        const abstract = abstractFromInvertedIndex(work?.abstract_inverted_index);
        const combinedText = `${title}\n${abstract}`;
        if (!passesTopicGate(queryPlan, combinedText)) return;
        const score = relevanceScore(searchQuery, work, abstract, queryPlan) - (localRank + 1) * 0.01;
        if (queryPlan?.strict_topic_gate && score < 1) return;
        candidates.push({ work, title, abstract, score, searchQuery, localRank: localRank + 1 });
      });
    } catch (error) {
      errors.push({ query: searchQuery, status: error?.status || error?.name || "error", message: cleanText(error?.message || error, 160) });
      if (error?.status === 429) break;
    }
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
  return { rows, used, errors };
}

function loadLocalIndex() {
  if (localIndexCache) return localIndexCache;
  const empty = { available: false, source_total: 0, records: [], reason: "local index not found" };
  try {
    if (!fs.existsSync(LOCAL_INDEX_PATH)) {
      localIndexCache = empty;
      return localIndexCache;
    }
    const data = JSON.parse(fs.readFileSync(LOCAL_INDEX_PATH, "utf8"));
    localIndexCache = {
      available: true,
      source_total: Number(data.source_total || 64183),
      note: cleanText(data.note || "Lightweight LitSearch local supplement.", 500),
      records: asArray(data.records),
    };
    return localIndexCache;
  } catch (error) {
    localIndexCache = { ...empty, reason: cleanText(error.message || error, 200) };
    return localIndexCache;
  }
}

function localRecordScore(record, query, queryPlan) {
  const text = `${record.title || ""}\n${record.abstract_preview || ""}`.toLowerCase();
  if (!passesTopicGate(queryPlan, text)) return -999;
  const terms = uniqueStrings([
    ...topicTokens(query),
    ...topicTokens(asArray(queryPlan?.local_queries).join(" ")),
    ...topicTokens(asArray(queryPlan?.openalex_queries).join(" ")),
    ...topicTokens(asArray(queryPlan?.must_terms).join(" ")),
  ], 50);
  let score = Number(record.local_score || 0) / 10;
  terms.forEach((term) => {
    if (text.includes(term)) score += term.length > 8 ? 2 : 0.7;
  });
  if (queryPlan?.strict_topic_gate && score < 2) return -999;
  return score;
}

function searchLocalCorpus(query, queryPlan, limit = 5) {
  const index = loadLocalIndex();
  if (!index.available) {
    return { available: false, source_total: index.source_total || 64183, note: index.reason, matches: [] };
  }
  const matches = index.records
    .map((record) => ({ record, score: localRecordScore(record, query, queryPlan) }))
    .filter((item) => item.score > -100)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((item, idx) => ({
      rank: idx + 1,
      corpusid: item.record.corpusid,
      title: cleanText(item.record.title, 260),
      abstract_preview: cleanText(item.record.abstract_preview, 420),
      score: Number(item.score.toFixed(3)),
      profile: item.record.profile || "local",
      source: item.record.source || "LitSearch local seed",
      reason: `Local LitSearch seed index; source_total=${index.source_total}; profile=${item.record.profile || "local"}; lexical_score=${item.score.toFixed(3)}.`,
    }));
  return {
    available: true,
    source_total: index.source_total,
    note: index.note,
    index_path: path.basename(LOCAL_INDEX_PATH),
    matches,
  };
}

function seedWebResearch(query, queries) {
  const results = [];
  if (isCarbonTopic(query)) {
    results.push(
      { title: "World Bank State and Trends of Carbon Pricing", url: "https://carbonpricingdashboard.worldbank.org/", snippet: "Authoritative policy and market dashboard for carbon pricing mechanisms." },
      { title: "ICAP ETS Allowance Price Explorer", url: "https://icapcarbonaction.com/en/ets-prices", snippet: "Tracks emissions trading system allowance prices and policy context." },
      { title: "Climate Focus carbon market review", url: "https://climatefocus.com/", snippet: "Public market commentary that should be treated as non-verified web context." },
    );
  } else if (isRagTopic(query)) {
    results.push(
      { title: "OpenAlex RAG evaluation metadata", url: "https://openalex.org/", snippet: `实时论文发现：${queries.slice(0, 3).join(" | ")}` },
      { title: "RAGAS evaluation framework", url: "https://docs.ragas.io/", snippet: "Common RAG evaluation vocabulary: faithfulness, answer relevance, context precision and recall; verify against papers before citing." },
      { title: "arXiv RAG evaluation papers", url: "https://arxiv.org/", snippet: "Used for manually checking preprint titles, authors, years and claims after OpenAlex discovery." },
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

const WEB_USER_AGENT = "ScholarLoop-Demo-WebResearch/0.1 (academic demo; no secrets)";
const WEB_SEARCH_URL = "https://lite.duckduckgo.com/lite/";
const FORUM_DOMAINS = ["reddit.com", "news.ycombinator.com", "ycombinator.com", "stackexchange.com", "stackoverflow.com", "quora.com", "zhihu.com", "v2ex.com", "segmentfault.com", "csdn.net", "groups.google.com"];

function isForumUrl(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return FORUM_DOMAINS.some((domain) => host.includes(domain));
  } catch (e) {
    return false;
  }
}

function decodeEntities(text) {
  return String(text || "").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
}

function stripHtml(value) {
  return decodeEntities(String(value || "").replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}

function decodeDuckUrl(href) {
  try {
    let raw = decodeEntities(href);
    if (raw.startsWith("//")) raw = "https:" + raw;
    const parsed = new URL(raw, "https://lite.duckduckgo.com/");
    const uddg = parsed.searchParams.get("uddg");
    return uddg ? uddg : parsed.toString();
  } catch (e) {
    return href;
  }
}

async function searchDuckDuckGo(query, maxResults, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const url = WEB_SEARCH_URL + "?q=" + encodeURIComponent(query);
    const response = await fetch(url, { signal: controller.signal, headers: { "user-agent": WEB_USER_AGENT, accept: "text/html" } });
    if (!response.ok) return [];
    const body = await response.text();
    const rows = body.split(/<tr>\s*<td valign="top">/);
    const items = [];
    for (const row of rows) {
      const link = row.match(/<a\b([^>]*result-link[^>]*)>(.*?)<\/a>/is);
      if (!link) continue;
      const hrefMatch = link[1].match(/href=["']([^"']+)["']/i);
      if (!hrefMatch) continue;
      const title = stripHtml(link[2]);
      const href = decodeDuckUrl(hrefMatch[1]);
      const snippetMatch = row.match(/<td class=["']result-snippet["']>(.*?)<\/td>/is);
      const snippet = snippetMatch ? stripHtml(snippetMatch[1]) : "";
      if (title && href) items.push({ title, url: href, snippet, is_forum: isForumUrl(href), source: "duckduckgo_lite" });
      if (items.length >= maxResults) break;
    }
    return items;
  } catch (e) {
    return [];
  } finally {
    clearTimeout(timer);
  }
}

async function liveWebResearch(query, queries) {
  const topic = String(query || "").split(/\s+/).filter(Boolean).join(" ");
  if (!topic) return null;
  const generalQueries = [`${topic} current discussion risks policy market review`];
  asArray(queries).slice(0, 2).forEach((q) => { if (q) generalQueries.push(`${q} review outlook risks policy market`); });
  const forumQuery = `${topic} 讨论 经验 reddit hacker news stackexchange zhihu`;

  const maxResults = 8;
  const seenQuery = new Set();
  const seenUrl = new Set();
  const allItems = [];
  const usedQueries = [];
  const errors = [];

  async function run(q, cap) {
    if (!q) return;
    const key = q.toLowerCase();
    if (seenQuery.has(key)) return;
    seenQuery.add(key);
    const items = await searchDuckDuckGo(q, cap, 7000);
    usedQueries.push(q);
    for (const item of items) {
      if (seenUrl.has(item.url)) continue;
      seenUrl.add(item.url);
      allItems.push(item);
    }
  }

  try {
    await run(forumQuery, Math.max(3, Math.floor(maxResults / 2)));
    for (const q of generalQueries) {
      if (allItems.length >= maxResults + 4) break;
      await run(q, maxResults);
    }
  } catch (e) {
    errors.push({ error: String((e && e.message) || e).slice(0, 200) });
  }

  if (!allItems.length) return null;
  const forumItems = allItems.filter((i) => i.is_forum);
  const otherItems = allItems.filter((i) => !i.is_forum);
  const ordered = forumItems.concat(otherItems).slice(0, maxResults);
  return {
    search_provider: "duckduckgo_lite",
    queries: usedQueries,
    results: ordered,
    page_excerpts: [],
    forum_count: forumItems.length,
    errors,
    notice: "Web research is live and non-verified; links must be opened and verified before citing.",
  };
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
    web_research_digest: {
      overview: "基于本轮检索到的公开网页 / 社区来源做的方向性综述；以下均需打开原文核验，不作为承重证据。",
      community_views: webResearch.results.slice(0, 4).filter((r) => r.url).map((r) => ({ point: r.title, source_title: r.title, url: r.url })),
      conclusion: "先打开上述真实来源核验，再结合 OpenAlex 论文与本地语料形成判断；网络 / 社区讨论只作线索，不当承重证据。",
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
    web_research_digest: (() => {
      const d = objectValue(src.web_research_digest || fb.web_research_digest);
      return {
        overview: cleanText(d.overview || "", 1400),
        community_views: valueList(d.community_views).map((v) => {
          const o = objectValue(v);
          return { point: cleanText(o.point || o.view || o.title || v, 500), source_title: cleanText(o.source_title || o.title || "", 200), url: cleanText(o.url || o.link || "", 400) };
        }).filter((v) => v.point || v.url).slice(0, 8),
        conclusion: cleanText(d.conclusion || "", 1000),
      };
    })(),
  };
}

function parseJsonContent(text) {
  const raw = cleanText(text, 8000).replace(/^```json\s*/i, "").replace(/```$/i, "");
  return JSON.parse(raw);
}

function normalizeQueryPlan(query, candidate, fallback) {
  const src = objectValue(candidate);
  const fb = objectValue(fallback);
  const openalex = uniqueStrings([
    ...asArray(src.openalex_queries),
    ...asArray(src.queries),
    ...asArray(fb.openalex_queries),
  ], 8);
  const localQueries = uniqueStrings([
    ...asArray(src.local_queries),
    ...asArray(src.local_search_queries),
    ...asArray(fb.local_queries),
  ], 8);
  const mustTerms = uniqueStrings([
    ...asArray(src.must_terms),
    ...asArray(src.required_terms),
    ...asArray(fb.must_terms),
  ], 16);
  const rejectIfMissingAny = uniqueStrings([
    ...asArray(src.reject_if_missing_any),
    ...asArray(src.required_any),
    ...asArray(fb.reject_if_missing_any),
  ], 12);
  const excludeTerms = uniqueStrings([
    ...asArray(src.exclude_terms),
    ...asArray(fb.exclude_terms),
  ], 12);
  return {
    planner: src.planner || (src.openalex_queries ? "deepseek_query_planner" : fb.planner || "static_topic_rules"),
    intent_cn: cleanText(src.intent_cn || src.intent || fb.intent_cn || `围绕“${query}”进行主题检索。`, 500),
    openalex_queries: openalex.length ? openalex : fallbackQueries(query),
    local_queries: localQueries.length ? localQueries : [query],
    must_terms: mustTerms,
    reject_if_missing_any: rejectIfMissingAny,
    exclude_terms: excludeTerms,
    strict_topic_gate: Boolean(src.strict_topic_gate ?? fb.strict_topic_gate),
    warnings: evidenceList(src.warnings || []),
  };
}

async function deepseekQueryPlan(query, fallbackPlan) {
  if (!DEEPSEEK_API_KEY) return { plan: fallbackPlan, meta: { calls: 0, tokens: 0, fallback: true, reason: "DeepSeek key not configured" } };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 9000);
  try {
    const response = await fetch(`${DEEPSEEK_BASE_URL.replace(/\/$/, "")}/chat/completions`, {
      method: "POST",
      signal: controller.signal,
      headers: { "content-type": "application/json", authorization: `Bearer ${DEEPSEEK_API_KEY}` },
      body: JSON.stringify({
        model: DEEPSEEK_MODEL,
        temperature: 0,
        max_tokens: 850,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: "你是科研检索 Query Planner。只返回 JSON，不返回论文标题，不编造论文。你的任务是把中文/混合主题改写成适合 OpenAlex 的英文检索词，并给出本地语料补强词和过滤边界。" },
          { role: "user", content: `用户主题: ${query}\n静态兜底计划: ${JSON.stringify(fallbackPlan)}\n请返回 JSON：{intent_cn, openalex_queries:[3到5个英文查询], local_queries:[3到5个短查询], must_terms:[相关关键词], reject_if_missing_any:[至少命中一个的关键词], exclude_terms:[明显排除词], strict_topic_gate:boolean, warnings:[string]}。要求：OpenAlex 查询优先英文；RAG/检索增强生成主题必须包含 retrieval augmented generation/RAG/evaluation/benchmark/faithfulness 等词；不要输出具体论文标题。` },
        ],
      }),
    });
    if (!response.ok) throw new Error(`DeepSeek planner ${response.status}`);
    const data = await response.json();
    const content = data?.choices?.[0]?.message?.content || "{}";
    return {
      plan: normalizeQueryPlan(query, parseJsonContent(content), fallbackPlan),
      meta: { calls: 1, tokens: data?.usage?.total_tokens || 0, fallback: false },
    };
  } catch (error) {
    return {
      plan: fallbackPlan,
      meta: { calls: 0, tokens: 0, fallback: true, reason: cleanText(error.message || error, 160) },
    };
  } finally {
    clearTimeout(timer);
  }
}

async function deepseekSummary(query, rows, webResearch, queryPlan = null, localCorpus = null) {
  if (!DEEPSEEK_API_KEY || !rows.length) return { summary: fallbackSummary(query, rows, webResearch), meta: { calls: 0, tokens: 0, cached: false } };
  const paperPayload = rows.slice(0, 8).map((r) => ({ title: r.title, year: r.year, venue: r.venue, citations: r.citation_count, abstract_preview: r.abstract_preview }));
  const localPayload = asArray(localCorpus?.matches).slice(0, 5).map((r) => ({ title: r.title, corpusid: r.corpusid, abstract_preview: r.abstract_preview, profile: r.profile }));
  const webPayload = (webResearch.results || []).slice(0, 6).map((r) => ({ title: r.title, url: r.url, snippet: r.snippet, is_forum: r.is_forum }));
  const response = await fetch(`${DEEPSEEK_BASE_URL.replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${DEEPSEEK_API_KEY}` },
    body: JSON.stringify({
      model: DEEPSEEK_MODEL,
      temperature: 0.2,
      max_tokens: 3200,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: "你是谨慎的中文科研调研助手。只返回 JSON。只能使用提供的 OpenAlex 论文和网页片段，不得编造论文、URL、指标、价格或网络观点。" },
        { role: "user", content: `主题: ${query}\n查询规划: ${JSON.stringify(queryPlan || {})}\nOpenAlex 候选论文（主证据）: ${JSON.stringify(paperPayload)}\n本地 64,183 篇 LitSearch 语料补强候选（只作补充/兜底，不替代 OpenAlex 元数据）: ${JSON.stringify(localPayload)}\n网页/背景片段: ${JSON.stringify(webPayload)}\n请用中文返回 JSON，键包括：prior_issues:[{issue,evidence,verification}], reading_route:[{stage,goal,papers}], research_plan:[{step,title,actions,output}], network_research_experience:[{title,detail,evidence}], web_reputation:[{view,evidence,verification}], caution_points:[string], deepseek_cn_summary:{title,summary,findings,evidence}, web_research_digest:{overview, community_views:[{point, source_title, url}], conclusion}。其中 web_research_digest 要做厚：overview 写一段较充实的网络调研综述；community_views 必须逐条来自上面“网页/背景片段”里的真实条目，point 写该来源反映的观点、source_title 与 url 只能用片段里出现过的真实标题/链接（is_forum 为 true 的论坛/社区条目优先选取）；conclusion 给出“该怎么做”的综合结论。严禁编造任何不在所给片段里的链接、论坛帖、指标或价格。` },
      ],
    }),
  });
  if (!response.ok) throw new Error(`DeepSeek ${response.status}`);
  const data = await response.json();
  const content = data?.choices?.[0]?.message?.content || "{}";
  return { summary: parseJsonContent(content), meta: { calls: 1, tokens: data?.usage?.total_tokens || 0, cached: false } };
}


function rateLimitFallbackPayload(query, queries, used, errors, started) {
  const topicIssue = isCarbonTopic(query)
    ? "\u78b3\u4ef7\u7814\u7a76\u8981\u5148\u533a\u5206\u5e02\u573a\u673a\u5236\u3001\u653f\u7b56\u51b2\u51fb\u548c\u4ef7\u683c\u6ce2\u52a8\u3002"
    : isMachineLearningTopic(query)
      ? "\u673a\u5668\u5b66\u4e60\u4e3b\u9898\u9700\u8981\u5148\u6536\u7a84\u5230\u4e00\u4e2a\u5177\u4f53\u4efb\u52a1\u3002"
      : "\u5148\u660e\u786e\u4e3b\u9898\u8fb9\u754c\u3001\u6570\u636e\u6765\u6e90\u548c\u8bc4\u4ef7\u6307\u6807\u3002";
  const webResearch = seedWebResearch(query, used.length ? used : queries);
  return {
    schema_version: "m130.search_response.v1",
    label: "OpenAlex \u9650\u6d41\u4fdd\u62a4\uff1a\u7ed3\u6784\u5316\u56de\u9000",
    verified_load_bearing: false,
    deterministic: true,
    source_contract: "OpenAlex 429 \u6216\u989d\u5ea6\u4e0d\u8db3\u65f6\uff0c\u4e0d\u5c55\u793a\u4f2a\u9020\u8bba\u6587\uff0c\u53ea\u5c55\u793a\u5f85\u6838\u9a8c\u7684\u8c03\u7814\u8def\u7ebf\u3002",
    status: "ok",
    enabled: true,
    reason: "\u5b9e\u65f6\u8bba\u6587\u6e90\u5f53\u524d\u88ab\u9650\u6d41\uff1b\u5df2\u8fd4\u56de\u53ef\u8bfb\u7684\u4e94\u6a21\u5757\u56de\u9000\uff0c\u672a\u7f16\u9020\u8bba\u6587\u63a8\u8350\u3002",
    fallback_reason: errors.map((e) => `${e.query}: ${e.message || e.status}`).join("; "),
    query,
    decomposition: { subqueries: queries, criteria: ["topic scoping", "retry later", "manual verification required"] },
    results: [],
    cost: { llm_calls: 0, tokens: 0, latency_s: (Date.now() - started) / 1000 },
    notice: "\u8fd9\u662f\u9650\u6d41\u4fdd\u62a4\u56de\u9000\uff1a\u7b49 OpenAlex \u6062\u590d\u6216\u914d\u7f6e API key \u540e\u4f1a\u81ea\u52a8\u56de\u5230\u5b9e\u65f6\u8bba\u6587\u7ed3\u679c\u3002",
    raw_mode: "openalex_rate_limit_fallback",
    source: { corpus: "OpenAlex temporarily rate-limited", ranker: "structured_fallback" },
    topic_research: {
      intent: "\u5f53\u524d OpenAlex \u8fd4\u56de\u9650\u6d41\u6216\u4e34\u65f6\u4e0d\u53ef\u7528\uff0c\u5148\u7ed9\u51fa\u4e0d\u5192\u5145\u5b9e\u65f6\u8bba\u6587\u7684\u8c03\u7814\u6846\u67b6\u3002",
      searched_queries: used,
      recommended_papers: [],
      prior_issues: [
        { issue: topicIssue, evidence: ["\u6682\u65e0\u5b9e\u65f6\u5019\u9009\u8bba\u6587\uff1aOpenAlex \u5f53\u524d\u9650\u6d41\uff0c\u9875\u9762\u4e0d\u4f1a\u7f16\u9020\u6807\u9898\u3001DOI \u6216\u5f15\u7528\u91cf\u3002"], verification: "OpenAlex 429; retry after quota/rate window or configure OPENALEX_API_KEY." },
        { issue: "\u4e0d\u628a\u56de\u9000\u5185\u5bb9\u5192\u5145\u4e3a\u5b9e\u65f6\u8bba\u6587\u8bc1\u636e\u3002", evidence: ["/api/search fallback"], verification: "\u9700\u8981\u7a0d\u540e\u91cd\u65b0\u8fd0\u884c\u5b9e\u65f6\u641c\u7d22\u3002" },
      ],
      reading_route: [
        { stage: "\u7b2c 1 \u6b65\uff1a\u6536\u7a84\u4e3b\u9898", goal: "\u628a\u8f93\u5165\u4e3b\u9898\u62c6\u6210 3-5 \u4e2a\u53ef\u68c0\u7d22\u5b50\u95ee\u9898\uff0c\u907f\u514d\u4e00\u6b21\u641c\u5f97\u8fc7\u5bbd\u3002", papers: [] },
        { stage: "\u7b2c 2 \u6b65\uff1a\u6062\u590d\u5b9e\u65f6\u8bba\u6587\u540e\u6838\u9a8c", goal: "\u7b49 OpenAlex \u6062\u590d\u540e\uff0c\u4f18\u5148\u6838\u9a8c\u6807\u9898\u3001\u5e74\u4efd\u3001DOI\u3001\u6458\u8981\u548c\u6765\u6e90\u94fe\u63a5\u3002", papers: [] },
        { stage: "\u7b2c 3 \u6b65\uff1a\u5f62\u6210\u8ba1\u5212", goal: "\u628a\u524d\u4eba\u95ee\u9898\u3001\u9605\u8bfb\u8def\u7ebf\u3001\u6267\u884c\u8ba1\u5212\u548c\u7f51\u7edc\u8c03\u7814\u6574\u5408\u6210\u4e00\u5c4f\u53ef\u770b\u7684\u7ed3\u679c\u3002", papers: [] },
      ],
      research_plan: [
        { step: 1, title: "\u5b9a\u4e49\u4e3b\u9898\u8fb9\u754c", actions: ["\u660e\u786e\u7814\u7a76\u5bf9\u8c61", "\u786e\u5b9a\u6570\u636e\u6765\u6e90", "\u5217\u51fa\u8bc4\u4ef7\u6307\u6807"], output: "\u5b50\u95ee\u9898\u6e05\u5355" },
        { step: 2, title: "\u5efa\u7acb\u5019\u9009\u8bba\u6587\u8868", actions: ["\u7b49\u5f85 OpenAlex \u6062\u590d", "\u8bb0\u5f55 DOI/URL", "\u6807\u6ce8\u6458\u8981\u662f\u5426\u7f3a\u5931"], output: "\u6587\u732e\u6838\u9a8c\u8868" },
        { step: 3, title: "\u505a\u53ef\u590d\u73b0\u5c0f\u5b9e\u9a8c", actions: ["\u9009\u62e9\u4e00\u4e2a\u5c0f\u5207\u53e3", "\u5b9e\u73b0\u57fa\u7ebf", "\u5c55\u793a\u8bef\u5dee\u548c\u5931\u8d25\u6837\u4f8b"], output: "\u53ef\u6f14\u793a Demo" },
      ],
      network_research_experience: [
        { title: "\u7f51\u7edc\u8c03\u7814\u7ecf\u9a8c", detail: "OpenAlex \u662f\u8bba\u6587\u53d1\u73b0\u6e90\uff1b\u9047\u5230 429 \u65f6\u5e94\u51cf\u5c11\u8bf7\u6c42\u3001\u4f7f\u7528\u7f13\u5b58\u3001\u52a0\u9000\u907f\uff0c\u6700\u597d\u914d\u7f6e OpenAlex API key\u3002", evidence: ["OpenAlex 429", "cache", "backoff"] },
      ],
      web_reputation: [],
      caution_points: ["\u5f53\u524d\u662f\u9650\u6d41\u56de\u9000\uff0c\u4e0d\u662f\u5b9e\u65f6\u8bba\u6587\u7ed3\u679c\u3002", "\u5f15\u7528\u524d\u5fc5\u987b\u6838\u9a8c\u539f\u6587\u3002", "\u5efa\u8bae\u914d\u7f6e OPENALEX_API_KEY \u63d0\u5347\u7a33\u5b9a\u6027\u3002"],
      deepseek_cn_summary: { title: "\u9650\u6d41\u65f6\u7684\u53ef\u9760\u56de\u9000", summary: "\u5b9e\u65f6\u8bba\u6587\u63a5\u53e3\u6682\u65f6\u4e0d\u53ef\u7528\u65f6\uff0c\u7cfb\u7edf\u4e0d\u5e94\u7f16\u9020\u8bba\u6587\u3002\u66f4\u5408\u9002\u7684\u505a\u6cd5\u662f\u5c55\u793a\u8c03\u7814\u8def\u7ebf\u3001\u95ee\u9898\u5206\u89e3\u548c\u5f85\u6838\u9a8c\u6e05\u5355\u3002", findings: ["\u4e0d\u7f16\u9020\u8bba\u6587", "\u4fdd\u7559\u8c03\u7814\u8def\u7ebf", "\u6062\u590d\u540e\u81ea\u52a8\u56de\u5230\u5b9e\u65f6\u68c0\u7d22"], evidence: ["OpenAlex 429"] },
      web_research: webResearch,
      deepseek_api_note: { role: "OpenAlex \u9650\u6d41\u65f6\u4e0d\u989d\u5916\u6d88\u8017 DeepSeek\uff1b\u5b9e\u65f6\u6062\u590d\u540e\u7ee7\u7eed\u670d\u52a1\u7aef\u5f52\u7eb3\u3002", base_url: DEEPSEEK_BASE_URL, limitation: "API key never exposed to browser." },
      limitations: ["No live papers in fallback mode.", "Retry after OpenAlex quota/rate window.", "Use an OpenAlex API key for production demos."],
    },
  };
}

async function buildPayload(query) {
  const started = Date.now();
  const fallbackPlan = staticQueryPlan(query);
  const { plan: queryPlan, meta: plannerMeta } = await deepseekQueryPlan(query, fallbackPlan);
  const queries = uniqueStrings(queryPlan.openalex_queries, 8);
  const localCorpus = searchLocalCorpus(query, queryPlan, 5);
  const { rows, used, errors } = await paperRows(query, queries, 8, queryPlan);
  if (!rows.length) {
    const fallbackErrors = errors.length ? errors : [{ query: queries[0] || query, status: "empty", message: "OpenAlex returned no candidates" }];
    const fallbackPayload = rateLimitFallbackPayload(query, queries, used, fallbackErrors, started);
    fallbackPayload.label = localCorpus.matches.length ? "OpenAlex 暂无强相关结果：本地语料兜底" : fallbackPayload.label;
    fallbackPayload.query_plan = queryPlan;
    fallbackPayload.local_corpus = localCorpus;
    fallbackPayload.topic_research.local_corpus_matches = localCorpus.matches;
    fallbackPayload.topic_research.deepseek_api_note = {
      role: "DeepSeek 先做检索规划；OpenAlex 暂无强相关候选时，本地 LitSearch seed 只作兜底线索。",
      base_url: DEEPSEEK_BASE_URL,
      limitation: "不把本地兜底线索冒充为 OpenAlex 实时论文证据。",
    };
    return fallbackPayload;
  }
  let webResearch = await liveWebResearch(query, used.length ? used : queries).catch(() => null);
  if (!webResearch || !(webResearch.results || []).length) webResearch = seedWebResearch(query, used.length ? used : queries);
  const fallback = fallbackSummary(query, rows, webResearch);
  const { summary: rawSummary, meta } = await deepseekSummary(query, rows, webResearch, queryPlan, localCorpus).catch(() => ({ summary: fallback, meta: { calls: 0, tokens: 0, fallback: true } }));
  const summary = sanitizeSummary(rawSummary, fallback);
  return {
    schema_version: "m130.search_response.v1",
    label: DEEPSEEK_API_KEY ? "DeepSeek规划 + OpenAlex主检索 + 本地语料补强" : "OpenAlex主检索 + 本地语料补强",
    verified_load_bearing: false,
    deterministic: false,
    source_contract: "实时结果只用于调研发现，不作为承重证据；失败时显示明确回退。",
    status: rows.length ? "ok" : "empty",
    enabled: true,
    reason: DEEPSEEK_API_KEY ? "DeepSeek 先生成英文检索规划，OpenAlex 负责真实论文元数据，本地 64,183 篇 LitSearch seed 负责补强/兜底，DeepSeek 最后做中文归纳。" : "OpenAlex 负责真实论文元数据，本地 64,183 篇 LitSearch seed 负责补强/兜底。",
    fallback_reason: null,
    query,
    query_plan: queryPlan,
    decomposition: { subqueries: queries, criteria: ["DeepSeek query planning", "OpenAlex primary evidence", "LitSearch local supplement", "manual verification required"] },
    results: rows,
    local_corpus: localCorpus,
    cost: { llm_calls: (plannerMeta.calls || 0) + (meta.calls || 0), tokens: (plannerMeta.tokens || 0) + (meta.tokens || 0), latency_s: (Date.now() - started) / 1000, planner_fallback: Boolean(plannerMeta.fallback) },
    notice: "实时主题调研只是发现草稿；论文和网页结论需人工核验。",
    raw_mode: "serverless_topic_research",
    source: { corpus: "OpenAlex live metadata + LitSearch local seed", ranker: "deepseek_planned_openalex_with_local_supplement" },
    topic_research: {
      intent: `围绕“${query}”进行后端实时主题调研。`,
      searched_queries: used,
      query_planner: queryPlan,
      recommended_papers: rows,
      local_corpus_matches: localCorpus.matches,
      prior_issues: summary.prior_issues || [],
      reading_route: summary.reading_route || [],
      research_plan: summary.research_plan || [],
      network_research_experience: summary.network_research_experience || [],
      web_reputation: summary.web_reputation || [],
      caution_points: summary.caution_points || [],
      deepseek_cn_summary: summary.deepseek_cn_summary || fallbackSummary(query, rows, webResearch).deepseek_cn_summary,
      web_research_digest: summary.web_research_digest || fallbackSummary(query, rows, webResearch).web_research_digest,
      web_research: webResearch,
      deepseek_api_note: {
        role: DEEPSEEK_API_KEY ? "Query planner first, then Chinese synthesis from supplied OpenAlex/local/web evidence on the server side" : "Not configured on this deployment",
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
  const payloadCacheKey = `${CACHE_VERSION}::${query.toLowerCase()}`;
  const cachedPayload = cacheGet(payloadCache, payloadCacheKey);
  if (cachedPayload) {
    return res.status(200).json({
      ...cachedPayload,
      label: cachedPayload.label.startsWith("缓存：") ? cachedPayload.label : `缓存：${cachedPayload.label}`,
      cache: { hit: true, ttl_ms: CACHE_TTL_MS },
    });
  }
  try {
    const payload = await buildPayload(query);
    cacheSet(payloadCache, payloadCacheKey, payload, payload.raw_mode === "openalex_rate_limit_fallback" ? 60_000 : CACHE_TTL_MS);
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
