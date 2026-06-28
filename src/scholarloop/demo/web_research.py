from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


USER_AGENT = "ScholarLoop-Demo-WebResearch/0.1 (academic demo; no secrets)"
SEARCH_URL = "https://lite.duckduckgo.com/lite/"
MAX_PAGE_CHARS = 240_000
SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
CARBON_RE = re.compile(r"碳价|碳价格|碳市场|碳交易|碳定价|carbon|emissions?\s+trading|ETS", re.I)
FORUM_DOMAINS = (
    "reddit.com", "news.ycombinator.com", "ycombinator.com", "stackexchange.com",
    "stackoverflow.com", "quora.com", "zhihu.com", "v2ex.com", "segmentfault.com",
    "csdn.net", "groups.google.com", "discuss.", "forum.", "community.",
)


@dataclass(frozen=True)
class WebSearchItem:
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo_lite"
    is_forum: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet, "source": self.source, "is_forum": self.is_forum}


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = TAG_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip()


def _decode_duck_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(html.unescape(url))
    qs = urllib.parse.parse_qs(parsed.query)
    if "uddg" in qs and qs["uddg"]:
        return qs["uddg"][0]
    return urllib.parse.urlunparse(parsed)


def _is_forum_url(url: str) -> bool:
    """按域名判断来源是否为论坛/社区，用于在前端分组展示，不改变抓取本身。"""

    try:
        host = urllib.parse.urlparse(url or "").netloc.lower()
    except Exception:
        return False
    return any(domain in host for domain in FORUM_DOMAINS)


def _cache_path(query: str) -> Path:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    root = Path("reports/m100/raw/web_research")
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{digest}.json"


