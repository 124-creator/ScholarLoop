from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class CorpusDocument:
    corpusid: int
    title: str
    abstract: str

    @property
    def text(self) -> str:
        return (self.title + "\n" + self.abstract).strip()


@dataclass(frozen=True)
class QueryRecord:
    query_id: str
    query: str
    gold: tuple[int, ...]
    query_set: str = ""
    specificity: int | None = None
    quality: int | None = None


class CorpusRepository(Protocol):
    def get(self, corpusid: int) -> CorpusDocument | None: ...
    def iter_documents(self) -> Iterable[CorpusDocument]: ...
    def search(self, query: str, top_k: int = 100) -> list[int]: ...
