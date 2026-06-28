from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from scholarloop.connectors.openalex import OpenAlexConnector
from scholarloop.corpus import LitSearchCorpus
from scholarloop.llm import LLMClient
from scholarloop.query.decompose import QueryDecomposer
from scholarloop.rank.fusion_v2 import FusionV2Config, build_feature_matrix, rank_with_features
from scholarloop.rank.rerank import CrossEncoderReranker
from scholarloop.retrieval.bm25 import BM25Retriever
from scholarloop.retrieval.dense_v2 import DEFAULT_DENSE_V2_MODEL, DenseV2Retriever
from scholarloop.utils import top_ids_from_scores
from scholarloop.demo.web_research import web_research_for_topic


REALTIME_ENV = "SCHOLARLOOP_REALTIME_ENABLED"
DEFAULT_DISABLED_MESSAGE = "实时模式默认关闭；设置 SCHOLARLOOP_REALTIME_ENABLED=1 后才会运行在线 LLM/检索。"
DEFAULT_TIMEOUT_S = 180.0
CJK_RE = re.compile(r"[\u3400-\u9fff]")
CARBON_TOPIC_RE = re.compile(
    r"(碳价|碳价格|碳市场|碳交易|碳定价|碳排放权|carbon\s+(price|pricing|market|trading)|emissions?\s+trading)",
    re.I,
)


@dataclass
class RealtimeRuntime:
    repo: LitSearchCorpus
    corpus: Any
    corpus_ids: np.ndarray
    docs: list[str]
    bm25: BM25Retriever
    dense: DenseV2Retriever
    cross: CrossEncoderReranker


_RUNTIME_LOCK = threading.RLock()
_RUNTIME_CACHE: RealtimeRuntime | None = None
_PRECHECK_CACHE: dict[str, Any] | None = None


