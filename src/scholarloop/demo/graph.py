from __future__ import annotations

import html
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from scholarloop.demo.assemble import M020_EVIDENCE_DIR, M070_GAPS_DISPLAY, read_json


def _copy(data: Any) -> Any:
    return deepcopy(data)


def load_graph_data(limit_edges: int | None = None) -> dict[str, Any]:
    gaps = read_json(M070_GAPS_DISPLAY)
    nodes = _copy(gaps.get("concept_nodes") or [])
    edges = _copy(gaps.get("matrix_edges") or [])
    if limit_edges is not None:
        edges = edges[:limit_edges]
        labels = {str(edge.get("source")) for edge in edges} | {str(edge.get("target")) for edge in edges}
        nodes = [node for node in nodes if str(node.get("label")) in labels]
    qids = sorted(p.stem for p in M020_EVIDENCE_DIR.glob("*.json"))[:3]
    evidence_sources = []
    for qid in qids:
        evidence = read_json(M020_EVIDENCE_DIR / f"{qid}.json")
        evidence_sources.append(
            {
                "query_id": qid,
                "source_path": str(M020_EVIDENCE_DIR / f"{qid}.json"),
                "criteria": _copy(evidence.get("criteria") or []),
                "citation_graph": _copy(evidence.get("citation_graph") or {}),
            }
        )
    return {
        "schema_version": "m100.graph.v1",
        "mode": "verified_json_only",
        "source_paths": {
            "m070_gaps_display": str(M070_GAPS_DISPLAY),
            "m020_evidence_dir": str(M020_EVIDENCE_DIR),
        },
        "missing_policy": "缺失字段显示需人工核验；不补写。",
        "nodes": nodes,
        "edges": edges,
        "evidence_sources": evidence_sources,
    }


def verify_graph_fidelity(graph: dict[str, Any] | None = None) -> dict[str, Any]:
    graph = graph or load_graph_data()
    gaps = read_json(M070_GAPS_DISPLAY)
    failures: list[str] = []
    if graph.get("nodes") != gaps.get("concept_nodes"):
        failures.append("nodes differ from reports/m070/gaps_display.json.concept_nodes")
    if graph.get("edges") != gaps.get("matrix_edges"):
        failures.append("edges differ from reports/m070/gaps_display.json.matrix_edges")
    for source in graph.get("evidence_sources", []):
        qid = source.get("query_id")
        path = M020_EVIDENCE_DIR / f"{qid}.json"
        if not path.exists():
            failures.append(f"evidence source missing: {qid}")
            continue
        evidence = read_json(path)
        if source.get("criteria") != (evidence.get("criteria") or []):
            failures.append(f"{qid}: criteria differ from M020 evidence")
        if source.get("citation_graph") != (evidence.get("citation_graph") or {}):
            failures.append(f"{qid}: citation_graph differs from M020 evidence")
    return {
        "schema_version": "m100.graph_fidelity.v1",
        "status": "PASS" if not failures else "BLOCKED",
        "fabrication": 0 if not failures else len(failures),
        "failures": failures,
        "source_paths": graph.get("source_paths"),
        "node_count": len(graph.get("nodes") or []),
        "edge_count": len(graph.get("edges") or []),
        "checked": {
            "nodes_equal_m070_concept_nodes": "nodes differ from reports/m070/gaps_display.json.concept_nodes" not in failures,
            "edges_equal_m070_matrix_edges": "edges differ from reports/m070/gaps_display.json.matrix_edges" not in failures,
            "m020_evidence_sources_equal": not any("M020" in failure or "criteria" in failure or "citation_graph" in failure for failure in failures),
        },
    }


def write_graph_fidelity(path: Path = Path("reports/m100/graph_fidelity.json")) -> dict[str, Any]:
    graph = load_graph_data()
    audit = verify_graph_fidelity(graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_graph_svg(graph: dict[str, Any], width: int = 960, height: int = 680) -> str:
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    labels = [str(node.get("label")) for node in nodes]
    n = max(1, len(labels))
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.36
    pos = {
        label: (
            cx + radius * math.cos(2 * math.pi * i / n),
            cy + radius * math.sin(2 * math.pi * i / n),
        )
        for i, label in enumerate(labels)
    }
    edge_svg = []
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source not in pos or target not in pos:
            continue
        x1, y1 = pos[source]
        x2, y2 = pos[target]
        future = int(edge.get("future_fill_count") or 0)
        stroke = "#16a34a" if future > 0 else "#94a3b8"
        width_edge = 1.4 + min(5, future)
        title = f"{source} → {target}; past={edge.get('past_cooccur_count')}; future={edge.get('future_fill_count')}; status={edge.get('evidence_status')}"
        edge_svg.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width_edge:.1f}" opacity="0.72"><title>{_e(title)}</title></line>'
        )
    node_svg = []
    for label, (x, y) in pos.items():
        node_svg.append(
            f'<g><circle cx="{x:.1f}" cy="{y:.1f}" r="18" fill="#2563eb" opacity="0.88"><title>{_e(label)}</title></circle>'
            f'<text x="{x:.1f}" y="{y + 34:.1f}" text-anchor="middle" font-size="12" fill="#111827">{_e(label)}</text></g>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="ScholarLoop verified relation graph">'
        '<rect width="100%" height="100%" fill="#f8fafc"/>'
        + "".join(edge_svg)
        + "".join(node_svg)
        + "</svg>"
    )


def render_graph_page(graph: dict[str, Any] | None = None) -> str:
    graph = graph or load_graph_data()
    audit = verify_graph_fidelity(graph)
    rows = "".join(
        "<tr>"
        f"<td>{_e(edge.get('source'))}</td><td>{_e(edge.get('target'))}</td>"
        f"<td>{_e(edge.get('past_cooccur_count'))}</td><td>{_e(edge.get('future_fill_count'))}</td><td>{_e(edge.get('evidence_status'))}</td>"
        "</tr>"
        for edge in graph.get("edges", [])[:50]
    )
    css = """
    body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#f8fafc;color:#111827}
    header{background:#0f172a;color:white;padding:20px 28px}main{max-width:1120px;margin:auto;padding:24px}
    section{background:white;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin:16px 0;box-shadow:0 1px 2px #0001}
    table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #e5e7eb;padding:6px}th{background:#f1f5f9}
    .ok{color:#166534}.warn{color:#92400e}.mono{font-family:ui-monospace,Menlo,Consolas,monospace}
    """
    return (
        "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>ScholarLoop M100 关系图</title>"
        f"<style>{css}</style><header><h1>ScholarLoop M100 关系图</h1><p>verified JSON only · fabrication={audit['fabrication']}</p></header><main>"
        "<section><h2>节点连线图</h2>"
        + render_graph_svg(graph)
        + "</section>"
        "<section><h2>忠实性与来源</h2>"
        f"<p class=\"{'ok' if audit['status']=='PASS' else 'warn'}\">fidelity status={_e(audit['status'])}; node_count={audit['node_count']}; edge_count={audit['edge_count']}</p>"
        f"<p class=\"mono\">M070: {_e(graph['source_paths']['m070_gaps_display'])}<br>M020: {_e(graph['source_paths']['m020_evidence_dir'])}</p>"
        "</section><section><h2>边值（逐字来自 M070 matrix_edges）</h2><table><thead><tr><th>source</th><th>target</th><th>past_cooccur_count</th><th>future_fill_count</th><th>evidence_status</th></tr></thead><tbody>"
        + rows
        + "</tbody></table></section></main></html>"
    )
