from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from scholarloop.llm import LLMClient
from scholarloop.utils import write_json
from scholarloop.evidence.status import (
    STATUS_INSUFFICIENT,
    STATUS_NEEDS_REVIEW,
    locate_in_paper,
    make_supported_field,
    make_unsupported_field,
    offline_missing_field,
    find_sentence_for_terms,
    criterion_tokens,
    dispute_status_for,
)

FIELD_NAMES = [
    'title',
    'authors_year',
    'source_or_doi',
    'recommendation_reason',
    'supported_research_question',
    'method',
    'data_or_scenario',
    'main_conclusion',
    'limitations',
    'relevance_strength',
]

LLM_FIELD_MAP = {
    'recommendation_reason': ['recommendation_reason_quote', 'recommendation_reason', 'reason'],
    'supported_research_question': ['supported_research_question_quote', 'research_question', 'question'],
    'method': ['method_quote', 'method'],
    'data_or_scenario': ['data_or_scenario_quote', 'data', 'scenario'],
    'main_conclusion': ['main_conclusion_quote', 'conclusion', 'main_conclusion'],
    'limitations': ['limitations_quote', 'limitation', 'limitations'],
    'relevance_strength': ['relevance_strength_quote', 'relevance_quote', 'relevance'],
}

FALLBACK_TERMS = {
    'recommendation_reason': ['propose', 'present', 'introduce', 'study', 'investigate', 'show', 'demonstrate'],
    'supported_research_question': [],
    'method': ['method', 'model', 'approach', 'framework', 'algorithm', 'network', 'learning', 'training'],
    'data_or_scenario': ['data', 'dataset', 'benchmark', 'experiment', 'task', 'corpus', 'simulation'],
    'main_conclusion': ['result', 'show', 'demonstrate', 'outperform', 'improve', 'effective', 'find'],
    'limitations': ['however', 'although', 'but', 'limitation', 'challenge', 'fail', 'not'],
    'relevance_strength': [],
}


def _usage_tokens(meta: dict[str, Any]) -> int:
    usage = meta.get('usage') or {}
    for key in ['total_tokens', 'totalTokenCount', 'total']:
        if usage.get(key) is not None:
            return int(usage[key])
    return 0


def _candidate_texts(parsed: Any, field_name: str) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = []
    if not isinstance(parsed, dict):
        return values
    for key in LLM_FIELD_MAP[field_name]:
        obj = parsed.get(key)
        if obj is None:
            continue
        if isinstance(obj, dict):
            val = obj.get('quote') or obj.get('value') or obj.get('snippet') or obj.get('text')
            conf = obj.get('confidence', 0.65)
        else:
            val = obj
            conf = 0.65
        if isinstance(val, str) and val.strip():
            values.append((val.strip(), float(conf or 0.65)))
    return values


def _field_from_llm_or_fallback(field_name: str, paper: dict[str, Any], parsed: Any, query: str, criteria: list[str]) -> dict[str, Any]:
    for quote, conf in _candidate_texts(parsed, field_name):
        located = locate_in_paper(paper, quote)
        if located:
            source_field, span, exact = located
            status = dispute_status_for(exact) if field_name == 'limitations' else '已有证据支持'
            return make_supported_field(field_name, exact, source_field, span, conf, status=status)

    terms = list(FALLBACK_TERMS.get(field_name, []))
    if field_name in {'recommendation_reason', 'supported_research_question', 'relevance_strength'}:
        terms += criterion_tokens(query) + [t for c in criteria for t in criterion_tokens(c)]
    found = find_sentence_for_terms(paper, terms) if terms else None
    if found:
        source_field, span, exact = found
        status = dispute_status_for(exact) if field_name == 'limitations' else '已有证据支持'
        return make_supported_field(field_name, exact, source_field, span, 0.55, status=status)

    if field_name == 'supported_research_question':
        title = str(paper.get('title') or '').strip()
        if title:
            located = locate_in_paper(paper, title, preferred='title')
            if located:
                source_field, span, exact = located
                return make_supported_field(field_name, exact, source_field, span, 0.5)

    status = STATUS_NEEDS_REVIEW if field_name in {'limitations', 'relevance_strength'} else STATUS_INSUFFICIENT
    hint = 'needs_full_text_or_human_review' if status == STATUS_NEEDS_REVIEW else 'no_grounded_span_found'
    return make_unsupported_field(field_name, status, '', 0.0, hint)


