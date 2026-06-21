from __future__ import annotations

from typing import Any

from scholarloop.evidence.status import (
    STATUS_INSUFFICIENT,
    STATUS_SUPPORTED,
    criterion_tokens,
    find_sentence_for_terms,
    make_unsupported_field,
)


def build_matrix_cell(paper: dict[str, Any], criterion: str) -> dict[str, Any]:
    terms = criterion_tokens(criterion)
    found = find_sentence_for_terms(paper, terms)
    if not found:
        return {
            'criterion': criterion,
            'addresses': False,
            'snippet': '',
            'status': STATUS_INSUFFICIENT,
            'source_field': None,
            'char_span': None,
            'resolution_hint': 'no_grounded_criterion_span_found',
        }
    source_field, span, exact = found
    return {
        'criterion': criterion,
        'addresses': True,
        'snippet': exact,
        'status': STATUS_SUPPORTED,
        'source_field': source_field,
        'char_span': span,
    }


def build_evidence_matrix(query_id: str, criteria: list[str], papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, paper in enumerate(papers, start=1):
        cells = [build_matrix_cell(paper, c) for c in criteria]
        rows.append({
            'rank': rank,
            'corpusid': int(paper['corpusid']),
            'title': str(paper.get('title') or ''),
            'cells': cells,
        })
    return rows


def validate_matrix_shape(matrix: list[dict[str, Any]], expected_rows: int, expected_cols: int) -> bool:
    if len(matrix) != expected_rows:
        return False
    return all(len(row.get('cells', [])) == expected_cols for row in matrix)
