from __future__ import annotations

import re
from typing import Any

STATUS_SUPPORTED = '已有证据支持'
STATUS_INSUFFICIENT = '证据不足'
STATUS_DISPUTED = '存在争议'
STATUS_NEEDS_REVIEW = '需人工核验'
ALL_STATUSES = [STATUS_SUPPORTED, STATUS_INSUFFICIENT, STATUS_DISPUTED, STATUS_NEEDS_REVIEW]

OFFLINE_MISSING_FIELDS = {'authors_year', 'source_or_doi'}
ONLINE_CONNECTOR_HINT = 'online_connector_required_for_author_year_source_doi'

_SENTENCE_RE = re.compile(r'[^.!?。！？\n]{24,500}[.!?。！？]?')
_TOKEN_RE = re.compile(r'[A-Za-z][A-Za-z0-9_-]{3,}')
STOPWORDS = {
    'with', 'from', 'that', 'this', 'these', 'those', 'using', 'based', 'into', 'over',
    'under', 'about', 'paper', 'papers', 'study', 'studies', 'method', 'methods',
    'model', 'models', 'approach', 'approaches', 'query', 'search', 'large', 'language'
}
DISPUTE_TERMS = ('however', 'although', 'but ', 'nevertheless', 'limitation', 'limitations', 'challenge', 'controvers', 'conflict', 'inconsistent')


def text_fields(paper: dict[str, Any]) -> dict[str, str]:
    return {
        'title': str(paper.get('title') or ''),
        'abstract': str(paper.get('abstract') or ''),
        'full_paper': str(paper.get('full_paper') or ''),
    }


def find_span(source: str, snippet: str) -> list[int] | None:
    if not source or not snippet:
        return None
    cleaned = snippet.strip()
    if not cleaned:
        return None
    pos = source.find(cleaned)
    if pos >= 0:
        return [pos, pos + len(cleaned)]
    # Conservative whitespace-normalized search, then map back by scanning windows.
    norm_snip = re.sub(r'\s+', ' ', cleaned)
    if len(norm_snip) < 12:
        return None
    for m in re.finditer(re.escape(norm_snip[:24]), re.sub(r'\s+', ' ', source)):
        _ = m
        break
    return None


def locate_in_paper(paper: dict[str, Any], snippet: str, preferred: str | None = None) -> tuple[str, list[int], str] | None:
    fields = text_fields(paper)
    order = [preferred] if preferred in fields else []
    order += [k for k in ['title', 'abstract', 'full_paper'] if k not in order]
    for field in order:
        span = find_span(fields[field], snippet)
        if span is not None:
            return field, span, fields[field][span[0]:span[1]]
    return None


def make_supported_field(field_name: str, value: str, source_field: str, span: list[int], confidence: float = 0.8, status: str = STATUS_SUPPORTED) -> dict[str, Any]:
    return {
        'field': field_name,
        'value': value,
        'status': status,
        'source_field': source_field,
        'char_span': span,
        'confidence': float(confidence),
    }


def make_unsupported_field(field_name: str, status: str = STATUS_INSUFFICIENT, value: str = '', confidence: float = 0.0, resolution_hint: str | None = None) -> dict[str, Any]:
    out = {
        'field': field_name,
        'value': value,
        'status': status,
        'source_field': None,
        'char_span': None,
        'confidence': float(confidence),
    }
    if resolution_hint:
        out['resolution_hint'] = resolution_hint
    return out


def offline_missing_field(field_name: str) -> dict[str, Any]:
    return make_unsupported_field(field_name, STATUS_NEEDS_REVIEW, '', 0.0, ONLINE_CONNECTOR_HINT)


def sentences(text: str) -> list[str]:
    chunks = [m.group(0).strip() for m in _SENTENCE_RE.finditer(text or '')]
    if chunks:
        return chunks
    text = (text or '').strip()
    return [text[:360]] if text else []


def criterion_tokens(text: str) -> list[str]:
    toks = []
    for t in _TOKEN_RE.findall(text.lower()):
        if t not in STOPWORDS and len(t) >= 4:
            toks.append(t)
    return sorted(set(toks), key=lambda x: (-len(x), x))[:12]


def find_sentence_for_terms(paper: dict[str, Any], terms: list[str], prefer_abstract: bool = True) -> tuple[str, list[int], str] | None:
    order = ['abstract', 'title', 'full_paper'] if prefer_abstract else ['title', 'abstract', 'full_paper']
    fields = text_fields(paper)
    lowered_terms = [t.lower() for t in terms if t]
    for field in order:
        src = fields[field]
        for sent in sentences(src):
            low = sent.lower()
            if any(t in low for t in lowered_terms):
                span = find_span(src, sent)
                if span:
                    return field, span, src[span[0]:span[1]]
    return None


def dispute_status_for(value: str) -> str:
    low = f' {value.lower()} '
    return STATUS_DISPUTED if any(term in low for term in DISPUTE_TERMS) else STATUS_SUPPORTED


def verify_located_value(paper: dict[str, Any], field: dict[str, Any]) -> bool:
    if field.get('status') != STATUS_SUPPORTED and field.get('status') != STATUS_DISPUTED:
        return True
    source_field = field.get('source_field')
    span = field.get('char_span')
    if source_field not in {'title', 'abstract', 'full_paper'} or not isinstance(span, list) or len(span) != 2:
        return False
    src = text_fields(paper)[source_field]
    start, end = int(span[0]), int(span[1])
    if start < 0 or end < start or end > len(src):
        return False
    return src[start:end] == field.get('value')
