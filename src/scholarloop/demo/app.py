from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from scholarloop.demo.assemble import assemble_demo, get_query_view, list_query_summaries
from scholarloop.demo.graph import load_graph_data, render_graph_page
from scholarloop.demo.graph_layout import stable_graph_payload
from scholarloop.demo.interactive import build_trail, render_pro_page, verify_span_payload
from scholarloop.demo.realtime import run_realtime_query
from scholarloop.demo.render import render_page
from scholarloop.demo.studio import render_studio_page, search_payload


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "ScholarLoopM080/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, body: bytes, status: int = 200, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: Any, status: int = 200) -> None:
        self._send(json_bytes(data), status=status)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/healthz":
                self._json({"ok": True, "mode": "offline", "llm_calls_per_request": 0})
                return
            if path == "/api/demo":
                self._json(assemble_demo())
                return
            if path == "/api/metrics":
                self._json(assemble_demo()["metrics"])
                return
            if path == "/api/gaps":
                self._json(assemble_demo()["gaps"])
                return
            if path == "/api/graph":
                self._json(load_graph_data())
                return
            if path == "/graph":
                self._send(render_graph_page().encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if path == "/api/graph_stable":
                self._json(stable_graph_payload())
                return
            if path == "/api/search":
                query = (parse_qs(parsed.query).get("q") or [""])[0]
                self._json(search_payload(query))
                return
            if path == "/api/realtime":
                query = (parse_qs(parsed.query).get("q") or [""])[0]
                self._json(run_realtime_query(query))
                return
            if path == "/api/verify_span":
                qs = parse_qs(parsed.query)
                qid = (qs.get("qid") or [""])[0]
                corpusid = int((qs.get("corpusid") or ["0"])[0])
                field = (qs.get("field") or [""])[0]
                self._json(verify_span_payload(qid, corpusid, field))
                return
            if path == "/api/trail":
                qs = parse_qs(parsed.query)
                qid = (qs.get("qid") or [list_query_summaries()[0]["query_id"]])[0]
                self._json(build_trail(qid))
                return
            if path == "/pro":
                qid = (parse_qs(parsed.query).get("qid") or [None])[0]
                self._send(render_pro_page(qid).encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if path == "/studio":
                qid = (parse_qs(parsed.query).get("qid") or [None])[0]
                lang = (parse_qs(parsed.query).get("lang") or [None])[0]
                self._send(render_studio_page(qid, lang).encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if path == "/api/queries":
                summaries = list_query_summaries()
                self._json({"queries": summaries, "count": len(summaries), "llm_calls_per_request": 0})
                return
            if path.startswith("/api/queries/"):
                qid = unquote(path.split("/api/queries/", 1)[1])
                self._json(get_query_view(qid))
                return
            if path == "/":
                demo = assemble_demo()
                qid = (parse_qs(parsed.query).get("qid") or [demo["queries"][0]["query_id"]])[0]
                view = get_query_view(qid)
                self._send(render_page(demo, view).encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            self._json({"error": "not_found", "path": path}, status=HTTPStatus.NOT_FOUND)
        except KeyError as exc:
            self._json({"error": "not_found", "detail": str(exc)}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:  # keep smoke debuggable without leaking secrets
            self._json({"error": type(exc).__name__, "detail": str(exc)[:500]}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def create_server(host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), DemoHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ScholarLoop M080 offline integration demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    server = create_server(args.host, args.port)
    host, port = server.server_address
    print(f"ScholarLoop M080 demo running at http://{host}:{port} (offline, llm_calls_per_request=0)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
