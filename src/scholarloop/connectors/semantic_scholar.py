from __future__ import annotations

from typing import Any

from .base import AcademicHttpClient, WorkMetadata, clean_doi, load_optional_secret_env, title_match
from .cache import CacheEntry


SEMANTIC_SCHOLAR_LICENSE = "Semantic Scholar Academic Graph API License; attribution required; rate limits apply"


class SemanticScholarConnector:
    source_name = "semantic_scholar"
    search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    paper_url = "https://api.semanticscholar.org/graph/v1/paper"

    def __init__(self, client: AcademicHttpClient | None = None) -> None:
        self.client = client or AcademicHttpClient(min_interval_s=1.1)
        self.env = load_optional_secret_env(("SEMANTIC_SCHOLAR_API_KEY", "S2_API_KEY"))

    def _headers(self) -> dict[str, str]:
        key = self.env.get("SEMANTIC_SCHOLAR_API_KEY") or self.env.get("S2_API_KEY")
        return {"x-api-key": key} if key else {}

    def search_title(self, title: str, *, max_results: int = 3, force_live: bool = False) -> list[WorkMetadata]:
        fields = "title,authors,year,venue,externalIds,citationCount,openAccessPdf"
        entry = self.client.get_json(
            self.source_name,
            self.search_url,
            {"query": title, "limit": max_results, "fields": fields},
            headers=self._headers(),
            force_live=force_live,
        )
        records = [self.parse_paper(p, entry) for p in (entry.body_json.get("data") or [])]
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

    def by_doi(self, doi: str, *, force_live: bool = False) -> WorkMetadata | None:
        cleaned = clean_doi(doi)
        if not cleaned:
            return None
        fields = "title,authors,year,venue,externalIds,citationCount,openAccessPdf"
        url = f"{self.paper_url}/DOI:{cleaned}"
        entry = self.client.get_json(self.source_name, url, {"fields": fields}, headers=self._headers(), force_live=force_live)
        return self.parse_paper(entry.body_json, entry) if entry.body_json else None

    @staticmethod
    def parse_paper(paper: dict[str, Any], entry: CacheEntry) -> WorkMetadata:
        external = paper.get("externalIds") or {}
        authors = tuple(str(a.get("name") or "").strip() for a in (paper.get("authors") or []) if str(a.get("name") or "").strip())
        oa = "open_access_pdf" if paper.get("openAccessPdf") else ""
        return WorkMetadata(
            source="semantic_scholar",
            external_id=str(paper.get("paperId") or external.get("CorpusId") or ""),
            title=str(paper.get("title") or ""),
            authors=authors,
            year=int(paper["year"]) if paper.get("year") is not None else None,
            venue=str(paper.get("venue") or ""),
            doi=clean_doi(external.get("DOI")),
            oa_status=oa,
            citation_count=int(paper["citationCount"]) if paper.get("citationCount") is not None else None,
            license=SEMANTIC_SCHOLAR_LICENSE,
            fetched_at=entry.fetched_at,
            cache_path=str(entry.path),
            raw=paper,
        )
