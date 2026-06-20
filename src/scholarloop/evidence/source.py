from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import pandas as pd

import scholarloop.config  # noqa: F401 - import triggers credential self-loading for downstream LLM use


@dataclass(frozen=True)
class AQueryOutput:
    query_id: str
    query: str
    criteria: list[str]
    ranked_corpusids: list[int]
    pool_size: int


class EvidenceSource:
    """Read-only adapter over M010 outputs and the LitSearch offline corpus."""

    def __init__(self, root: Path = Path('.')) -> None:
        self.root = Path(root)
        self._corpus: pd.DataFrame | None = None
        self._paper_by_id: dict[int, dict[str, Any]] | None = None
        self._query_by_id: dict[str, str] | None = None

    @property
    def corpus_dir(self) -> Path:
        return self.root / 'spike' / 'raw' / 'datasets' / 'litsearch' / 'corpus_clean'

    @property
    def query_dir(self) -> Path:
        return self.root / 'spike' / 'raw' / 'datasets' / 'hf' / 'query'

    def load_corpus(self) -> pd.DataFrame:
        if self._corpus is None:
            paths = sorted(self.corpus_dir.glob('*.parquet'))
            if not paths:
                raise FileNotFoundError(f'No LitSearch parquet files under {self.corpus_dir}')
            frames = [pd.read_parquet(p) for p in paths]
            df = pd.concat(frames, ignore_index=True)
            required = {'corpusid', 'title', 'abstract', 'citations', 'full_paper'}
            missing = required - set(df.columns)
            if missing:
                raise ValueError(f'LitSearch corpus missing columns: {sorted(missing)}')
            self._corpus = df
            self._paper_by_id = {int(row.corpusid): row._asdict() for row in df.itertuples(index=False)}
        return self._corpus

    def load_queries(self) -> dict[str, str]:
        if self._query_by_id is None:
            paths = sorted(self.query_dir.glob('*.parquet'))
            if not paths:
                raise FileNotFoundError(f'No LitSearch query parquet files under {self.query_dir}')
            df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
            self._query_by_id = {f'litsearch_{i:03d}': str(row['query']) for i, row in df.reset_index(drop=True).iterrows()}
        return self._query_by_id

    def get_paper(self, corpusid: int) -> dict[str, Any]:
        self.load_corpus()
        assert self._paper_by_id is not None
        if int(corpusid) not in self._paper_by_id:
            raise KeyError(f'corpusid not found in LitSearch corpus: {corpusid}')
        row = dict(self._paper_by_id[int(corpusid)])
        row['corpusid'] = int(row['corpusid'])
        for key in ['title', 'abstract', 'full_paper']:
            row[key] = '' if row.get(key) is None else str(row.get(key))
        if row.get('citations') is None:
            row['citations'] = []
        return row

    def get_query_text(self, query_id: str) -> str:
        return self.load_queries().get(query_id, query_id)


def load_a_outputs(results_path: Path = Path('reports/m010/results.json'), source: EvidenceSource | None = None) -> list[AQueryOutput]:
    """Load M010 per-query ScholarLoop-A outputs without modifying them.

    M010 stores A decomposition subqueries under `decomposition`; M020 uses those
    strings as criteria columns when a separate criteria field is absent.
    """

    source = source or EvidenceSource()
    data = json.loads(Path(results_path).read_text(encoding='utf-8'))
    outputs: list[AQueryOutput] = []
    for item in data.get('per_query', []):
        criteria = item.get('criteria') or item.get('decomposition') or []
        if isinstance(criteria, str):
            criteria = [criteria]
        ranked = ((item.get('scholarloop_a') or {}).get('ranked_top20') or [])
        outputs.append(AQueryOutput(
            query_id=str(item['query_id']),
            query=source.get_query_text(str(item['query_id'])),
            criteria=[str(c) for c in criteria if str(c).strip()],
            ranked_corpusids=[int(x) for x in ranked],
            pool_size=int(item.get('pool_size') or 0),
        ))
    return outputs