def realtime_enabled() -> bool:
    return os.environ.get(REALTIME_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def unavailable(
    reason: str = DEFAULT_DISABLED_MESSAGE,
    *,
    enabled: bool = False,
    elapsed_s: float = 0.0,
    llm_calls: int = 0,
    tokens: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": "m100.realtime_response.v1",
        "mode": "realtime_optional",
        "enabled": enabled,
        "status": "unavailable",
        "reason": reason,
        "notice": "实时结果非 verified 承重；失败时不编造推荐。",
        "cost": {"llm_calls": llm_calls, "tokens": tokens, "latency_s": elapsed_s},
        "results": [],
    }


def clear_realtime_runtime_cache() -> None:
    """Clear in-process caches. Intended for tests and deterministic equivalence checks."""

    global _RUNTIME_CACHE, _PRECHECK_CACHE
    with _RUNTIME_LOCK:
        _RUNTIME_CACHE = None
        _PRECHECK_CACHE = None


def _build_runtime() -> RealtimeRuntime:
    repo = LitSearchCorpus(Path("."))
    corpus = repo.load_corpus()
    corpus_ids = repo.corpus_ids
    docs = corpus["text"].tolist()
    bm25 = BM25Retriever(docs)
    dense = DenseV2Retriever(
        docs,
        cache_dir=Path("reports/m040/cache/dense_v2"),
        model_name=DEFAULT_DENSE_V2_MODEL,
        batch_size=64,
        device="cpu",
        local_files_only=False,
    )
    cross = CrossEncoderReranker(Path("reports/m100/cache/realtime_rerank"), batch_size=16, device="cpu")
    return RealtimeRuntime(repo=repo, corpus=corpus, corpus_ids=corpus_ids, docs=docs, bm25=bm25, dense=dense, cross=cross)


def _runtime(use_runtime_cache: bool = True) -> tuple[RealtimeRuntime, bool]:
    global _RUNTIME_CACHE
    if not use_runtime_cache:
        return _build_runtime(), False
    with _RUNTIME_LOCK:
        if _RUNTIME_CACHE is None:
            _RUNTIME_CACHE = _build_runtime()
            return _RUNTIME_CACHE, False
        return _RUNTIME_CACHE, True


def warm_realtime_cache() -> dict[str, Any]:
    start = time.perf_counter()
    _, reused = _runtime(use_runtime_cache=True)
    return {"status": "ok", "cache_reused": reused, "elapsed_s": time.perf_counter() - start}


def _precheck(llm: LLMClient, use_runtime_cache: bool) -> dict[str, Any]:
    global _PRECHECK_CACHE
    if use_runtime_cache and _PRECHECK_CACHE is not None:
        cached = dict(_PRECHECK_CACHE)
        cached["cached"] = True
        return cached
    result = dict(llm.precheck())
    result["cached"] = False
    if use_runtime_cache and result.get("valid"):
        _PRECHECK_CACHE = dict(result)
    return result


def _max_or_zero(arrays: list[np.ndarray], length: int) -> np.ndarray:
    if not arrays:
        return np.zeros(length, dtype=np.float32)
    return np.max(np.vstack(arrays), axis=0).astype(np.float32)


def _pool_from_scores(scores: list[np.ndarray], corpus_ids: np.ndarray, top_k: int) -> list[int]:
    pool: set[int] = set()
    for score in scores:
        pool.update(top_ids_from_scores(score, corpus_ids, top_k))
    return sorted(pool)


def _usage_tokens(meta: dict[str, Any] | None) -> int:
    usage = (meta or {}).get("usage") or {}
    return int(usage.get("total_tokens") or 0) if isinstance(usage, dict) else 0


def _llm_call_count(meta: dict[str, Any] | None) -> int:
    return 0 if (meta or {}).get("cached") else 1


def _has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def _needs_topic_research_path(query: str) -> bool:
    """Route topics outside the frozen local LitSearch corpus to live discovery."""

    return bool(_has_cjk(query) or CARBON_TOPIC_RE.search(query or ""))


def _fallback_topic_queries(query: str) -> list[str]:
    if CARBON_TOPIC_RE.search(query or ""):
        return [
            "carbon price forecasting",
            "carbon market price prediction machine learning",
            "emissions trading scheme carbon price volatility",
            "carbon pricing policy impact carbon market",
        ]
    return [query]


def _dedupe(items: list[str], *, limit: int = 6) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = " ".join(str(item or "").split())
        key = value.lower()
        if value and key not in seen:
            out.append(value)
            seen.add(key)
        if len(out) >= limit:
            break
    return out


def _topic_query_plan(llm: LLMClient, query: str, precheck: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    fallback = {
        "english_queries": _fallback_topic_queries(query),
        "intent": "围绕用户输入主题进行开放学术论文发现；结果为实时非 verified 调研草稿。",
        "criteria": ["主题相关", "方法或实证结果清晰", "优先包含综述、预测、影响因素或市场机制研究"],
    }
    if not precheck.get("valid"):
        return fallback, {"cached": True, "usage": {"total_tokens": 0}, "fallback": "llm_precheck_failed"}
    system = (
        "You convert short Chinese or English research topics into cautious academic search queries. "
        "Return JSON only. Do not invent paper titles. Prefer English queries for OpenAlex."
    )
    user = (
        "User topic: " + query + "\n"
        "Return one JSON object with keys:\n"
        "- english_queries: 3-5 English academic search strings;\n"
        "- intent: one Chinese sentence explaining the research intent;\n"
        "- criteria: 3-5 Chinese relevance criteria.\n"
        "If the topic is about 碳价格, include carbon price forecasting, carbon market, emissions trading scheme, and policy impact."
    )
    try:
        parsed, meta = llm.chat_json(
            "topic_query_plan_" + hashlib.sha256(query.encode("utf-8")).hexdigest()[:12],
            system,
            user,
            {"module": "demo.realtime.topic_query_plan", "query_sha12": hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]},
            max_tokens=1200,
        )
        queries = _dedupe(list(parsed.get("english_queries") or []) + fallback["english_queries"], limit=6)
        return {
            "english_queries": queries or fallback["english_queries"],
            "intent": str(parsed.get("intent") or fallback["intent"]),
            "criteria": list(parsed.get("criteria") or fallback["criteria"]),
        }, meta
    except Exception as exc:
        return fallback | {"planner_exception": type(exc).__name__}, {"cached": True, "usage": {"total_tokens": 0}, "fallback": str(exc)[:160]}


def _abstract_from_inverted_index(raw: dict[str, Any], *, limit: int = 900) -> str:
    inverted = raw.get("abstract_inverted_index") or {}
    if not isinstance(inverted, dict) or not inverted:
        return ""
    max_pos = 0
    for positions in inverted.values():
        if isinstance(positions, list) and positions:
            max_pos = max(max_pos, max(int(p) for p in positions))
    words = [""] * (max_pos + 1)
    for word, positions in inverted.items():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            idx = int(pos)
            if 0 <= idx < len(words):
                words[idx] = str(word)
    return " ".join(w for w in words if w).strip()[:limit]


def _openalex_url(raw: dict[str, Any]) -> str:
    primary = raw.get("primary_location") or {}
    return str(primary.get("landing_page_url") or raw.get("doi") or raw.get("id") or "")


TOPIC_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "using",
    "based",
    "about",
    "under",
    "over",
    "large",
    "small",
    "model",
    "models",
    "language",
}


