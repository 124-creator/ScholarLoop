from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .base import CorpusDocument, QueryRecord
from scholarloop.utils import tokenize


class LitSearchCorpus:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self.root = Path(root)
        self.corpus_dir = self.root / "spike" / "raw" / "datasets" / "litsearch" / "corpus_clean"
        self.query_dir = self.root / "spike" / "raw" / "datasets" / "hf" / "query"
        self._corpus: pd.DataFrame | None = None
        self._queries: list[QueryRecord] | None = None
        self._id_to_index: dict[int, int] | None = None

    def load_corpus(self) -> pd.DataFrame:
        if self._corpus is not None:
            return self._corpus
        files = sorted(self.corpus_dir.glob("full-*-of-00006.parquet"))
        if len(files) != 6:
            raise RuntimeError(f"LitSearch corpus_clean requires 6 shards; found {len(files)} under {self.corpus_dir}")
        frames = [pd.read_parquet(p, columns=["corpusid", "title", "abstract"]) for p in files]
        df = pd.concat(frames, ignore_index=True)
        df["corpusid"] = df["corpusid"].astype(int)
        df["title"] = df["title"].fillna("")
        df["abstract"] = df["abstract"].fillna("")
        df["text"] = (df["title"] + "\n" + df["abstract"]).str.strip()
        self._corpus = df
        self._id_to_index = {int(cid): i for i, cid in enumerate(df["corpusid"].to_numpy(dtype=np.int64))}
        return df

    def load_queries(self) -> list[QueryRecord]:
        if self._queries is not None:
            return self._queries
        files = sorted(self.query_dir.glob("*.parquet"))
        if not files:
            raise RuntimeError(f"No LitSearch query parquet files under {self.query_dir}")
        df = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
        records: list[QueryRecord] = []
        for i, row in df.reset_index(drop=True).iterrows():
            gold = tuple(int(x) for x in list(row["corpusids"]))
            records.append(QueryRecord(
                query_id=f"litsearch_{i:03d}", query=str(row["query"]), gold=gold,
                query_set=str(row.get("query_set", "")), specificity=int(row.get("specificity", 0)), quality=int(row.get("quality", 0)),
            ))
        self._queries = records
        return records

    def validate_gold(self) -> None:
        corpus = self.load_corpus()
        id_set = set(int(x) for x in corpus["corpusid"].to_numpy(dtype=np.int64))
        missing = sorted({cid for q in self.load_queries() for cid in q.gold} - id_set)
        if missing:
            raise RuntimeError(f"Gold corpusids missing from corpus_clean: {missing[:20]}")

    @property
    def corpus_ids(self) -> np.ndarray:
        return self.load_corpus()["corpusid"].to_numpy(dtype=np.int64)

    @property
    def id_to_index(self) -> dict[int, int]:
        self.load_corpus()
        assert self._id_to_index is not None
        return self._id_to_index

    def get(self, corpusid: int) -> CorpusDocument | None:
        idx = self.id_to_index.get(int(corpusid))
        if idx is None:
            return None
        row = self.load_corpus().iloc[idx]
        return CorpusDocument(corpusid=int(row["corpusid"]), title=str(row["title"]), abstract=str(row["abstract"]))

    def iter_documents(self) -> Iterable[CorpusDocument]:
        for row in self.load_corpus().itertuples(index=False):
            yield CorpusDocument(corpusid=int(row.corpusid), title=str(row.title), abstract=str(row.abstract))

    def search(self, query: str, top_k: int = 100) -> list[int]:
        # Simple repository fallback search used only for interface smoke tests.
        qset = set(tokenize(query))
        scored = []
        for i, row in enumerate(self.load_corpus().itertuples(index=False)):
            toks = set(tokenize(row.text))
            score = len(qset & toks)
            if score:
                scored.append((score, int(row.corpusid)))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [cid for _, cid in scored[:top_k]]
