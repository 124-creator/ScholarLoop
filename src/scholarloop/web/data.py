from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import json

ROOT = Path('.')
M010_RESULTS = ROOT / 'reports' / 'm010' / 'results.json'
M020_EVIDENCE_DIR = ROOT / 'reports' / 'm020' / 'evidence'
M020_VERIFICATION = ROOT / 'reports' / 'm020' / 'verification.json'
LITSEARCH_CORPUS_DIR = ROOT / 'spike' / 'raw' / 'datasets' / 'litsearch' / 'corpus_clean'

OFFLINE_LLM_CALLS_PER_REQUEST = 0
REALTIME_ENABLED_DEFAULT = False
OFFICIAL_MISSING_FIELDS = ('authors_year', 'source_or_doi')
REQUIRED_FIELD_KEYS = {
    'title', 'authors_year', 'source_or_doi', 'recommendation_reason',
    'supported_research_question', 'method', 'data_or_scenario',
    'main_conclusion', 'limitations', 'relevance_strength'
}
DEMO_TAGS = {
    'litsearch_000': {'demo_label': 'AI 科研演示：大语言模型压缩 / 知识蒸馏', 'demo_kind': 'ai_research'},
    'litsearch_002': {'demo_label': 'AI 科研演示：幻觉检测 / 神经生成', 'demo_kind': 'ai_research'},
}


@dataclass(frozen=True)
class QuerySummary:
    query_id: str
    query: str
    criteria_count: int
    top_n: int
    demo_label: str | None = None
    demo_kind: str | None = None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def load_m010_results() -> dict[str, Any]:
    return _read_json(M010_RESULTS)


@lru_cache(maxsize=1)
def m010_by_query() -> dict[str, dict[str, Any]]:
    return {str(item['query_id']): item for item in load_m010_results().get('per_query', [])}


@lru_cache(maxsize=1)
def m010_reason_examples() -> dict[str, dict[int, dict[str, Any]]]:
    out: dict[str, dict[int, dict[str, Any]]] = {}
    for ex in load_m010_results().get('reason_examples', []) or []:
        qid = str(ex.get('query_id'))
        out[qid] = {int(row['corpusid']): row for row in ex.get('top_results', []) if 'corpusid' in row}
    return out


@lru_cache(maxsize=None)
def load_evidence_doc(qid: str) -> dict[str, Any]:
    path = M020_EVIDENCE_DIR / f'{qid}.json'
    if not path.exists():
        raise KeyError(f'No M020 evidence doc for query_id={qid}')
    return _read_json(path)


@lru_cache(maxsize=1)
def evidence_query_ids() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in M020_EVIDENCE_DIR.glob('*.json')))


@lru_cache(maxsize=1)
def corpus_meta_by_id() -> dict[int, dict[str, Any]]:
    import pandas as pd

    rows: dict[int, dict[str, Any]] = {}
    for path in sorted(LITSEARCH_CORPUS_DIR.glob('*.parquet')):
        df = pd.read_parquet(path, columns=['corpusid', 'title', 'abstract', 'full_paper', 'citations'])
        for row in df.itertuples(index=False):
            citations = getattr(row, 'citations')
            if citations is None:
                citations = []
            try:
                citation_count = len(list(citations))
            except Exception:
                citation_count = 0
            rows[int(row.corpusid)] = {
                'corpusid': int(row.corpusid),
                'title': '' if row.title is None else str(row.title),
                'has_abstract': bool(row.abstract),
                'has_full_paper': bool(row.full_paper),
                'citation_count_in_offline_field': citation_count,
            }
    return rows


def list_queries() -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for qid in evidence_query_ids():
        doc = load_evidence_doc(qid)
        demo = DEMO_TAGS.get(qid, {})
        summaries.append(QuerySummary(
            query_id=qid,
            query=str(doc.get('query') or ''),
            criteria_count=len(doc.get('criteria') or []),
            top_n=int(doc.get('top_n') or len(doc.get('cards') or [])),
            demo_label=demo.get('demo_label'),
            demo_kind=demo.get('demo_kind'),
        ).__dict__)
    return summaries