def _topic_tokens(value: str) -> list[str]:
    tokens = re.findall(r"[a-z][a-z0-9-]{2,}", (value or "").lower())
    return [token for token in tokens if token not in TOPIC_STOPWORDS]


def _topic_relevance_score(query: str, title: str, abstract: str, citations: int | None) -> float:
    title_text = (title or "").lower()
    text = f"{title} {abstract}".lower()
    query_text = " ".join((query or "").lower().split())
    query_tokens = _topic_tokens(query_text)
    score = min(float(citations or 0), 1000.0) / 1000.0
    if abstract:
        score += 3.0
    if query_text and query_text in title_text:
        score += 5.0
    elif query_text and query_text in text:
        score += 2.0
    if query_tokens:
        title_hits = sum(1 for token in query_tokens if token in title_text)
        text_hits = sum(1 for token in query_tokens if token in text)
        score += (title_hits / len(query_tokens)) * 5.0
        score += (text_hits / len(query_tokens)) * 3.0
        if text_hits == 0:
            score -= 3.0
        for token in query_tokens:
            if token in title_text:
                score += 0.6
    phrase_terms = re.findall(r"[a-z][a-z0-9-]{2,}(?:\s+[a-z][a-z0-9-]{2,})", query_text)
    for phrase in phrase_terms:
        if phrase in title_text:
            score += 1.0
        elif phrase in text:
            score += 0.4
    if "compression" in query_text and "compression" not in text and "compress" not in text:
        score -= 3.0
    if CARBON_TOPIC_RE.search(query or "") or "carbon" in " ".join(query.lower().split()):
        if "carbon" in text:
            score += 3.0
        if any(term in text for term in ("price", "pricing", "market", "trading", "emission", "emissions", "ets")):
            score += 2.0
        if any(term in text for term in ("forecast", "forecasting", "prediction", "predict", "volatility", "policy", "scheme")):
            score += 1.5
        if "carbon price forecasting" in text or "carbon price prediction" in text:
            score += 2.0
        if "carbon" in title_text and any(term in title_text for term in ("price", "pricing", "market", "trading", "emission", "emissions", "ets")):
            score += 2.5
        elif not any(term in title_text for term in ("price", "pricing", "market", "trading", "emission", "emissions", "ets")):
            score -= 4.0
        if "carbon" not in text:
            score -= 6.0
    return score