def _llm_extract(llm: LLMClient, query_id: str, corpusid: int, query: str, criteria: list[str], paper: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    abstract = re.sub(r'\s+', ' ', str(paper.get('abstract') or '')).strip()[:3200]
    full = re.sub(r'\s+', ' ', str(paper.get('full_paper') or '')).strip()[:1200]
    title = str(paper.get('title') or '').strip()[:500]
    system = (
        'You extract grounded evidence fields from paper text. Return strict JSON only. '
        'Every value must be an exact quote copied from the provided title/abstract/full_paper. '
        'If no exact quote exists, return an empty string for that field. Do not infer authors, years, venues, DOI, or facts outside the text.'
    )
    user = f"""Query: {query}
Criteria: {criteria}
Paper corpusid: {corpusid}
Title: {title}
Abstract: {abstract}
Full_paper_excerpt: {full}

Return JSON object with these string quote fields, each copied exactly from the supplied text or empty string:
{{
  "recommendation_reason_quote": "...",
  "supported_research_question_quote": "...",
  "method_quote": "...",
  "data_or_scenario_quote": "...",
  "main_conclusion_quote": "...",
  "limitations_quote": "...",
  "relevance_strength_quote": "..."
}}
"""
    return llm.chat_json(f'card_{query_id}_{corpusid}', system, user, {'query_id': query_id, 'corpusid': corpusid, 'arm': 'm020_card'}, max_tokens=1536)


def build_evidence_card(query_id: str, query: str, criteria: list[str], paper: dict[str, Any], llm: LLMClient | None = None, report_dir: Path = Path('reports/m020')) -> dict[str, Any]:
    llm = llm or LLMClient(report_dir / 'raw' / 'llm')
    parsed: Any = {}
    meta: dict[str, Any] = {'total_tokens': 0, 'elapsed_s': 0.0, 'llm_error': None}
    try:
        parsed, llm_meta = _llm_extract(llm, query_id, int(paper['corpusid']), query, criteria, paper)
        meta = {
            'total_tokens': _usage_tokens(llm_meta),
            'elapsed_s': float(llm_meta.get('elapsed_s') or 0.0),
            'raw_path': llm_meta.get('raw_path'),
            'llm_error': None,
        }
    except Exception as exc:  # fallback is conservative: no unsupported value is promoted without span.
        meta = {'total_tokens': 0, 'elapsed_s': 0.0, 'raw_path': None, 'llm_error': type(exc).__name__}

    fields: dict[str, dict[str, Any]] = {}
    title = str(paper.get('title') or '').strip()
    if title:
        located = locate_in_paper(paper, title, preferred='title')
        if located:
            source_field, span, exact = located
            fields['title'] = make_supported_field('title', exact, source_field, span, 1.0)
        else:
            fields['title'] = make_unsupported_field('title', STATUS_INSUFFICIENT, '', 0.0, 'title_not_located')
    else:
        fields['title'] = make_unsupported_field('title', STATUS_INSUFFICIENT, '', 0.0, 'missing_title')

    fields['authors_year'] = offline_missing_field('authors_year')
    fields['source_or_doi'] = offline_missing_field('source_or_doi')

    for name in FIELD_NAMES:
        if name in fields:
            continue
        fields[name] = _field_from_llm_or_fallback(name, paper, parsed, query, criteria)

    card = {
        'schema_version': 'm020.evidence_card.v1',
        'query_id': query_id,
        'corpusid': int(paper['corpusid']),
        'fields': {name: fields[name] for name in FIELD_NAMES},
        'llm_meta': meta,
    }
    return card


def write_card(path: Path, card: dict[str, Any]) -> None:
    write_json(path, card)