def search_web(query: str, *, max_results: int = 8, force_live: bool = False) -> list[WebSearchItem]:
    """Search public webpages and parse title/url/snippet from DuckDuckGo Lite.

    This is not a verified evidence path. It is an optional demo research aid:
    if the search page changes or blocks access, callers must show an explicit
    empty state instead of inventing web opinions.
    """

    query = " ".join((query or "").split())
    if not query:
        return []
    cache = _cache_path("search:" + query)
    if cache.exists() and not force_live:
        data = json.loads(cache.read_text(encoding="utf-8"))
        cached_items = [WebSearchItem(**item) for item in data.get("items", [])]
        if cached_items:
            return cached_items

    url = SEARCH_URL + "?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", "replace")

    rows = re.split(r"<tr>\s*<td valign=\"top\">", body)
    items: list[WebSearchItem] = []
    for row in rows:
        link = re.search(r"<a\b(?=[^>]*class=['\"]result-link['\"])(?=[^>]*href=['\"]([^'\"]+)['\"])[^>]*>(.*?)</a>", row, re.I | re.S)
        if not link:
            continue
        title = _clean_text(link.group(2))
        href = _decode_duck_url(link.group(1))
        snippet_match = re.search(r"<td class=['\"]result-snippet['\"]>(.*?)</td>", row, re.I | re.S)
        snippet = _clean_text(snippet_match.group(1)) if snippet_match else ""
        if title and href:
            items.append(WebSearchItem(title=title, url=href, snippet=snippet, is_forum=_is_forum_url(href)))
        if len(items) >= max_results:
            break

    cache.write_text(
        json.dumps(
            {"query": query, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": [item.to_dict() for item in items]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return items


def authoritative_seed_sources(topic: str) -> list[WebSearchItem]:
    if not CARBON_RE.search(topic or ""):
        return []
    return [
        WebSearchItem(
            title="State and Trends of Carbon Pricing - World Bank Group",
            url="https://www.worldbank.org/en/publication/state-and-trends-of-carbon-pricing",
            snippet="World Bank publication page tracking carbon pricing instruments, policy trends, coverage, revenues, and implementation developments.",
            source="authoritative_seed",
        ),
        WebSearchItem(
            title="ETS Allowance Prices - ICAP Carbon Action",
            url="https://icapcarbonaction.com/en/ets-prices",
            snippet="ICAP page for emissions trading system allowance prices; useful for distinguishing market prices, policy schemes, and time-varying ETS data.",
            source="authoritative_seed",
        ),
        WebSearchItem(
            title="Carbon Markets 2025: Review and Outlook - Climate Focus",
            url="https://climatefocus.com/publications/carbon-market-2025-review-and-outlook/",
            snippet="Climate Focus review/outlook page discussing carbon-market developments, risks, and policy/market context.",
            source="authoritative_seed",
        ),
        WebSearchItem(
            title="Carbon Market Forecasts - MSCI Carbon Markets",
            url="https://www.msci.com/data-and-analytics/carbon-markets/carbon-market-forecasts",
            snippet="MSCI page describing carbon market forecast data, price/demand/supply scenarios, and market modelling considerations.",
            source="authoritative_seed",
        ),
    ]


def fetch_page_excerpt(url: str, *, max_chars: int = 900) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"url": url, "status": "invalid_url", "excerpt": ""}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            content_type = resp.headers.get("content-type", "")
            raw = resp.read(MAX_PAGE_CHARS)
        if "html" not in content_type.lower() and "text" not in content_type.lower():
            return {"url": url, "status": "unsupported_content_type", "content_type": content_type, "excerpt": ""}
        text = raw.decode("utf-8", "replace")
        text = SCRIPT_STYLE_RE.sub(" ", text)
        text = _clean_text(text)
        return {"url": url, "status": "ok", "content_type": content_type, "excerpt": text[:max_chars]}
    except Exception as exc:
        return {"url": url, "status": "fetch_failed", "error_type": type(exc).__name__, "excerpt": ""}


def web_research_for_topic(topic: str, queries: list[str], *, max_results: int = 8) -> dict[str, Any]:
    topic = " ".join((topic or "").split())
    general_queries: list[str] = []
    if topic:
        general_queries.append(f"{topic} current discussion risks policy market review")
    general_queries.extend([f"{query} review outlook risks policy market" for query in queries[:2] if query])
    forum_query = f"{topic} 讨论 经验 reddit hacker news stackexchange zhihu" if topic else ""

    seen_query: set[str] = set()
    seen_url: set[str] = set()
    all_items: list[WebSearchItem] = []
    used_queries: list[str] = []
    errors: list[dict[str, str]] = []

    def _run(query: str, cap: int) -> None:
        if not query:
            return
        key = query.lower()
        if key in seen_query:
            return
        seen_query.add(key)
        try:
            items = search_web(query, max_results=cap)
            used_queries.append(query)
            for item in items:
                if item.url in seen_url:
                    continue
                seen_url.add(item.url)
                all_items.append(item)
        except Exception as exc:
            errors.append({"query": query, "error_type": type(exc).__name__, "error": str(exc)[:200]})

    # 先抓社区/论坛，给论坛结果预留名额；再抓通用主题检索补满。
    _run(forum_query, max(3, max_results // 2))
    for query in general_queries:
        if len(all_items) >= max_results + 4:
            break
        _run(query, max_results)

    if not all_items:
        all_items.extend(authoritative_seed_sources(topic)[:max_results])

    # 论坛/社区来源优先排序，但不丢弃普通来源。
    forum_items = [item for item in all_items if getattr(item, "is_forum", False)]
    other_items = [item for item in all_items if not getattr(item, "is_forum", False)]
    ordered = (forum_items + other_items)[:max_results]

    page_excerpts = [fetch_page_excerpt(item.url) for item in ordered[:4]]

    return {
        "status": "ok" if ordered else "unavailable",
        "search_provider": "duckduckgo_lite",
        "queries": used_queries,
        "results": [item.to_dict() for item in ordered],
        "page_excerpts": page_excerpts,
        "forum_count": len(forum_items),
        "errors": errors,
        "notice": "Web research is live and non-verified; search snippets/pages may change and must be cited/checked before use.",
    }
