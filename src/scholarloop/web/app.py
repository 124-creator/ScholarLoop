from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any

from scholarloop.web.data import get_paper_meta, get_query_doc, list_queries
from scholarloop.web.render import render_query_page

STATIC_DIR = Path(__file__).parent / 'static'


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')


class ScholarLoopHandler(BaseHTTPRequestHandler):
    server_version = 'ScholarLoopM030/1.0'

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter default; smoke records explicit lines.
        return

    def _send(self, body: bytes, status: int = 200, content_type: str = 'application/json; charset=utf-8') -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: Any, status: int = 200) -> None:
        self._send(json_bytes(data), status, 'application/json; charset=utf-8')

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        try:
            if path == '/healthz':
                self._send_json({'ok': True, 'mode': 'offline', 'llm_calls_per_request': 0, 'realtime_enabled': False})
                return
            if path == '/api/queries':
                self._send_json({'queries': list_queries(), 'count': len(list_queries()), 'llm_calls_per_request': 0})
                return
            if path.startswith('/api/queries/'):
                qid = unquote(path.split('/api/queries/', 1)[1])
                self._send_json(get_query_doc(qid))
                return
            if path.startswith('/api/papers/'):
                cid = int(unquote(path.split('/api/papers/', 1)[1]))
                self._send_json(get_paper_meta(cid))
                return
            if path == '/static/styles.css':
                self._send((STATIC_DIR / 'styles.css').read_bytes(), 200, 'text/css; charset=utf-8')
                return
            if path == '/' or path.startswith('/queries/'):
                queries = list_queries()
                qs = parse_qs(parsed.query)
                qid = qs.get('qid', [None])[0]
                if path.startswith('/queries/'):
                    qid = unquote(path.split('/queries/', 1)[1])
                qid = qid or (queries[0]['query_id'] if queries else '')
                html = render_query_page(get_query_doc(qid), queries).encode('utf-8')
                self._send(html, 200, 'text/html; charset=utf-8')
                return
            self._send_json({'error': 'not_found', 'path': parsed.path}, HTTPStatus.NOT_FOUND)
        except KeyError as exc:
            self._send_json({'error': 'not_found', 'message': str(exc), 'realtime_enabled': False}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({'error': 'internal_error', 'type': type(exc).__name__, 'message': str(exc)[:500]}, HTTPStatus.INTERNAL_SERVER_ERROR)


def create_server(host: str = '127.0.0.1', port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ScholarLoopHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='ScholarLoop M030 offline web demo')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    server = create_server(args.host, args.port)
    host, port = server.server_address
    print(f'ScholarLoop M030 offline demo running at http://{host}:{port}', flush=True)
    print('Default mode: offline, deterministic, 0 LLM calls/request. Press Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
