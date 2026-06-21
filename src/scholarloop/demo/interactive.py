from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from scholarloop.demo.assemble import (
    M020_EVIDENCE_DIR,
    M040_RESULTS,
    M050_REPLAY_DIR,
    M070_GAPS_DISPLAY,
    evidence_query_ids,
    get_query_view,
    load_evidence,
    load_gaps_display,
)
from scholarloop.demo.graph import load_graph_data
from scholarloop.demo.source_text import source_record_for_display, verify_value_span

M100_GAP_FREQUENCY = Path("reports/m100/gap_frequency_ablation.json")
M110_CONSISTENCY = Path("reports/m110/consistency_scan.json")


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _json_attr(value: Any) -> str:
    return _e(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _status_class(status: str | None) -> str:
    mapping = {
        "已有证据支持": "ok",
        "存在争议": "warn",
        "证据不足": "muted",
        "需人工核验": "review",
    }
    return mapping.get(status or "", "muted")


def verify_span_payload(qid: str, corpusid: int, field: str) -> dict[str, Any]:
    evidence = load_evidence(qid)
    selected: dict[str, Any] | None = None
    for card in evidence.get("cards", []):
        if int(card.get("corpusid")) == int(corpusid):
            selected = (card.get("fields") or {}).get(field)
            break
    if selected is None:
        return {
            "schema_version": "m120.verify_span.v1",
            "status": "需人工核验",
            "highlightable": False,
            "mismatch": False,
            "manual_review_reason": f"field not found in M020 evidence: {qid}/{corpusid}/{field}",
            "source_path": str(M020_EVIDENCE_DIR / f"{qid}.json"),
        }
    verification = verify_value_span(int(corpusid), selected, value_key="value")
    source_field = verification.get("source_field")
    source = source_record_for_display(int(corpusid), source_field) if source_field else {}
    return {
        "schema_version": "m120.verify_span.v1",
        "query_id": qid,
        "source_path": str(M020_EVIDENCE_DIR / f"{qid}.json"),
        "source_contract": "highlight only when source_text[char_span] == value; otherwise manual review",
        **verification,
        "source_text": source.get("source_text", ""),
    }


def iter_card_field_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for qid in evidence_query_ids():
        evidence = load_evidence(qid)
        for card in evidence.get("cards", []):
            corpusid = int(card["corpusid"])
            for name, field in (card.get("fields") or {}).items():
                result = verify_value_span(corpusid, field, value_key="value")
                checks.append(
                    {
                        "kind": "card_field",
                        "query_id": qid,
                        "corpusid": corpusid,
                        "field": name,
                        "source_field": result.get("source_field"),
                        "char_span": result.get("char_span"),
                        "status": result.get("status"),
                        "highlightable": result.get("highlightable"),
                        "mismatch": result.get("mismatch"),
                        "manual_review_reason": result.get("manual_review_reason"),
                    }
                )
    return checks


def iter_matrix_cell_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for qid in evidence_query_ids():
        evidence = load_evidence(qid)
        for row in evidence.get("matrix", []):
            corpusid = int(row["corpusid"])
            for idx, cell in enumerate(row.get("cells") or []):
                pseudo = {
                    "field": f"matrix[{idx}]",
                    "criterion": cell.get("criterion"),
                    "value": cell.get("snippet") or "",
                    "status": cell.get("status"),
                    "source_field": cell.get("source_field"),
                    "char_span": cell.get("char_span"),
                    "confidence": cell.get("confidence"),
                }
                result = verify_value_span(corpusid, pseudo, value_key="value")
                checks.append(
                    {
                        "kind": "matrix_cell",
                        "query_id": qid,
                        "corpusid": corpusid,
                        "criterion": cell.get("criterion"),
                        "source_field": result.get("source_field"),
                        "char_span": result.get("char_span"),
                        "status": result.get("status"),
                        "highlightable": result.get("highlightable"),
                        "mismatch": result.get("mismatch"),
                        "manual_review_reason": result.get("manual_review_reason"),
                    }
                )
    return checks


def build_span_fidelity() -> dict[str, Any]:
    checks = iter_card_field_checks() + iter_matrix_cell_checks()
    mismatches = [row for row in checks if row.get("mismatch")]
    null_or_review = [row for row in checks if not row.get("highlightable")]
    return {
        "schema_version": "m120.span_fidelity.v1",
        "status": "PASS" if not mismatches else "BLOCKED",
        "source": {
            "m020_evidence_dir": str(M020_EVIDENCE_DIR),
            "litsearch_source_adapter": "scholarloop.evidence.source.EvidenceSource",
        },
        "contract": "highlight_text == source_text[char_span] == field value; non-verifiable fields are not highlighted",
        "total_checks": len(checks),
        "highlightable_count": sum(1 for row in checks if row.get("highlightable")),
        "manual_review_or_null_span_count": len(null_or_review),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
        "manual_review_sample": null_or_review[:20],
    }


def write_span_fidelity(path: Path = Path("reports/m120/span_fidelity.json")) -> dict[str, Any]:
    report = build_span_fidelity()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_trail(qid: str) -> dict[str, Any]:
    view = get_query_view(qid)
    gap_freq = json.loads(M100_GAP_FREQUENCY.read_text(encoding="utf-8")) if M100_GAP_FREQUENCY.exists() else {}
    gaps = load_gaps_display()
    evidence_cards = view["evidence"]["cards"]
    top_rows = view["ranking"]["rows"][:5]
    steps = [
        {
            "step": 1,
            "label": "查询拆解",
            "what_happened": "读取 M010/M040 已落盘 decomposition；Demo 不调用 LLM。",
            "data": view.get("decomposition") or [],
            "source_paths": [str(M040_RESULTS), view["evidence"]["source_path"]],
            "fabricated": False,
        },
        {
            "step": 2,
            "label": "检索与排序",
            "what_happened": "读取 A-v2 top20、gold 命中和排序理由；不新增排序或指标。",
            "data": {
                "system": view["ranking"]["system"],
                "metrics": view["ranking"]["metrics"],
                "top_rows": top_rows,
            },
            "source_paths": [view["ranking"]["source_path"]],
            "fabricated": False,
        },
        {
            "step": 3,
            "label": "证据接地",
            "what_happened": "读取 M020 evidence cards/matrix；可点字段核验 char_span 原文高亮。",
            "data": {
                "card_count": len(evidence_cards),
                "matrix_rows": len(view["evidence"]["matrix"]),
                "status_counts": _status_counts(evidence_cards),
            },
            "source_paths": [view["evidence"]["source_path"], str(M020_EVIDENCE_DIR)],
            "fabricated": False,
        },
        {
            "step": 4,
            "label": "研究空白候选启发",
            "what_happened": "读取 M070 候选展示，并按 M110 口径展示 M100 频率边界：候选启发，非独立预测能力。",
            "data": {
                "gap_items": len(gaps.get("items") or []),
                "graph_nodes": len(gaps.get("concept_nodes") or []),
                "graph_edges": len(gaps.get("matrix_edges") or []),
                "m100_frequency_boundary": {
                    "conclusion": gap_freq.get("conclusion"),
                    "claim_boundary": gap_freq.get("claim_boundary"),
                    "frequency_matched_delta": (gap_freq.get("frequency_matched_metrics") or {}).get("paired_delta"),
                },
            },
            "source_paths": [str(M070_GAPS_DISPLAY), str(M100_GAP_FREQUENCY), str(M110_CONSISTENCY)],
            "fabricated": False,
        },
    ]
    return {
        "schema_version": "m120.trail.v1",
        "query_id": qid,
        "query": view.get("query"),
        "mode": "verified_artifact_trace_only",
        "llm_calls_per_request": 0,
        "fabrication": 0,
        "steps": steps,
        "boundary_note": "research gaps are candidate-generation hints only; M100/M110 frequency boundary is shown explicitly",
    }


def _status_counts(cards: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in cards:
        for field in (card.get("fields") or {}).values():
            status = str(field.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
    return counts


def build_trail_fidelity() -> dict[str, Any]:
    qids = evidence_query_ids()
    trails = [build_trail(qid) for qid in qids]
    missing_sources: list[dict[str, Any]] = []
    fabricated_steps: list[dict[str, Any]] = []
    for trail in trails:
        for step in trail.get("steps", []):
            if step.get("fabricated"):
                fabricated_steps.append({"query_id": trail["query_id"], "step": step["label"]})
            for source in step.get("source_paths", []):
                path = Path(source)
                if not path.exists():
                    missing_sources.append({"query_id": trail["query_id"], "step": step["label"], "source": source})
    return {
        "schema_version": "m120.trail_fidelity.v1",
        "status": "PASS" if not missing_sources and not fabricated_steps else "BLOCKED",
        "query_count": len(trails),
        "step_count": sum(len(t.get("steps", [])) for t in trails),
        "fabrication": len(fabricated_steps),
        "fabricated_steps": fabricated_steps,
        "missing_source_count": len(missing_sources),
        "missing_sources": missing_sources[:50],
        "source_policy": "all trail steps surface verified pipeline artifacts only; no generated chain-of-thought",
    }


def write_trail_fidelity(path: Path = Path("reports/m120/trail_fidelity.json")) -> dict[str, Any]:
    report = build_trail_fidelity()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def render_pro_page(qid: str | None = None) -> str:
    qids = evidence_query_ids()
    qid = qid if qid in qids else qids[0]
    view = get_query_view(qid)
    trail = build_trail(qid)
    graph = load_graph_data(limit_edges=18)
    first_card = (view["evidence"]["cards"] or [{}])[0]
    cards_html = _render_cards(view)
    trail_html = _render_trail(trail)
    graph_html = _render_compact_graph(graph)
    q_options = "".join(
        f'<option value="{_e(item)}" {"selected" if item == qid else ""}>{_e(item)}</option>'
        for item in qids
    )
    css = """
    :root{--bg:#0f172a;--card:#ffffff;--muted:#64748b;--line:#e2e8f0;--ok:#15803d;--warn:#b45309;--review:#7c3aed;--bad:#b91c1c}
    *{box-sizing:border-box}body{margin:0;background:#f8fafc;color:#111827;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}
    header{background:linear-gradient(135deg,#0f172a,#1e3a8a);color:white;padding:26px 32px}.wrap{max-width:1220px;margin:auto;padding:22px}
    .grid{display:grid;grid-template-columns:1.15fr .85fr;gap:18px}.card{background:white;border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 10px 20px #0f172a0a;margin-bottom:18px}
    .pill{display:inline-flex;gap:6px;align-items:center;border-radius:999px;padding:4px 10px;font-size:12px;background:#eef2ff;color:#3730a3;margin:2px}.ok{color:var(--ok)}.warn{color:var(--warn)}.review{color:var(--review)}.muted{color:var(--muted)}
    button.verify{border:1px solid var(--line);background:#f8fafc;border-radius:10px;padding:8px;margin:4px;cursor:pointer;text-align:left}button.verify:hover{border-color:#2563eb;background:#eff6ff}
    .field{display:block;font-size:13px}.hl{background:#fef08a;border-radius:5px;padding:0 2px}.source{white-space:pre-wrap;line-height:1.65;border:1px solid var(--line);border-radius:12px;padding:14px;background:#fffdf2;max-height:320px;overflow:auto}
    details{border:1px solid var(--line);border-radius:12px;margin:10px 0;background:#fff}summary{cursor:pointer;padding:12px 14px;font-weight:650}.step{padding:0 14px 14px}.mini{font-size:12px;color:var(--muted)}svg text{font-size:11px}
    @media(max-width:900px){.grid{grid-template-columns:1fr}header{padding:18px}.wrap{padding:14px}}
    """
    js = """
    async function verifySpan(btn){
      const params = new URLSearchParams({qid:btn.dataset.qid, corpusid:btn.dataset.corpusid, field:btn.dataset.field});
      const out = document.getElementById('span-result');
      out.innerHTML = '<p class="mini">loading verified span...</p>';
      const res = await fetch('/api/verify_span?' + params.toString());
      const data = await res.json();
      if(!data.highlightable){
        out.innerHTML = `<p class="review">需人工核验：${escapeHtml(data.manual_review_reason || 'not highlightable')}</p>`;
        return;
      }
      const p = data.source_preview;
      out.innerHTML = `<p><b>${escapeHtml(data.field)}</b> · ${escapeHtml(data.status)} · ${escapeHtml(data.source_field)} · confidence=${escapeHtml(data.confidence)}</p>`+
        `<div class="source">${escapeHtml(p.before)}<span class="hl">${escapeHtml(p.highlight)}</span>${escapeHtml(p.after)}</div>`+
        `<p class="mini">contract: highlight == source_text[char_span] == value; source=${escapeHtml(data.source_path)}</p>`;
    }
    function escapeHtml(s){return String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
    function gotoQuery(sel){location.href='/pro?qid='+encodeURIComponent(sel.value)}
    """
    return (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>ScholarLoop Pro · 可核验可信 Demo</title><style>{css}</style>"
        f"<header><h1>ScholarLoop Pro：点即核验的可信论文搜索</h1><p>offline 0-LLM · verified artifacts only · qid={_e(qid)}</p>"
        '<p><span class="pill">🔍 点证据字段 → 原文高亮</span><span class="pill">🧭 渐进式轨迹</span><span class="pill">🕸 关系图</span><span class="pill">零编造</span></p></header>'
        '<main class="wrap"><section class="card"><label>选择查询： <select onchange="gotoQuery(this)">'
        + q_options
        + f'</select></label><h2>{_e(view.get("query"))}</h2><p class="mini">Existing M080 baseline remains at <a href="/">/</a>; this is an additive enhanced view.</p></section>'
        '<div class="grid"><div>'
        '<section class="card"><h2>1 · 点即核验证据链</h2><p class="mini">只在 source_text[char_span] == value 时高亮；否则显示需人工核验。</p>'
        + cards_html
        + '</section><section class="card"><h2>2 · Agent 决策轨迹（verified only）</h2>'
        + trail_html
        + '</section></div><aside>'
        '<section class="card"><h2>核验结果</h2><div id="span-result"><p class="mini">点击左侧任一字段。</p></div></section>'
        '<section class="card"><h2>3 · 关系图聚焦</h2>'
        + graph_html
        + '</section></aside></div></main>'
        f"<script>{js}</script></html>"
    )


def _render_cards(view: dict[str, Any]) -> str:
    rows: list[str] = []
    field_order = ["title", "recommendation_reason", "supported_research_question", "method", "data_or_scenario", "main_conclusion", "limitations"]
    for card in view["evidence"]["cards"]:
        corpusid = int(card["corpusid"])
        fields = card.get("fields") or {}
        buttons = []
        for name in field_order:
            field = fields.get(name) or {}
            status = field.get("status")
            value = field.get("value") or field.get("resolution_hint") or "需人工核验"
            buttons.append(
                f'<button class="verify" data-qid="{_e(view["query_id"])}" data-corpusid="{corpusid}" data-field="{_e(name)}" onclick="verifySpan(this)">'
                f'<span class="field"><b>{_e(name)}</b> <span class="{_status_class(status)}">● {_e(status)}</span></span>'
                f'<span class="mini">{_e(str(value)[:170])}</span></button>'
            )
        rows.append(f'<article><h3>corpusid={corpusid}</h3>{"".join(buttons)}</article>')
    return "".join(rows)


def _render_trail(trail: dict[str, Any]) -> str:
    out = []
    for step in trail.get("steps", []):
        sources = "".join(f'<span class="pill">{_e(src)}</span>' for src in step.get("source_paths", []))
        data_preview = json.dumps(step.get("data"), ensure_ascii=False, indent=2)[:1200]
        out.append(
            f'<details open><summary>{step["step"]}. {_e(step["label"])} <span class="mini">fabricated={_e(step.get("fabricated"))}</span></summary>'
            f'<div class="step"><p>{_e(step.get("what_happened"))}</p><p>{sources}</p><pre class="source">{_e(data_preview)}</pre></div></details>'
        )
    return "".join(out)


def _render_compact_graph(graph: dict[str, Any]) -> str:
    nodes = [str(n.get("label")) for n in graph.get("nodes", [])][:12]
    node_set = set(nodes)
    edges = [e for e in graph.get("edges", []) if str(e.get("source")) in node_set and str(e.get("target")) in node_set][:18]
    if not nodes:
        return '<p class="review">需人工核验：graph nodes missing</p>'
    import math

    width, height = 520, 360
    cx, cy, radius = width / 2, height / 2, 135
    pos = {
        label: (
            cx + radius * math.cos(2 * math.pi * i / len(nodes)),
            cy + radius * math.sin(2 * math.pi * i / len(nodes)),
        )
        for i, label in enumerate(nodes)
    }
    edge_svg = []
    for edge in edges:
        s, t = str(edge.get("source")), str(edge.get("target"))
        x1, y1 = pos[s]
        x2, y2 = pos[t]
        color = "#16a34a" if int(edge.get("future_fill_count") or 0) > 0 else "#94a3b8"
        edge_svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="2"><title>{_e(s)} → {_e(t)}</title></line>')
    node_svg = []
    for label, (x, y) in pos.items():
        node_svg.append(f'<g><circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="#2563eb"><title>{_e(label)}</title></circle><text x="{x:.1f}" y="{y+28:.1f}" text-anchor="middle">{_e(label)}</text></g>')
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="verified relation graph">'
        '<rect width="100%" height="100%" fill="#f8fafc"/>'
        + "".join(edge_svg)
        + "".join(node_svg)
        + '</svg><p class="mini">数据来自 /api/graph；研究空白按 M110 频率边界仅作候选启发。</p>'
    )
