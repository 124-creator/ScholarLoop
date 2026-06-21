from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .base import AcademicHttpClient, WorkMetadata, clean_doi, load_optional_secret_env, title_match
from .cache import CacheEntry


CROSSREF_LICENSE = "Crossref REST API metadata; docs site CC BY 4.0; record licenses may vary"


class CrossrefConnector:
    source_name = "crossref"
    base_url = "https://api.crossref.org/works"

    def __init__(self, client: AcademicHttpClient | None = None) -> None:
        self.client = client or AcademicHttpClient(min_interval_s=0.35)
        self.env = load_optional_secret_env(("CROSSREF_MAILTO",))

    def _params(self, params: dict[str, Any]) -> dict[str, Any]:
        out = dict(params)
        mailto = self.env.get("CROSSREF_MAILTO") or "no-public-email@example.com"
        out["mailto"] = mailto
        return out

    def by_doi(self, doi: str, *, force_live: bool = False) -> WorkMetadata | None:
        cleaned = clean_doi(doi)
        if not cleaned:
            return None
        url = f"{self.base_url}/{quote(cleaned, safe='')}"
        entry = self.client.get_json(self.source_name, url, self._params({}), force_live=force_live)
        msg = (entry.body_json or {}).get("message") or {}
        return self.parse_message(msg, entry) if msg else None

    def search_title(self, title: str, *, max_results: int = 3, force_live: bool = False) -> list[WorkMetadata]:
        params = self._params({"query.title": title, "rows": max_results})
        entry = self.client.get_json(self.source_name, self.base_url, params, force_live=force_live)
        items = ((entry.body_json or {}).get("message") or {}).get("items") or []
        records = [self.parse_message(item, entry) for item in items]
        records = [r for r in records if r is not None]
        scored = []
        for record in records:
            match = title_match(title, record.title)
            scored.append(
                WorkMetadata(
                    source=record.source,
                    external_id=record.external_id,
                    title=record.title,
                    authors=record.authors,
                    year=record.year,
                    venue=record.venue,
                    doi=record.doi,
                    oa_status=record.oa_status,
                    citation_count=record.citation_count,
                    license=record.license,
                    fetched_at=record.fetched_at,
                    cache_path=record.cache_path,
                    raw=record.raw,
                    title_score=match.normalized_score,
                    title_token_jaccard=match.token_jaccard,
                )
            )
        scored.sort(key=lambda r: (-r.title_score, -r.title_token_jaccard, r.external_id))
        return scored

    @staticmethod
    def _date_year(msg: dict[str, Any]) -> int | None:
        for key in ("published-print", "published-online", "published", "issued", "created"):
            date_parts = ((msg.get(key) or {}).get("date-parts") or [])
            if date_parts and date_parts[0]:
                try:
                    return int(date_parts[0][0])
                except Exception:
                    continue
        return None

    @staticmethod
    def parse_message(msg: dict[str, Any], entry: CacheEntry) -> WorkMetadata:
        title_list = msg.get("title") or []
        venue_list = msg.get("container-title") or []
        authors = []
        for author in msg.get("author") or []:
            given = str(author.get("given") or "").strip()
            family = str(author.get("family") or "").strip()
            name = " ".join(x for x in [given, family] if x)
            if name:
                authors.append(name)
        return WorkMetadata(
            source="crossref",
            external_id=f"https://doi.org/{clean_doi(msg.get('DOI'))}" if msg.get("DOI") else str(msg.get("URL") or ""),
            title=str(title_list[0] if title_list else ""),
            authors=tuple(authors),
            year=CrossrefConnector._date_year(msg),
            venue=str(venue_list[0] if venue_list else ""),
            doi=clean_doi(msg.get("DOI")),
            oa_status="",
            citation_count=int(msg["is-referenced-by-count"]) if msg.get("is-referenced-by-count") is not None else None,
            license=CROSSREF_LICENSE,
            fetched_at=entry.fetched_at,
            cache_path=str(entry.path),
            raw=msg,
        )
