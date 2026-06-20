from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from scholarloop.web.app import create_server
from scholarloop.web.data import OFFICIAL_MISSING_FIELDS, get_query_doc, list_queries, source_evidence_doc
from scholarloop.web.render import render_query_page
from scholarloop.utils import write_json

SECRET_RE = re.compile(r'(?:sk|ark)-[A-Za-z0-9_\-]{12,}')


def sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def hash_dir(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    for f in sorted(path.rglob('*')):
        if f.is_file():
            h.update(str(f.relative_to(path)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def scan_for_secrets(paths: list[Path]) -> dict[str, Any]:
    hits: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        for f in base.rglob('*'):
            if not f.is_file() or 'secrets' in f.parts:
                continue
            try:
                text = f.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            if SECRET_RE.search(text):
                hits.append(str(f))
    return {'scanned': [str(p) for p in paths], 'excluded': ['secrets'], 'secret_like_hits': len(hits), 'hit_files': hits}


def fetch_json(base_url: str, path: str) -> tuple[int, dict[str, Any]]:
    with urlopen(base_url + path, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))


def fetch_text(base_url: str, path: str) -> tuple[int, str]:
    with urlopen(base_url + path, timeout=10) as resp:
        return resp.status, resp.read().decode('utf-8')


def assert_view_matches_source(qid: str) -> dict[str, Any]:
    view = get_query_doc(qid)
    source = source_evidence_doc(qid)
    failures: list[str] = []
    if view['evidence']['cards'] != source['cards']:
        failures.append('cards differ from M020 source')
    if view['evidence']['matrix'] != source['matrix']:
        failures.append('matrix differs from M020 source')
    if view['evidence']['criteria'] != source['criteria']:
        failures.append('criteria differ from M020 source')
    for card in view['evidence']['cards']:
        fields = card.get('fields') or {}
        for name in OFFICIAL_MISSING_FIELDS:
            f = fields.get(name) or {}
            if f.get('status') != '需人工核验' or not f.get('resolution_hint'):
                failures.append(f'{qid}/{card.get("corpusid")}/{name} missing review status or hint')
            if f.get('value'):
                failures.append(f'{qid}/{card.get("corpusid")}/{name} has forbidden invented value')
    html = render_query_page(view, list_queries())
    for status in ['已有证据支持', '证据不足', '存在争议', '需人工核验']:
        if status not in html:
            failures.append(f'status badge missing in html: {status}')
    return {'query_id': qid, 'ok': not failures, 'failures': failures, 'html_bytes': len(html.encode('utf-8'))}


def write_demo_manifest(report_dir: Path) -> None:
    demo_dir = report_dir / 'demo'
    demo_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        'schema_version': 'm030.demo_manifest.v1',
        'mode': 'offline_alias_to_grounded_m020_docs',
        'demos': [
            {
                'demo_id': 'ai_research_litsearch_000',
                'query_id': 'litsearch_000',
                'label': 'AI 科研演示：大语言模型压缩 / 知识蒸馏',
                'source_evidence': 'reports/m020/evidence/litsearch_000.json',
                'no_new_fields': True,
            },
            {
                'demo_id': 'ai_research_litsearch_002',
                'query_id': 'litsearch_002',
                'label': 'AI 科研演示：幻觉检测 / 神经生成',
                'source_evidence': 'reports/m020/evidence/litsearch_002.json',
                'no_new_fields': True,
            },
        ],
        'note': 'Carbon-price demo is not fabricated offline; current cross-domain demo uses existing grounded AI research LitSearch evidence.',
    }
    write_json(demo_dir / 'demo_manifest.json', manifest)
    for item in manifest['demos']:
        source = Path(item['source_evidence'])
        if source.exists():
            write_json(demo_dir / f"{item['demo_id']}.json", json.loads(source.read_text(encoding='utf-8')))


def run(report_dir: Path) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    m010_before = sha256_file(Path('reports/m010/results.json'))
    m020_before = hash_dir(Path('reports/m020'))
    write_demo_manifest(report_dir)

    queries = list_queries()
    per_query = [assert_view_matches_source(q['query_id']) for q in queries]
    faithful = all(x['ok'] for x in per_query)

    server = create_server('127.0.0.1', 0)
    host, port = server.server_address
    base = f'http://{host}:{port}'
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    smoke_lines: list[str] = [f'started {base}']
    try:
        health_status, health = fetch_json(base, '/healthz')
        smoke_lines.append(f'GET /healthz -> {health_status} {health}')
        q_status, q_payload = fetch_json(base, '/api/queries')
        smoke_lines.append(f'GET /api/queries -> {q_status} count={q_payload.get("count")}')
        endpoint_ok = health_status == 200 and q_status == 200 and q_payload.get('count') == len(queries)
        all_accessible = True
        api_payload_match = True
        first_html = ''
        second_html = ''
        for i, q in enumerate(queries):
            status, payload = fetch_json(base, f"/api/queries/{q['query_id']}")
            smoke_lines.append(f"GET /api/queries/{q['query_id']} -> {status}")
            all_accessible = all_accessible and status == 200
            source = source_evidence_doc(q['query_id'])
            api_payload_match = api_payload_match and payload.get('evidence', {}).get('cards') == source.get('cards') and payload.get('evidence', {}).get('matrix') == source.get('matrix')
            if i == 0:
                html_status, first_html = fetch_text(base, f"/?qid={q['query_id']}")
                html_status2, second_html = fetch_text(base, f"/?qid={q['query_id']}")
                smoke_lines.append(f"GET /?qid={q['query_id']} -> {html_status}, repeat -> {html_status2}")
                endpoint_ok = endpoint_ok and html_status == 200 and html_status2 == 200
        two_renders_identical = first_html == second_html and bool(first_html)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    (report_dir / 'smoke_console.txt').write_text('\n'.join(smoke_lines) + '\n', encoding='utf-8')

    m010_after = sha256_file(Path('reports/m010/results.json'))
    m020_after = hash_dir(Path('reports/m020'))
    secret_scan = scan_for_secrets([Path('src'), Path('tests'), Path('reports/m030'), Path('docs')])
    status = 'PASS' if endpoint_ok and all_accessible and faithful and api_payload_match and two_renders_identical and health.get('llm_calls_per_request') == 0 and m010_before == m010_after and m020_before == m020_after and secret_scan['secret_like_hits'] == 0 else 'BLOCKED'
    verification = {
        'schema_version': 'm030.web_verification.v1',
        'status': status,
        'W1_single_command_runnable': endpoint_ok and all_accessible,
        'W1_benchmark_queries_accessible': all_accessible,
        'benchmark_query_count': len(queries),
        'W2_faithful_zero_fabrication': faithful and api_payload_match,
        'api_payload_matches_m020_json': api_payload_match,
        'render_field_checks': per_query,
        'official_missing_fields_policy_ok': all(x['ok'] for x in per_query),
        'offline_default': True,
        'realtime_enabled_default': False,
        'llm_calls_per_baseline_request': health.get('llm_calls_per_request'),
        'two_renders_identical': two_renders_identical,
        'status_badges_present': all(status in first_html for status in ['已有证据支持', '证据不足', '存在争议', '需人工核验']),
        'm010_unchanged': m010_before == m010_after,
        'm020_unchanged': m020_before == m020_after,
        'demo_manifest': 'reports/m030/demo/demo_manifest.json',
        'secret_scan': secret_scan,
        'smoke_console': 'reports/m030/smoke_console.txt',
        'single_command': "PYTHONPATH=src python -m scholarloop.web.app --host 127.0.0.1 --port 8765",
    }
    write_json(report_dir / 'web-verification.json', verification)
    write_json(report_dir / 'secret_scan.json', secret_scan)
    if status != 'PASS':
        write_json(report_dir / '030-stop-web.md.json', verification)
    return verification


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-dir', default='reports/m030')
    args = parser.parse_args(argv)
    out = run(Path(args.report_dir))
    print(json.dumps({'status': out['status'], 'W1': out['W1_single_command_runnable'], 'W2': out['W2_faithful_zero_fabrication'], 'queries': out['benchmark_query_count']}, ensure_ascii=False, indent=2))
    return 0 if out['status'] == 'PASS' else 5


if __name__ == '__main__':
    raise SystemExit(main())
