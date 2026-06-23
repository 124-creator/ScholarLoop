const DEEPSEEK_BASE_URL = process.env.DEEPSEEK_BASE_URL || "https://api.deepseek.com";
const DEEPSEEK_MODEL = process.env.DEEPSEEK_MODEL || process.env.LLM_MODEL || "deepseek-chat";
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

function fallbackQueries(query) {
  if (isCarbonTopic(query)) {
    return [
      "carbon price forecasting",
      "carbon market price prediction machine learning",
      "emissions trading scheme carbon price volatility",
      "carbon pricing policy impact carbon market",
    ];
  }
  return [query, `${query} survey`, `${query} review`, `${query} machine learning`].filter(Boolean);
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
  } else {
    results.push({ title: "OpenAlex live metadata", url: "https://openalex.org/", snippet: `Live academic metadata search for: ${queries.slice(0, 3).join(" | ")}` });
  }
  return { search_provider: "serverless_seed_sources", queries, results, page_excerpts: [] };
}

function fallbackSummary(query, rows, webResearch) {
  const titles = rows.slice(0, 4).map((r) => r.title).filter(Boolean);
  return {
    prior_issues: [
      { issue: "Define the research boundary before modeling or comparison.", evidence: titles.slice(0, 2), verification: "Generated from live OpenAlex titles/abstracts; read the papers before treating as evidence." },
      { issue: "Check data availability, time coverage, baselines, and evaluation design.", evidence: titles.slice(1, 3), verification: "Candidate issue; requires manual verification." },
      { issue: "Avoid optimizing only for a single metric without robustness and error analysis.", evidence: titles.slice(2, 4), verification: "Method-level caution; verify against full texts." },
    ],
    reading_route: [
      { stage: "Round 1", goal: "Read the most directly relevant survey/high-citation papers to fix terminology and scope.", papers: titles.slice(0, 3) },
      { stage: "Round 2", goal: "Build a matrix of data, methods, metrics, limitations, and reproducibility gaps.", papers: titles.slice(3, 6) },
      { stage: "Round 3", goal: "Select 1-2 feasible gaps for a demo or experiment plan.", papers: titles.slice(0, 6) },
    ],
    research_plan: [
      { step: 1, title: "Clarify the task", actions: ["Define topic scope", "List variables/data sources", "Choose evaluation metrics"], output: "Problem definition and keyword table" },
      { step: 2, title: "Read and compare papers", actions: ["Summarize methods", "Record datasets and limits", "Mark unverifiable claims"], output: "Literature matrix" },
      { step: 3, title: "Build a baseline", actions: ["Prepare data", "Run simple baselines", "Track errors"], output: "Reproducible baseline report" },
      { step: 4, title: "Improve and present", actions: ["Add one clear improvement", "Run ablation", "Package the evidence chain"], output: "Portfolio-ready demo" },
    ],
    network_research_experience: [
      { title: "Separate live metadata from verified evidence", detail: "OpenAlex/Web snippets are useful for discovery, but load-bearing claims need full-text verification.", evidence: webResearch.results.slice(0, 3).map((r) => r.title) },
      { title: "Use English query expansion", detail: "Short Chinese topics often need English academic query expansion to retrieve enough literature.", evidence: [] },
    ],
    web_reputation: [
      { view: "Public web sources are context, not final proof; commercial forecasts or dashboards may have different incentives.", evidence: webResearch.results.slice(0, 3).map((r) => r.title), verification: "Open sources manually before citing." },
    ],
    caution_points: ["Do not expose private API keys in a static page.", "Live metadata changes over time; record search date.", "Open full papers before making load-bearing claims."],
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
        { role: "system", content: "You are a cautious research planning assistant. Return JSON only. Use only supplied papers and web snippets. Do not invent papers, URLs, metrics, market prices, or online opinions." },
        { role: "user", content: `Topic: ${query}\nOpenAlex papers: ${JSON.stringify(paperPayload)}\nWeb/context snippets: ${JSON.stringify(webPayload)}\nReturn JSON with keys: prior_issues:[{issue,evidence,verification}], reading_route:[{stage,goal,papers}], research_plan:[{step,title,actions,output}], network_research_experience:[{title,detail,evidence}], web_reputation:[{view,evidence,verification}], caution_points:[string].` },
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
  const { summary, meta } = await deepseekSummary(query, rows, webResearch).catch(() => ({ summary: fallbackSummary(query, rows, webResearch), meta: { calls: 0, tokens: 0, fallback: true } }));
  return {
    schema_version: "m130.search_response.v1",
    label: DEEPSEEK_API_KEY ? "Serverless realtime: OpenAlex + DeepSeek" : "Serverless realtime: OpenAlex only",
    verified_load_bearing: false,
    deterministic: false,
    source_contract: "Realtime results are not verified load-bearing evidence. Failed calls return explicit empty fallback.",
    status: rows.length ? "ok" : "empty",
    enabled: true,
    reason: DEEPSEEK_API_KEY ? "Live serverless search used OpenAlex metadata and DeepSeek summarization." : "Live serverless search used OpenAlex metadata; DeepSeek key is not configured.",
    fallback_reason: null,
    query,
    decomposition: { subqueries: queries, criteria: ["topic relevance", "metadata availability", "manual verification required"] },
    results: rows,
    cost: { llm_calls: meta.calls || 0, tokens: meta.tokens || 0, latency_s: (Date.now() - started) / 1000 },
    notice: "Realtime topic research is a discovery draft; verify papers and web claims manually.",
    raw_mode: "serverless_topic_research",
    source: { corpus: "OpenAlex live metadata", ranker: "serverless_topic_research" },
    topic_research: {
      intent: `Live topic research for: ${query}`,
      searched_queries: used,
      recommended_papers: rows,
      prior_issues: summary.prior_issues || [],
      reading_route: summary.reading_route || [],
      research_plan: summary.research_plan || [],
      network_research_experience: summary.network_research_experience || [],
      web_reputation: summary.web_reputation || [],
      caution_points: summary.caution_points || [],
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