def get_paper_meta(corpusid: int) -> dict[str, Any]:
    meta = corpus_meta_by_id().get(int(corpusid))
    if not meta:
        raise KeyError(f'corpusid not found in LitSearch corpus: {corpusid}')
    return dict(meta)


def _ranking_rows(qid: str, evidence_doc: dict[str, Any], m010_query: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = ((m010_query.get('scholarloop_a') or {}).get('ranked_top20') or [])
    reason_map = m010_reason_examples().get(qid, {})
    evidence_ids = {int(card['corpusid']) for card in evidence_doc.get('cards', [])}
    rows = []
    for rank, cid in enumerate(ranked, start=1):
        cid = int(cid)
        reason_row = reason_map.get(cid, {})
        rows.append({
            'rank': rank,
            'corpusid': cid,
            'has_evidence_card': cid in evidence_ids,
            # score/reason are exposed only when M010 report already contains them.
            'score': reason_row.get('score'),
            'reason': reason_row.get('reason'),
        })
    return rows


def assert_official_missing_fields(evidence_doc: dict[str, Any]) -> None:
    for card in evidence_doc.get('cards', []):
        fields = card.get('fields') or {}
        if set(fields) != REQUIRED_FIELD_KEYS:
            raise ValueError(f"Unexpected field keys for corpusid={card.get('corpusid')}")
        for name in OFFICIAL_MISSING_FIELDS:
            field = fields.get(name) or {}
            if field.get('status') == '已有证据支持':
                raise ValueError(f'{name} must never be supported in offline web view')
            if not field.get('resolution_hint'):
                raise ValueError(f'{name} missing resolution_hint')


def get_query_doc(qid: str) -> dict[str, Any]:
    evidence_doc = load_evidence_doc(qid)
    assert_official_missing_fields(evidence_doc)
    m010_query = m010_by_query().get(qid)
    if not m010_query:
        raise KeyError(f'No M010 per_query for query_id={qid}')
    verification = _read_json(M020_VERIFICATION) if M020_VERIFICATION.exists() else {}
    view = {
        'schema_version': 'm030.query_view.v1',
        'query_id': qid,
        'query': evidence_doc.get('query'),
        'decomposition': m010_query.get('decomposition') or evidence_doc.get('criteria') or [],
        'criteria': evidence_doc.get('criteria') or [],
        'ranking': _ranking_rows(qid, evidence_doc, m010_query),
        'evidence': evidence_doc,
        'm010_metrics': {
            'P@10': (m010_query.get('scholarloop_a') or {}).get('P@10'),
            'R@20': (m010_query.get('scholarloop_a') or {}).get('R@20'),
            'F1': (m010_query.get('scholarloop_a') or {}).get('F1'),
        },
        'm020_grounding': {
            'fabrication_rate': verification.get('fabrication_rate'),
            'matrix_fabrication_rate': verification.get('matrix_fabrication_rate'),
            'official_missing_field_compliance_rate': verification.get('official_missing_field_compliance_rate'),
        },
        'render_contract': {
            'upstream_m010': str(M010_RESULTS),
            'upstream_m020': str(M020_EVIDENCE_DIR / f'{qid}.json'),
            'offline': True,
            'realtime_enabled': REALTIME_ENABLED_DEFAULT,
            'llm_calls_per_request': OFFLINE_LLM_CALLS_PER_REQUEST,
            'field_values_source': 'reports/m020/evidence JSON copied without rewriting',
            'official_missing_policy': 'authors_year/source_or_doi show status plus resolution_hint only; no invented authors/year/DOI',
        },
        'demo': DEMO_TAGS.get(qid),
    }
    return view


def source_evidence_doc(qid: str) -> dict[str, Any]:
    return load_evidence_doc(qid)
