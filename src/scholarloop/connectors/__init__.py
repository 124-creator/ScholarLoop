"""Academic metadata connectors used by ScholarLoop.

The public snapshot keeps optional connectors import-safe: install optional
packages such as `arxiv` only when that connector is used.
"""

from .base import FieldProvenance, TitleMatch, WorkMetadata, title_match
from .openalex import OpenAlexConnector
from .crossref import CrossrefConnector
from .semantic_scholar import SemanticScholarConnector

try:  # optional dependency
    from .arxiv import ArxivConnector
except Exception:  # pragma: no cover - optional connector may be unavailable
    ArxivConnector = None

__all__ = [
    "FieldProvenance",
    "TitleMatch",
    "WorkMetadata",
    "title_match",
    "OpenAlexConnector",
    "CrossrefConnector",
    "SemanticScholarConnector",
    "ArxivConnector",
]
