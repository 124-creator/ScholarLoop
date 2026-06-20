from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .cache import CacheEntry, ResponseCache


USER_AGENT = "ScholarLoop-M050/0.1 (mailto:15517837680@163.com; academic metadata connector)"
TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class FieldProvenance:
    source: str
    external_id: str
    fetched_at: str
    license: str
    cache_path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "external_id": self.external_id,
            "fetched_at": self.fetched_at,
            "license": self.license,
            "cache_path": self.cache_path,
        }


@dataclass(frozen=True)
class WorkMetadata:
    source: str
    external_id: str
    title: str
    authors: tuple[str, ...]
    year: int | None
    venue: str
    doi: str
    oa_status: str
    citation_count: int | None
    license: str
    fetched_at: str
    cache_path: str
    raw: dict[str, Any]
    title_score: float = 0.0
    title_token_jaccard: float = 0.0

    @property
    def provenance(self) -> FieldProvenance:
        return FieldProvenance(self.source, self.external_id, self.fetched_at, self.license, self.cache_path)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "external_id": self.external_id,
            "title": self.title,
            "authors": list(self.authors),
            "year": self.year,
            "venue": self.venue,
            "doi": self.doi,
            "oa_status": self.oa_status,
            "citation_count": self.citation_count,
            "license": self.license,
            "fetched_at": self.fetched_at,
            "cache_path": self.cache_path,
            "title_score": self.title_score,
            "title_token_jaccard": self.title_token_jaccard,
        }


@dataclass(frozen=True)
class TitleMatch:
    query_title: str
    candidate_title: str
    normalized_score: float
    token_jaccard: float
    strong: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_title": self.query_title,
            "candidate_title": self.candidate_title,
            "normalized_score": self.normalized_score,
            "token_jaccard": self.token_jaccard,
            "strong": self.strong,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_title(text: str) -> str:
    return " ".join(TOKEN_RE.findall((text or "").lower()))


def title_match(query_title: str, candidate_title: str, threshold: float = 0.94, token_threshold: float = 0.80) -> TitleMatch:
    q_norm = normalize_title(query_title)
    c_norm = normalize_title(candidate_title)
    score = SequenceMatcher(None, q_norm, c_norm).ratio() if q_norm and c_norm else 0.0
    q_tokens = set(q_norm.split())
    c_tokens = set(c_norm.split())
    jaccard = len(q_tokens & c_tokens) / len(q_tokens | c_tokens) if q_tokens and c_tokens else 0.0
    strong = bool(q_norm and c_norm and (q_norm == c_norm or (score >= threshold and jaccard >= token_threshold)))
    return TitleMatch(query_title, candidate_title, float(score), float(jaccard), strong)


class RateLimiter:
    def __init__(self, min_interval_s: float = 0.25) -> None:
        self.min_interval_s = min_interval_s
        self._last_by_source: dict[str, float] = {}

    def wait(self, source: str) -> None:
        last = self._last_by_source.get(source)
        now = time.monotonic()
        if last is not None:
            delta = now - last
            if delta < self.min_interval_s:
                time.sleep(self.min_interval_s - delta)
        self._last_by_source[source] = time.monotonic()


def load_optional_secret_env(names: tuple[str, ...]) -> dict[str, str]:
    """Read optional API env vars from environment or local secrets without echoing values."""
    found = {name: os.environ.get(name, "") for name in names if os.environ.get(name)}
    root = Path(__file__).resolve().parents[3]
    for filename in ("academic.env.local", "llm.env.local"):
        p = root / "secrets" / filename
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in names and value and key not in found:
                os.environ[key] = value
                found[key] = value
    return found


def public_headers(headers: Any) -> dict[str, str]:
    allowed = {
        "content-type",
        "x-rate-limit-limit",
        "x-rate-limit-interval",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-credits-used",
        "x-ratelimit-reset",
        "x-concurrency-limit",
        "retry-after",
    }
    out: dict[str, str] = {}
    for key, value in dict(headers).items():
        low = key.lower()
        if low in allowed:
            out[key] = str(value)
    return out


class AcademicHttpClient:
    def __init__(
        self,
        cache: ResponseCache | None = None,
        *,
        offline: bool = False,
        timeout_s: float = 30.0,
        retries: int = 2,
        min_interval_s: float = 0.25,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.cache = cache or ResponseCache()
        self.offline = offline
        self.timeout_s = timeout_s
        self.retries = retries
        self.user_agent = user_agent
        self.limiter = RateLimiter(min_interval_s)

    def get_json(
        self,
        source: str,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        headers: dict[str, str] | None = None,
        force_live: bool = False,
    ) -> CacheEntry:
        path = self.cache.path_for(source, "GET", url, params)
        if path.exists() and not force_live:
            return self.cache.read_path(path)
        if self.offline:
            raise RuntimeError(f"Offline cache miss for {source}: {url}")
        all_headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        all_headers.update(headers or {})
        request_params = {k: v for k, v in (params or {}).items() if v is not None}
        query = urllib.parse.urlencode(request_params, doseq=True)
        request_url = url + ("?" + query if query else "")
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self.limiter.wait(source)
            try:
                req = urllib.request.Request(request_url, headers=all_headers, method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    raw = resp.read()
                    body = json.loads(raw.decode("utf-8"))
                    return self.cache.write(
                        path,
                        source=source,
                        method="GET",
                        url=url,
                        params=params,
                        fetched_at=utc_now_iso(),
                        status_code=int(resp.status),
                        headers=public_headers(resp.headers),
                        body_json=body,
                    )
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.retries:
                    raise RuntimeError(f"{source} HTTP {exc.code}; response not cached") from exc
                time.sleep(min(2.0 ** attempt, 8.0))
            except Exception as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise RuntimeError(f"{source} request failed: {type(exc).__name__}") from exc
                time.sleep(min(2.0 ** attempt, 8.0))
        raise RuntimeError(f"{source} request failed: {last_error}")


def clean_doi(doi: str | None) -> str:
    if not doi:
        return ""
    value = str(doi).strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    value = value.removeprefix("doi:").strip()
    return value.lower()


def format_authors_year(record: WorkMetadata, max_authors: int = 6) -> str:
    authors = list(record.authors)
    if not authors and record.year is None:
        return ""
    if len(authors) > max_authors:
        names = ", ".join(authors[:max_authors]) + ", et al."
    else:
        names = ", ".join(authors)
    if record.year is not None:
        return f"{names} ({record.year})" if names else str(record.year)
    return names


def format_source_or_doi(record: WorkMetadata) -> str:
    parts: list[str] = []
    if record.doi:
        parts.append(f"DOI: {record.doi}")
    if record.venue:
        parts.append(f"Source: {record.venue}")
    if record.oa_status:
        parts.append(f"OA: {record.oa_status}")
    if record.citation_count is not None:
        parts.append(f"Citations: {record.citation_count}")
    return "; ".join(parts)
