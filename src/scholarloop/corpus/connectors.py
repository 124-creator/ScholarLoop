from __future__ import annotations

from .base import CorpusDocument


class OnlineConnector:
    """Interface seam for future online academic sources; not implemented in M010."""
    source_name: str = "online"

    def resolve(self, identifier: str) -> CorpusDocument | None:
        raise NotImplementedError("Online connectors are intentionally not implemented in module 010.")


class OpenAlexConnector(OnlineConnector):
    source_name = "openalex"


class SemanticScholarConnector(OnlineConnector):
    source_name = "semantic_scholar"


class CrossrefConnector(OnlineConnector):
    source_name = "crossref"


class ArxivConnector(OnlineConnector):
    source_name = "arxiv"
