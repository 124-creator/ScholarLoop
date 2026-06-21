from __future__ import annotations

from pathlib import Path
from typing import Any

from scholarloop.utils import write_json


def validate_query_evidence(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {'schema_version', 'query_id', 'query', 'criteria', 'top_n', 'cards', 'matrix'}
    missing = required - set(doc)
    if missing:
        errors.append(f'missing top-level keys: {sorted(missing)}')
    criteria = doc.get('criteria') or []
    matrix = doc.get('matrix') or []
    cards = doc.get('cards') or []
    if len(matrix) != len(cards):
        errors.append('matrix row count != card count')
    for row in matrix:
        if len(row.get('cells', [])) != len(criteria):
            errors.append(f"row {row.get('corpusid')} cell count != criteria count")
    return errors


def write_query_evidence(report_dir: Path, doc: dict[str, Any]) -> Path:
    errors = validate_query_evidence(doc)
    if errors:
        raise ValueError('; '.join(errors))
    out = report_dir / 'evidence' / f"{doc['query_id']}.json"
    write_json(out, doc)
    return out


def _field_status_counts(cards: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in cards:
        for field in (card.get('fields') or {}).values():
            status = field.get('status')
            counts[status] = counts.get(status, 0) + 1
    return counts


def render_markdown_report(path: Path, docs: list[dict[str, Any]], verification: dict[str, Any]) -> None:
    lines: list[str] = []
    lines += [
        '# M020 B-lite evidence matrix report',
        '',
        f"- Status: **{verification.get('status')}**",
        f"- Query docs rendered: {len(docs)}",
        f"- Top-N per query: {verification.get('config', {}).get('top_n')}",
        f"- fabrication_rate: `{verification.get('fabrication_rate')}`",
        f"- official missing-field compliance: `{verification.get('official_missing_field_compliance_rate')}`",
        '',
        '## Status distribution',
        '',
    ]
    for status, count in sorted((verification.get('status_counts') or {}).items()):
        lines.append(f'- {status}: {count}')
    lines += ['', '## Demonstration examples']
    for doc in docs[:3]:
        lines += ['', f"### {doc['query_id']}", '', f"Query: {doc['query']}", '', '| rank | corpusid | title | ' + ' | '.join(doc['criteria']) + ' |']
        lines.append('|---:|---:|---|' + '|'.join(['---'] * len(doc['criteria'])) + '|')
        for row in doc['matrix']:
            cells = []
            for cell in row['cells']:
                if cell['addresses']:
                    snippet = cell['snippet'].replace('|', '/').replace('\n', ' ')[:120]
                    cells.append(f"✅ {snippet}")
                else:
                    cells.append('—')
            title = row.get('title', '').replace('|', '/')[:80]
            lines.append(f"| {row['rank']} | {row['corpusid']} | {title} | " + ' | '.join(cells) + ' |')
        lines += ['', '#### First card fields']
        if doc.get('cards'):
            card = doc['cards'][0]
            for name, field in card['fields'].items():
                val = (field.get('value') or field.get('resolution_hint') or '').replace('\n', ' ')[:140]
                lines.append(f"- **{name}** [{field.get('status')}]: {val}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