def _paper_rows_from_openalex(queries: list[str], *, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    connector = OpenAlexConnector()
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    used_queries: list[str] = []
    for search_query in queries[:4]:
        records = connector.search_topic(search_query, max_results=max(limit * 3, 25))
        used_queries.append(search_query)
        for local_rank, record in enumerate(records, start=1):
            key = record.doi or record.external_id or record.title.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            abstract = _abstract_from_inverted_index(record.raw)
            relevance_score = _topic_relevance_score(search_query, record.title, abstract, record.citation_count)
            candidates.append(
                {
                    "_sort_score": relevance_score - (local_rank * 0.01),
                    "corpusid": record.external_id.rsplit("/", 1)[-1] or record.external_id,
                    "external_id": record.external_id,
                    "score": round(max(0.1, relevance_score / 14.0), 6),
                    "title": record.title,
                    "abstract_preview": abstract[:360],
                    "abstract_status": "openalex_abstract" if abstract else "missing_in_openalex",
                    "reason": (
                        f"OpenAlex topic search; query='{search_query}'; local_rank={local_rank}; "
                        f"topic_score={relevance_score:.3f}; abstract={'yes' if abstract else 'no'}; "
                        f"citations={record.citation_count}; year={record.year}"
                    ),
                    "authors": list(record.authors[:6]),
                    "year": record.year,
                    "venue": record.venue,
                    "doi": record.doi,
                    "url": _openalex_url(record.raw),
                    "source": record.source,
                    "citation_count": record.citation_count,
                    "authors_year": {
                        "status": "openalex_metadata",
                        "value": ", ".join(record.authors[:3]) + (f" ({record.year})" if record.year else ""),
                        "provenance": record.provenance.to_dict(),
                    },
                    "source_or_doi": {
                        "status": "openalex_metadata" if record.doi or _openalex_url(record.raw) else "需人工核验",
                        "value": record.doi or _openalex_url(record.raw),
                        "provenance": record.provenance.to_dict(),
                    },
                }
            )
    candidates.sort(key=lambda row: (-float(row.get("_sort_score") or 0.0), -int(row.get("citation_count") or 0), str(row.get("title") or "")))
    rows: list[dict[str, Any]] = []
    for rank, row in enumerate(candidates[:limit], start=1):
        clean = dict(row)
        clean.pop("_sort_score", None)
        clean["rank"] = rank
        rows.append(clean)
    return rows, used_queries


def _fallback_prior_issues(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    titles = [row.get("title") for row in rows[:4] if row.get("title")]
    if CARBON_TOPIC_RE.search(query or ""):
        return [
            {
                "issue": "碳价格受政策冲击、配额规则、能源价格和宏观变量共同影响，序列可能非平稳且阶段性变化明显。",
                "evidence": titles[:2],
                "verification": "由实时论文题名/摘要和领域常识归纳，需人工核验。",
            },
            {
                "issue": "不同碳市场之间可能存在溢出效应，单一市场建模容易漏掉跨市场信息。",
                "evidence": titles[1:3],
                "verification": "候选问题，后续应回到论文原文确认。",
            },
            {
                "issue": "预测模型容易只追求精度，缺少滚动验证、基线对照、消融实验和可解释性分析。",
                "evidence": titles[2:4],
                "verification": "方法论层面的候选问题，需结合具体文献确认。",
            },
        ]
    return [
        {
            "issue": "先确认主题边界、核心变量、常用数据集和主流评估指标，否则后续路线容易发散。",
            "evidence": titles[:3],
            "verification": "基于实时候选论文题名/摘要生成，需人工核验。",
        }
    ]


def _fallback_research_plan(query: str) -> list[dict[str, Any]]:
    if CARBON_TOPIC_RE.search(query or ""):
        return [
            {"step": 1, "title": "界定研究问题", "actions": ["确定市场：EU ETS / 中国全国碳市场 / 区域试点", "确定任务：价格预测、影响因素分析或风险预警"], "output": "问题定义 + 检索关键词表"},
            {"step": 2, "title": "系统阅读推荐论文", "actions": ["先读综述和高被引实证论文", "记录数据来源、变量、模型、评价指标和局限"], "output": "文献矩阵"},
            {"step": 3, "title": "建立数据与基线", "actions": ["收集碳价、能源、宏观、政策和市场交易变量", "完成清洗、缺失处理、时序切分和滚动验证"], "output": "可复现实验数据集 + BM25/ARIMA/LSTM/XGBoost 等基线"},
            {"step": 4, "title": "改进模型并做消融", "actions": ["比较机器学习、深度学习与混合模型", "加入政策事件、跨市场变量或注意力机制", "做消融和显著性/稳健性检验"], "output": "主实验表 + 消融实验"},
            {"step": 5, "title": "解释与形成作品展示", "actions": ["用 SHAP/特征重要性解释关键驱动因素", "把论文证据、实验结果和 Demo 串成可审计链路"], "output": "研究路线图 + 可展示作品集页面"},
        ]
    return [
        {"step": 1, "title": "明确问题边界", "actions": ["定义研究对象、数据、指标和目标用户"], "output": "问题定义"},
        {"step": 2, "title": "阅读推荐论文", "actions": ["整理方法、数据、指标、局限"], "output": "文献矩阵"},
        {"step": 3, "title": "形成可执行实验路线", "actions": ["建立基线、做对比、做误差分析"], "output": "实验计划"},
    ]


def _fallback_network_research_experience(query: str, rows: list[dict[str, Any]], web_research: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    has_abstract = sum(1 for row in rows if row.get("abstract_preview"))
    sources = sorted({str(row.get("source") or "OpenAlex") for row in rows if row.get("source")})
    web_results = (web_research or {}).get("results") or []
    web_titles = [item.get("title") for item in web_results[:4] if item.get("title")]
    if CARBON_TOPIC_RE.search(query or ""):
        return [
            {
                "title": "检索词要从中文主题扩展成英文术语族",
                "detail": "“碳价格”直接搜中文很容易丢结果；更稳的英文检索式包括 carbon price forecasting、carbon market、emissions trading scheme、carbon pricing policy impact。",
                "evidence": web_titles[:2] or [row.get("title") for row in rows[:3] if row.get("title")],
            },
            {
                "title": "先筛有摘要的候选，再看高被引和近年论文",
                "detail": f"本轮候选中有 {has_abstract}/{len(rows)} 篇带 OpenAlex 摘要。没有摘要时不能补写，只能标注并打开来源人工核验。",
                "evidence": [row.get("title") for row in rows if row.get("abstract_preview")][:3],
            },
            {
                "title": "DeepSeek 负责生成搜索意图和归纳网页证据，HTTP 检索由工具执行",
                "detail": "DeepSeek API 本身不直接浏览网页；本系统让 DeepSeek 生成/使用检索意图，工具真实访问 DuckDuckGo Lite 和网页片段，再把网页证据交给 DeepSeek 总结网络评价与注意点。",
                "evidence": web_titles or sources or ["openalex"],
            },
        ]
    return [
        {
            "title": "先拆关键词，再查开放学术 API",
            "detail": "实时调研先把用户问题拆成英文检索式，再向开放学术元数据源取论文；模型只负责归纳，不负责伪造证据。",
            "evidence": [row.get("title") for row in rows[:3] if row.get("title")],
        }
    ]


def _topic_summary(
    llm: LLMClient,
    query: str,
    rows: list[dict[str, Any]],
    web_research: dict[str, Any],
    precheck: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    fallback = {
        "prior_issues": _fallback_prior_issues(query, rows),
        "research_plan": _fallback_research_plan(query),
        "network_research_experience": _fallback_network_research_experience(query, rows, web_research),
        "web_reputation": [
            {
                "view": "公开网页调研结果只能作为方向感：需区分政策/市场评论、行业预测、学术论文和商业营销内容；若网页证据不足，应明确标注而不是补写结论。",
                "evidence": [item.get("title") for item in (web_research.get("results") or [])[:3] if item.get("title")],
                "verification": "需打开网页原文核验；不得当作 verified 结论。",
            }
        ],
        "caution_points": [
            "网页搜索结果会变化，商业机构预测可能有立场或营销目的。",
            "碳价/碳信用/碳市场/ETS 是不同概念，调研时要分清。",
            "政策和市场价格具有时效性，投递作品集应标注检索日期和来源。",
        ],
        "reading_route": [
            {"stage": "第一轮", "goal": "先读题名/摘要最相关的论文，确认术语和问题边界。", "papers": [row.get("title") for row in rows[:3] if row.get("title")]},
            {"stage": "第二轮", "goal": "按方法、数据、评价指标和局限整理文献矩阵。", "papers": [row.get("title") for row in rows[3:6] if row.get("title")]},
        ],
        "web_research_digest": {
            "overview": "本轮基于 DuckDuckGo Lite 实时检索到的公开网页/社区讨论做方向性综述；以下均需打开原文核验，不作为承重证据。",
            "community_views": [
                {"point": item.get("title"), "source_title": item.get("title"), "url": item.get("url")}
                for item in (web_research.get("results") or [])[:4]
                if item.get("url")
            ],
            "conclusion": "建议先打开上述真实来源核验，再结合 OpenAlex 论文与本地语料形成判断；网络讨论仅作线索，不当承重证据。",
        },
    }
    if not precheck.get("valid") or not rows:
        return fallback, {"cached": True, "usage": {"total_tokens": 0}, "fallback": "no_llm_or_no_rows"}
    paper_payload = [
        {
            "title": row.get("title"),
            "year": row.get("year"),
            "venue": row.get("venue"),
            "citations": row.get("citation_count"),
            "abstract_preview": row.get("abstract_preview"),
        }
        for row in rows[:8]
    ]
    web_payload = {
        "search_provider": web_research.get("search_provider"),
        "queries": web_research.get("queries") or [],
        "results": [
            {"title": item.get("title"), "url": item.get("url"), "snippet": item.get("snippet"), "is_forum": item.get("is_forum")}
            for item in (web_research.get("results") or [])[:8]
        ],
        "page_excerpts": [
            {"url": item.get("url"), "status": item.get("status"), "excerpt": item.get("excerpt")}
            for item in (web_research.get("page_excerpts") or [])[:4]
        ],
    }
    system = (
        "You are a cautious research planning assistant. Return Chinese JSON only. "
        "Use only the supplied OpenAlex paper snippets and web-search/page snippets. "
        "Do not invent papers, URLs, metrics, market prices, or online opinions. "
        "Every issue/opinion must include a verification note such as 需人工核验."
    )
    user = (
        "用户主题：" + query + "\n"
        "候选论文（OpenAlex 实时返回，非 verified 承重）：\n" + str(paper_payload) + "\n"
        "公开网页调研证据（DuckDuckGo Lite + 页面片段，非 verified 承重）：\n" + str(web_payload) + "\n"
        "请返回 JSON：\n"
        "{prior_issues:[{issue,evidence,verification}], "
        "research_plan:[{step,title,actions,output}], "
        "reading_route:[{stage,goal,papers}], "
        "network_research_experience:[{title,detail,evidence}], "
        "web_reputation:[{view,evidence,verification}], "
        "caution_points:[string], "
        "web_research_digest:{overview, community_views:[{point, source_title, url}], conclusion}}。\n"
        "目标是帮助用户先找推荐论文，再总结前人可能遇到的问题，最后给出第一步、第二步等执行路线，并说明网络上对该主题的评价/讨论和注意点。\n"
        "其中 web_research_digest 要做厚：overview 写一段较充实的网络调研综述；community_views 必须逐条来自上面“公开网页调研证据”里的真实条目，point 写该来源反映的观点、source_title 与 url 只能用证据里出现过的真实标题/链接（is_forum 为 true 的论坛/社区条目优先选取）；conclusion 给出“该怎么做”的综合结论。严禁编造任何不在所给证据里的链接、论坛帖、指标或市场价格。"
    )
    try:
        summary_cache_basis = query + str([r.get("external_id") for r in rows[:6]]) + str([item.get("url") for item in (web_research.get("results") or [])[:6]])
        parsed, meta = llm.chat_json(
            "topic_summary_" + hashlib.sha256(summary_cache_basis.encode("utf-8")).hexdigest()[:12],
            system,
            user,
            {"module": "demo.realtime.topic_summary", "query_sha12": hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]},
            max_tokens=3200,
        )
        return {
            "prior_issues": list(parsed.get("prior_issues") or fallback["prior_issues"]),
            "research_plan": list(parsed.get("research_plan") or fallback["research_plan"]),
            "reading_route": list(parsed.get("reading_route") or fallback["reading_route"]),
            "network_research_experience": list(parsed.get("network_research_experience") or fallback["network_research_experience"]),
            "web_reputation": list(parsed.get("web_reputation") or fallback["web_reputation"]),
            "caution_points": list(parsed.get("caution_points") or fallback["caution_points"]),
            "web_research_digest": parsed.get("web_research_digest") or fallback["web_research_digest"],
        }, meta
    except Exception as exc:
        return fallback | {"summary_exception": type(exc).__name__}, {"cached": True, "usage": {"total_tokens": 0}, "fallback": str(exc)[:160]}


def run_topic_research_query(query: str, limit: int = 8, timeout_s: float = DEFAULT_TIMEOUT_S, use_runtime_cache: bool = True) -> dict[str, Any]:
    started = time.perf_counter()
    query = " ".join((query or "").split())
    if not query:
        return unavailable("缺少 q 参数；未运行主题调研。", enabled=realtime_enabled())
    if not realtime_enabled():
        return unavailable()
    try:
        raw_dir = Path("reports/m100/raw/realtime_llm")
        llm = LLMClient(raw_dir, max_tokens=2048)
        precheck = _precheck(llm, use_runtime_cache)
        precheck_tokens = _usage_tokens({"usage": precheck.get("usage") or {}})
        precheck_calls = 0 if precheck.get("cached") else 1
        plan, plan_meta = _topic_query_plan(llm, query, precheck)
        queries = _dedupe(list(plan.get("english_queries") or []) + _fallback_topic_queries(query), limit=6)
        rows, used_queries = _paper_rows_from_openalex(queries, limit=limit)
        web_research = web_research_for_topic(query, queries, max_results=8)
        summary, summary_meta = _topic_summary(llm, query, rows, web_research, precheck)
        elapsed = time.perf_counter() - started
        llm_calls = precheck_calls + _llm_call_count(plan_meta) + _llm_call_count(summary_meta)
        tokens = precheck_tokens + _usage_tokens(plan_meta) + _usage_tokens(summary_meta)
        if not rows:
            return unavailable(
                "OpenAlex 未返回可展示论文；未编造推荐。",
                enabled=True,
                elapsed_s=elapsed,
                llm_calls=llm_calls,
                tokens=tokens,
            ) | {"topic_research": {"intent": plan.get("intent"), "searched_queries": used_queries, "results": []}}
        return {
            "schema_version": "m100.realtime_response.v1",
            "mode": "topic_research_optional",
            "enabled": True,
            "status": "ok",
            "notice": "主题调研结果来自实时 OpenAlex 元数据与 LLM 归纳，非 verified 承重；论文题名/作者/DOI 带来源，问题与路线需人工核验。",
            "query": query,
            "decomposition": {"subqueries": queries, "criteria": list(plan.get("criteria") or [])},
            "results": rows,
            "cost": {"llm_calls": llm_calls, "tokens": tokens, "latency_s": elapsed},
            "source": {"corpus": "OpenAlex live metadata", "ranker": "topic_research_openalex"},
            "topic_research": {
                "intent": plan.get("intent"),
                "searched_queries": used_queries,
                "recommended_papers": rows,
                "prior_issues": summary.get("prior_issues") or [],
                "reading_route": summary.get("reading_route") or [],
                "research_plan": summary.get("research_plan") or [],
                "network_research_experience": summary.get("network_research_experience") or [],
                "web_reputation": summary.get("web_reputation") or [],
                "caution_points": summary.get("caution_points") or [],
                "web_research": web_research,
                "web_research_digest": summary.get("web_research_digest") or {},
                "deepseek_api_note": {
                    "role": "生成检索意图，并基于真实网页/论文证据做归纳",
                    "base_url": "https://api.deepseek.com",
                    "limitation": "DeepSeek 不直接充当搜索引擎；HTTP 搜索/抓取由工具执行，DeepSeek 只基于返回证据总结。",
                },
                "limitations": [
                    "实时结果会随 OpenAlex 更新变化；不是 frozen verified 评测结果。",
                    "前人问题和路线为基于题名/摘要的调研草稿，必须回到论文原文人工核验。",
                    "若需要承重证据，应进一步下载原文并做 span 级证据链校验。",
                ],
            },
            "cache": {
                "precheck_cached": bool(precheck.get("cached")),
                "topic_query_plan_cached": bool(plan_meta.get("cached")),
                "topic_summary_cached": bool(summary_meta.get("cached")),
            },
            "budget": {"timeout_s": timeout_s, "elapsed_s": elapsed, "exceeded": elapsed > timeout_s, "completed_results_not_discarded": True},
        }
    except Exception as exc:
        return unavailable(
            f"主题调研不可用：{type(exc).__name__}；未编造结果。",
            enabled=realtime_enabled(),
            elapsed_s=time.perf_counter() - started,
        ) | {"exception": str(exc)[:300]}


def run_realtime_query(query: str, limit: int = 10, timeout_s: float = DEFAULT_TIMEOUT_S, use_runtime_cache: bool = True) -> dict[str, Any]:
    started = time.perf_counter()
    query = " ".join((query or "").split())
    if not query:
        return unavailable("缺少 q 参数；未运行实时检索。")
    if not realtime_enabled():
        return unavailable()
    if _needs_topic_research_path(query):
        return run_topic_research_query(query, limit=min(max(limit, 6), 10), timeout_s=timeout_s, use_runtime_cache=use_runtime_cache)
    try:
        raw_dir = Path("reports/m100/raw/realtime_llm")
        llm = LLMClient(raw_dir, max_tokens=2048)
        precheck = _precheck(llm, use_runtime_cache)
        precheck_usage = precheck.get("usage") or {}
        precheck_tokens = int(precheck_usage.get("total_tokens") or 0) if isinstance(precheck_usage, dict) else 0
        precheck_calls = 0 if precheck.get("cached") else 1
        if not precheck.get("valid"):
            return unavailable(
                "LLM precheck failed；实时不可用，未编造结果。",
                enabled=True,
                elapsed_s=time.perf_counter() - started,
                llm_calls=precheck_calls,
                tokens=precheck_tokens,
            ) | {"precheck": precheck}
        decomposer = QueryDecomposer(llm)
        qid = "realtime_" + hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
        decomp = decomposer.decompose(qid, query)
        runtime, runtime_cache_reused = _runtime(use_runtime_cache=use_runtime_cache)
        repo = runtime.repo
        corpus = runtime.corpus
        corpus_ids = runtime.corpus_ids
        bm25 = runtime.bm25
        dense = runtime.dense
        bm25_scores = bm25.bm25_scores(query)
        dense_scores = dense.scores(query)
        subqueries = list(decomp.subqueries)[:4] or [query]
        sub_bm25 = _max_or_zero([bm25.bm25_scores(q) for q in subqueries], len(corpus_ids))
        sub_dense = _max_or_zero([row for row in dense.batch_scores(subqueries)], len(corpus_ids))
        pool_ids = _pool_from_scores([bm25_scores, dense_scores, sub_bm25, sub_dense], corpus_ids, top_k=80)
        pool_indices = [repo.id_to_index[cid] for cid in pool_ids]
        pre_features = build_feature_matrix(pool_indices, bm25_scores, dense_scores, sub_bm25, sub_dense, {})
        pre_cfg = FusionV2Config(weights={"bm25": 0.1, "dense_v2": 0.4, "sub_bm25": 0.15, "sub_dense_v2": 0.15, "cross_encoder": 0.0}, final_k=80)
        pre_ranked = rank_with_features(pool_indices, corpus_ids, pre_features, pre_cfg)
        cross_ids = [r.corpusid for r in pre_ranked[:20]]
        cross_scores_by_id = runtime.cross.score(qid, query, cross_ids, corpus, repo.id_to_index)
        cross_scores_by_index = {repo.id_to_index[cid]: score for cid, score in cross_scores_by_id.items() if cid in repo.id_to_index}
        features = build_feature_matrix(pool_indices, bm25_scores, dense_scores, sub_bm25, sub_dense, cross_scores_by_index)
        cfg = FusionV2Config(weights={"bm25": 0.1, "dense_v2": 0.4, "sub_bm25": 0.15, "sub_dense_v2": 0.15, "cross_encoder": 0.2}, final_k=limit)
        ranked = rank_with_features(pool_indices, corpus_ids, features, cfg)
        rows = []
        for rank, item in enumerate(ranked[:limit], start=1):
            doc = repo.get(item.corpusid)
            rows.append(
                {
                    "rank": rank,
                    "corpusid": item.corpusid,
                    "score": item.score,
                    "title": "" if doc is None else doc.title,
                    "abstract_preview": "" if doc is None else doc.abstract[:320],
                    "reason": item.reason,
                    "authors_year": {"status": "需人工核验", "resolution_hint": "realtime connector not run in M100 smoke"},
                    "source_or_doi": {"status": "需人工核验", "resolution_hint": "realtime connector not run in M100 smoke"},
                }
            )
        usage = decomp.meta.get("usage") or {}
        decomp_tokens = int(usage.get("total_tokens") or 0) if isinstance(usage, dict) else 0
        decomp_calls = 0 if decomp.meta.get("cached") else 1
        tokens = precheck_tokens + decomp_tokens
        llm_calls = precheck_calls + decomp_calls
        elapsed = time.perf_counter() - started
        budget_exceeded = elapsed > timeout_s
        return {
            "schema_version": "m100.realtime_response.v1",
            "mode": "realtime_optional",
            "enabled": True,
            "status": "ok",
            "notice": "实时结果非 verified 承重；用于演示新查询能力，成本和延时需单独披露。" + (" 本次超过展示预算但已完成真实排序，未丢弃已算结果。" if budget_exceeded else ""),
            "query": query,
            "decomposition": {"subqueries": list(decomp.subqueries), "criteria": list(decomp.criteria)},
            "results": rows,
            "cost": {"llm_calls": llm_calls, "tokens": tokens, "latency_s": elapsed},
            "source": {"corpus": "LitSearch corpus_clean", "ranker": "A-v2-compatible realtime path"},
            "cache": {"runtime_reused": runtime_cache_reused, "precheck_cached": bool(precheck.get("cached")), "decomposition_cached": bool(decomp.meta.get("cached"))},
            "budget": {"timeout_s": timeout_s, "elapsed_s": elapsed, "exceeded": budget_exceeded, "completed_results_not_discarded": True},
        }
    except Exception as exc:
        return unavailable(
            f"实时不可用：{type(exc).__name__}；未编造结果。",
            enabled=realtime_enabled(),
            elapsed_s=time.perf_counter() - started,
        ) | {"exception": str(exc)[:300]}
