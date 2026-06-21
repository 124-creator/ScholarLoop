from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import time
from pathlib import Path
from typing import Any

from scholarloop.llm import LLMClient
from scholarloop.utils import percentile, write_json
from scholarloop.evidence.card import FIELD_NAMES, build_evidence_card
from scholarloop.evidence.graph import build_internal_citation_graph
from scholarloop.evidence.matrix import build_evidence_matrix
from scholarloop.evidence.render import render_markdown_report, write_query_evidence
from scholarloop.evidence.source import EvidenceSource, load_a_outputs
from scholarloop.evidence.status import (
    ALL_STATUSES,
    STATUS_DISPUTED,
    STATUS_SUPPORTED,
    ONLINE_CONNECTOR_HINT,
    text_fields,
)

SECRET_RE = re.compile(r'(?:sk|ark)-[A-Za-z0-9_\-]{12,}')


def _usage_tokens(meta: dict[str, Any]) -> int:
    return int(meta.get('total_tokens') or 0)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def evidence_hash(report_dir: Path) -> str:
    h = hashlib.sha256()
    for path in sorted((report_dir / 'evidence').glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        h.update(json.dumps(data, ensure_ascii=False, sort_keys=True).encode('utf-8'))
    return h.hexdigest()


def scan_for_secrets(paths: list[Path]) -> dict[str, Any]:
    hits: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if not path.is_file() or 'secrets' in path.parts:
                continue
            try:
                text = path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            if SECRET_RE.search(text):
                hits.append(str(path))
    return {'scanned': [str(p) for p in paths], 'excluded': ['secrets'], 'secret_like_hits': len(hits), 'hit_files': hits}


def _verify_span(source_text: str, span: Any, value: str) -> bool:
    if not isinstance(span, list) or len(span) != 2:
        return False
    start, end = int(span[0]), int(span[1])
    return 0 <= start <= end <= len(source_text) and source_text[start:end] == value


def verify_doc(doc: dict[str, Any], source: EvidenceSource) -> dict[str, Any]:
    supported_total = 0
    supported_fail = 0
    disputed_total = 0
    disputed_fail = 0
    status_counts = {s: 0 for s in ALL_STATUSES}
    official_total = 0
    official_ok = 0
    completeness_ok = True
    matrix_supported_total = 0
    matrix_supported_fail = 0

    for card in doc.get('cards', []):
        paper = source.get_paper(int(card['corpusid']))
        fields = card.get('fields') or {}
        if set(fields) != set(FIELD_NAMES):
            completeness_ok = False
        for name in FIELD_NAMES:
            field = fields.get(name) or {}
            status = field.get('status')
            status_counts[status] = status_counts.get(status, 0) + 1
            if name in {'authors_year', 'source_or_doi'}:
                official_total += 1
                if status != STATUS_SUPPORTED and field.get('resolution_hint') == ONLINE_CONNECTOR_HINT:
                    official_ok += 1
            if status in {STATUS_SUPPORTED, STATUS_DISPUTED}:
                src_field = field.get('source_field')
                ok = src_field in text_fields(paper) and _verify_span(text_fields(paper)[src_field], field.get('char_span'), field.get('value') or '')
                if status == STATUS_SUPPORTED:
                    supported_total += 1
                    supported_fail += 0 if ok else 1
                else:
                    disputed_total += 1
                    disputed_fail += 0 if ok else 1

    paper_by_id = {int(c['corpusid']): source.get_paper(int(c['corpusid'])) for c in doc.get('cards', [])}
    for row in doc.get('matrix', []):
        paper = paper_by_id.get(int(row['corpusid']))
        if not paper:
            matrix_supported_fail += 1
            continue
        for cell in row.get('cells', []):
            if cell.get('status') == STATUS_SUPPORTED and cell.get('addresses'):
                matrix_supported_total += 1
                src_field = cell.get('source_field')
                ok = src_field in text_fields(paper) and _verify_span(text_fields(paper)[src_field], cell.get('char_span'), cell.get('snippet') or '')
                matrix_supported_fail += 0 if ok else 1

    return {
        'supported_total': supported_total,
        'supported_fail': supported_fail,
        'disputed_total': disputed_total,
        'disputed_fail': disputed_fail,
        'matrix_supported_total': matrix_supported_total,
        'matrix_supported_fail': matrix_supported_fail,
        'official_missing_total': official_total,
        'official_missing_ok': official_ok,
        'field_completeness_ok': completeness_ok,
        'status_counts': status_counts,
    }


def build_dev_outputs(report_dir: Path, limit: int, top_n: int, llm: LLMClient) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = EvidenceSource()
    outputs = load_a_outputs(source=source)[:limit]
    docs: list[dict[str, Any]] = []
    timings: list[float] = []
    tokens = 0
    api_calls = 0
    for out in outputs:
        q_start = time.perf_counter()
        papers = [source.get_paper(cid) for cid in out.ranked_corpusids[:top_n]]
        cards = []
        for paper in papers:
            card = build_evidence_card(out.query_id, out.query, out.criteria, paper, llm=llm, report_dir=report_dir)
            cards.append(card)
            tokens += _usage_tokens(card.get('llm_meta') or {})
            api_calls += 1
        matrix = build_evidence_matrix(out.query_id, out.criteria, papers)
        doc = {
            'schema_version': 'm020.query_evidence.v1',
            'query_id': out.query_id,
            'query': out.query,
            'criteria': out.criteria,
            'top_n': top_n,
            'source': {'m010_results': 'reports/m010/results.json', 'ranker': 'scholarloop_a', 'upstream_read_only': True},
            'cards': cards,
            'matrix': matrix,
            'citation_graph': build_internal_citation_graph(papers),
        }
        write_query_evidence(report_dir, doc)
        docs.append(doc)
        timings.append(time.perf_counter() - q_start)
    return docs, {'tokens': tokens, 'api_calls': api_calls, 'timings': timings}


def aggregate_verification(report_dir: Path, limit: int, top_n: int, run1_hash: str, run2_hash: str, upstream_before: str, upstream_after: str, efficiency: dict[str, Any]) -> dict[str, Any]:
    source = EvidenceSource()
    totals = {
        'supported_total': 0, 'supported_fail': 0, 'disputed_total': 0, 'disputed_fail': 0,
        'matrix_supported_total': 0, 'matrix_supported_fail': 0, 'official_missing_total': 0,
        'official_missing_ok': 0,
    }
    status_counts = {s: 0 for s in ALL_STATUSES}
    completeness_ok = True
    docs = []
    for path in sorted((report_dir / 'evidence').glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        docs.append(doc)
        v = verify_doc(doc, source)
        for key in totals:
            totals[key] += int(v[key])
        for status, count in v['status_counts'].items():
            status_counts[status] = status_counts.get(status, 0) + int(count)
        completeness_ok = completeness_ok and bool(v['field_completeness_ok'])

    fabrication_rate = totals['supported_fail'] / max(1, totals['supported_total'])
    matrix_fabrication_rate = totals['matrix_supported_fail'] / max(1, totals['matrix_supported_total'])
    official_rate = totals['official_missing_ok'] / max(1, totals['official_missing_total'])
    secret_scan = scan_for_secrets([Path('src'), Path('tests'), Path('reports/m020'), Path('docs')])
    status = 'PASS' if fabrication_rate == 0 and matrix_fabrication_rate == 0 and official_rate == 1.0 and completeness_ok and run1_hash == run2_hash and upstream_before == upstream_after and secret_scan['secret_like_hits'] == 0 else 'BLOCKED'
    verification = {
        'schema_version': 'm020.verification.v1',
        'status': status,
        'config': {'limit': limit, 'top_n': top_n, 'dev_queries': len(docs), 'demo_examples': ['litsearch_000 as AI research demo', 'litsearch_001', 'litsearch_002']},
        'fabrication_rate': fabrication_rate,
        'supported_field_total': totals['supported_total'],
        'supported_field_failures': totals['supported_fail'],
        'disputed_grounded_total': totals['disputed_total'],
        'disputed_grounding_failures': totals['disputed_fail'],
        'matrix_fabrication_rate': matrix_fabrication_rate,
        'matrix_supported_total': totals['matrix_supported_total'],
        'matrix_supported_failures': totals['matrix_supported_fail'],
        'official_missing_field_compliance_rate': official_rate,
        'official_missing_ok': totals['official_missing_ok'],
        'official_missing_total': totals['official_missing_total'],
        'field_completeness_ok': completeness_ok,
        'status_counts': status_counts,
        'reproducible': run1_hash == run2_hash,
        'run1_hash': run1_hash,
        'run2_hash': run2_hash,
        'upstream_m010_unchanged': upstream_before == upstream_after,
        'upstream_m010_sha256': upstream_after,
        'efficiency': efficiency,
        'secret_scan': secret_scan,
    }
    write_json(report_dir / 'verification.json', verification)
    write_json(report_dir / 'secret_scan.json', secret_scan)
    render_markdown_report(report_dir / 'evidence-matrix-report.md', docs, verification)
    grounding_lines = [
        '# M020 grounding report',
        '',
        f"- Status: **{status}**",
        f"- fabrication_rate: `{fabrication_rate}`",
        f"- matrix_fabrication_rate: `{matrix_fabrication_rate}`",
        f"- official_missing_field_compliance_rate: `{official_rate}`",
        f"- reproducible: `{run1_hash == run2_hash}`",
        f"- upstream_m010_unchanged: `{upstream_before == upstream_after}`",
        f"- secret_like_hits: `{secret_scan['secret_like_hits']}`",
        '',
        '## Notes',
        '- `fabrication_rate` only counts fields explicitly marked 已有证据支持; every such value must match source_text[char_span].',
        '- 作者/年份/来源/DOI are not present in the offline LitSearch corpus and are forced to non-support with online connector resolution hints.',
    ]
    (report_dir / 'grounding-report.md').write_text('\n'.join(grounding_lines) + '\n', encoding='utf-8')
    if status != 'PASS':
        (report_dir / '020-stop-grounding.md').write_text('\n'.join(grounding_lines) + '\n', encoding='utf-8')
    return verification


def run(report_dir: Path, limit: int = 30, top_n: int = 3) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'raw' / 'llm').mkdir(parents=True, exist_ok=True)
    upstream = Path('reports/m010/results.json')
    upstream_before = sha256_file(upstream)
    llm = LLMClient(report_dir / 'raw' / 'llm')
    precheck = llm.precheck()
    write_json(report_dir / 'llm_precheck.json', precheck)
    if not precheck.get('valid'):
        stop = {'status': 'BLOCKED', 'reason': 'LLM precheck failed after scholarloop.config import', 'present': precheck.get('present'), 'exception_type': precheck.get('exception_type')}
        write_json(report_dir / '020-stop-llm-precheck.json', stop)
        return stop

    start = time.perf_counter()
    docs, eff = build_dev_outputs(report_dir, limit, top_n, llm)
    run1_hash = evidence_hash(report_dir)
    # Run again with cached raw responses; output JSON must remain byte-equivalent after canonical hashing.
    docs2, _ = build_dev_outputs(report_dir, limit, top_n, llm)
    run2_hash = evidence_hash(report_dir)
    timings = eff['timings']
    efficiency = {
        'total_wall_s': time.perf_counter() - start,
        'first_run_query_seconds_sum': float(sum(timings)),
        'p50_query_s': percentile(timings, 50),
        'p95_query_s': percentile(timings, 95),
        'total_tokens': int(eff['tokens']),
        'api_calls': int(eff['api_calls']),
        'api_calls_per_query': float(eff['api_calls'] / max(1, limit)),
    }
    upstream_after = sha256_file(upstream)
    verification = aggregate_verification(report_dir, limit, top_n, run1_hash, run2_hash, upstream_before, upstream_after, efficiency)
    return verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-dir', default='reports/m020')
    parser.add_argument('--limit', type=int, default=30)
    parser.add_argument('--top-n', type=int, default=3)
    args = parser.parse_args(argv)
    out = run(Path(args.report_dir), args.limit, args.top_n)
    print(json.dumps({'status': out.get('status'), 'fabrication_rate': out.get('fabrication_rate'), 'report_dir': args.report_dir}, ensure_ascii=False, indent=2))
    return 0 if out.get('status') == 'PASS' else 5


if __name__ == '__main__':
    raise SystemExit(main())
