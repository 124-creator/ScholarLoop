from __future__ import annotations

from typing import Any

from .base import AcademicHttpClient, WorkMetadata, clean_doi, load_optional_secret_env, title_match
from .cache import CacheEntry


OPENALEX_LICENSE = "CC0; https://help.openalex.org/hc/en-us/articles/24397762024087-Pricing"


class OpenAlexConnector:
    source_name = "openalex"
    base_url = "https://api.openalex.org/works"

    def __init__(self, client: AcademicHttpClient | None = None) -> None:
        self.client = client or AcademicHttpClient()
        self.env = load_optional_secret_env(("OPENALEX_API_KEY",))

    def _params(self, params: dict[str, Any]) -> dict[str, Any]:
        out = dict(params)
        if self.env.get("OPENALEX_API_KEY"):
            out["api_key"] = self.env["OPENALEX_API_KEY"]
        return out

    def search_title(self, title: str, *, max_results: int = 5, force_live: bool = False) -> list[WorkMetadata]:
        # OpenAlex treats ?/* as wildcard syntax and may return HTTP 400.
        # Academic titles frequently contain punctuation, so sanitize only the
        # query string sent to the API while enforcing the strong local title
        # match against the original title before accepting any value.
        query_text = title.replace("?", " ").replace("*", " ")
        params = self._params(
            {
                "search": query_text,
                "per-page": max_results,
                "select": "id,doi,title,display_name,authorships,publication_year,primary_location,open_access,cited_by_count",
            }
        )
        entry = self.client.get_json(self.source_name, self.base_url, params, force_live=force_live)
        records = [self.parse_work(item, entry) for item in (entry.body_json.get("results") or [])]
        scored: list[WorkMetadata] = []
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

    def by_doi(self, doi: str, *, force_live: bool = False) -> WorkMetadata | None:
        cleaned = clean_doi(doi)
        if not cleaned:
            return None
        params = self._params(
            {
                "filter": f"doi:{cleaned}",
                "per-page": 1,
                "select": "id,doi,title,display_name,authorships,publication_year,primary_location,open_access,cited_by_count",
            }
        )
        entry = self.client.get_json(self.source_name, self.base_url, params, force_live=force_live)
        results = entry.body_json.get("results") or []
        return self.parse_work(results[0], entry) if results else None

    @staticmethod
    def parse_work(work: dict[str, Any], entry: CacheEntry) -> WorkMetadata:
        authors = []
        for authorship in work.get("authorships") or []:
            author = authorship.get("author") or {}
            name = str(author.get("display_name") or "").strip()
            if name:
                authors.append(name)
        primary_location = work.get("primary_location") or {}
        source = primary_location.get("source") or {}
        venue = (
            source.get("display_name")
            or (work.get("host_venue") or {}).get("display_name")
            or primary_location.get("landing_page_url")
            or ""
        )
        open_access = work.get("open_access") or {}
        title = work.get("title") or work.get("display_name") or ""
        return WorkMetadata(
            source="openalex",
            external_id=str(work.get("id") or ""),
            title=str(title),
            authors=tuple(authors),
            year=int(work["publication_year"]) if work.get("publication_year") is not None else None,
            venue=str(venue or ""),
            doi=clean_doi(work.get("doi")),
            oa_status=str(open_access.get("oa_status") or ""),
            citation_count=int(work["cited_by_count"]) if work.get("cited_by_count") is not None else None,
            license=OPENALEX_LICENSE,
            fetched_at=entry.fetched_at,
            cache_path=str(entry.path),
            raw=work,
        )
