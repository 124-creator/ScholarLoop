from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from .base import AcademicHttpClient, WorkMetadata, clean_doi, title_match
from .cache import CacheEntry


ARXIV_LICENSE = "arXiv API Terms of Use; acknowledge arXiv data usage; record-level licenses vary"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivConnector:
    source_name = "arxiv"
    base_url = "https://export.arxiv.org/api/query"

    def __init__(self, client: AcademicHttpClient | None = None) -> None:
        self.client = client or AcademicHttpClient(min_interval_s=3.1)

    def search_title(self, title: str, *, max_results: int = 3, force_live: bool = False) -> list[WorkMetadata]:
        # arXiv returns Atom XML, so use the JSON cache envelope with raw XML string.
        query = f'ti:"{title}"'
        params = {"search_query": query, "start": 0, "max_results": max_results}
        entry = self._get_atom(params, force_live=force_live)
        records = [self.parse_entry(e, entry) for e in self._entries(entry.body_json["xml"])]
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

    def _get_atom(self, params: dict[str, Any], *, force_live: bool = False) -> CacheEntry:
        # Reuse AcademicHttpClient caching semantics by fetching as text via urlopen-compatible XML envelope.
        # The arXiv API does not return JSON; the cache body stores {"xml": "..."}.
        import urllib.request
        from .base import public_headers, utc_now_iso

        path = self.client.cache.path_for(self.source_name, "GET", self.base_url, params)
        if path.exists() and not force_live:
            return self.client.cache.read_path(path)
        if self.client.offline:
            raise RuntimeError("Offline cache miss for arXiv")
        query = urllib.parse.urlencode(params)
        url = self.base_url + "?" + query
        self.client.limiter.wait(self.source_name)
        req = urllib.request.Request(url, headers={"User-Agent": self.client.user_agent, "Accept": "application/atom+xml"})
        with urllib.request.urlopen(req, timeout=self.client.timeout_s) as resp:
            xml = resp.read().decode("utf-8")
            return self.client.cache.write(
                path,
                source=self.source_name,
                method="GET",
                url=self.base_url,
                params=params,
                fetched_at=utc_now_iso(),
                status_code=int(resp.status),
                headers=public_headers(resp.headers),
                body_json={"xml": xml},
            )

    @staticmethod
    def _entries(xml: str) -> list[ET.Element]:
        root = ET.fromstring(xml)
        return root.findall(f"{ATOM}entry")

    @staticmethod
    def parse_entry(entry_el: ET.Element, cache_entry: CacheEntry) -> WorkMetadata:
        title = " ".join((entry_el.findtext(f"{ATOM}title") or "").split())
        authors = tuple(a.findtext(f"{ATOM}name") or "" for a in entry_el.findall(f"{ATOM}author"))
        authors = tuple(a.strip() for a in authors if a.strip())
        published = entry_el.findtext(f"{ATOM}published") or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        doi = entry_el.findtext(f"{ARXIV_NS}doi") or ""
        return WorkMetadata(
            source="arxiv",
            external_id=str(entry_el.findtext(f"{ATOM}id") or ""),
            title=title,
            authors=authors,
            year=year,
            venue="arXiv",
            doi=clean_doi(doi),
            oa_status="green",
            citation_count=None,
            license=ARXIV_LICENSE,
            fetched_at=cache_entry.fetched_at,
            cache_path=str(cache_entry.path),
            raw={"title": title, "published": published, "doi": doi},
        )
