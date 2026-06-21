from __future__ import annotations

import html
from typing import Any


def e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def badge(status: str | None) -> str:
    status = status or "未标注"
    cls = "ok" if status in {"已有证据支持", "已有外部来源支持"} else "warn"
    if "争议" in status:
        cls = "dispute"
    return f'<span class="badge {cls}">{e(status)}</span>'


def render_query_options(queries: list[dict[str, Any]], selected: str) -> str:
    return "".join(
        f'<option value="{e(q["query_id"])}" {"selected" if q["query_id"] == selected else ""}>{e(q["query_id"])} · {e(q["query"][:80])}</option>'
        for q in queries
    )


def render_decomposition(view: dict[str, Any]) -> str:
    return "<ol>" + "".join(f"<li>{e(item)}</li>" for item in view.get("decomposition", [])) + "</ol>"


def render_ranking(view: dict[str, Any]) -> str:
    rows = []
    for row in view["ranking"]["rows"]:
        rows.append(
            "<tr>"
            f"<td>{row['rank']}</td><td>{row['corpusid']}</td><td>{e(row['relation_label'])}</td>"
            f"<td>{e(row.get('score'))}</td><td class=\"reason\">{e(row.get('reason') or 'M040 未存储该项 reason；不补写')}</td>"
            "</tr>"
        )
    metrics = view["ranking"]["metrics"]
    return (
        '<p class="metric-line">'
        f"P@10={e(metrics.get('P@10'))} · R@20={e(metrics.get('R@20'))} · F1={e(metrics.get('F1'))} · NDCG@20={e(metrics.get('NDCG@20'))}"
        "</p>"
        '<table><thead><tr><th>Rank</th><th>CorpusID</th><th>相关性标注</th><th>M040 score</th><th>M040 reason</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def render_evidence_matrix(view: dict[str, Any]) -> str:
    criteria = view["evidence"].get("criteria") or []
    head = "<tr><th>Rank</th><th>CorpusID</th><th>Title</th>" + "".join(f"<th>{e(c)}</th>" for c in criteria) + "</tr>"
    body = []
    for row in view["evidence"].get("matrix", []):
        cells = []
        for cell in row.get("cells", []):
            snippet = cell.get("snippet") if cell.get("addresses") else "不补写"
            cells.append(f"<td>{badge(cell.get('status'))}<br><span class=\"snippet\">{e(snippet)}</span></td>")
        body.append(f"<tr><td>{e(row.get('rank'))}</td><td>{e(row.get('corpusid'))}</td><td>{e(row.get('title'))}</td>{''.join(cells)}</tr>")
    return '<div class="table-wrap"><table class="matrix"><thead>' + head + "</thead><tbody>" + "".join(body) + "</tbody></table></div>"


def render_enrichment(view: dict[str, Any]) -> str:
    rows = []
    for card in view["enrichment"].get("cards", []):
        a = card["authors_year"]
        s = card["source_or_doi"]
        prov_a = a.get("external_provenance") or {}
        prov_s = s.get("external_provenance") or {}
        rows.append(
            "<tr>"
            f"<td>{e(card['corpusid'])}</td><td>{e(card['title'])}</td>"
            f"<td>{badge(a.get('status'))}<br>{e(a.get('display'))}<br><span class=\"muted\">{e(prov_a.get('source') or a.get('resolution_hint') or '')}</span></td>"
            f"<td>{badge(s.get('status'))}<br>{e(s.get('display'))}<br><span class=\"muted\">{e(prov_s.get('source') or s.get('resolution_hint') or '')}</span></td>"
            "</tr>"
        )
    return "<table><thead><tr><th>CorpusID</th><th>Title</th><th>作者/年份</th><th>DOI/来源</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def render_gaps(gaps: dict[str, Any], limit: int = 10) -> str:
    items = gaps.get("items", [])[:limit]
    rows = []
    for item in items:
        counts = item.get("counts") or {}
        rows.append(
            "<tr>"
            f"<td>{e(item.get('id'))}</td><td>{e(item.get('concept_a'))}</td><td>{e(item.get('concept_b'))}</td>"
            f"<td>{e(item.get('score'))}</td><td>{badge(item.get('evidence_status'))}</td>"
            f"<td>past={e(counts.get('past_cooccur_count'))}; future={e(counts.get('future_fill_count'))}</td>"
            f"<td class=\"reason\">{e(item.get('narration'))}</td>"
            "</tr>"
        )
    edges = gaps.get("matrix_edges", [])[:limit]
    edge_rows = "".join(
        f"<tr><td>{e(edge.get('source'))}</td><td>{e(edge.get('target'))}</td><td>{e(edge.get('past_cooccur_count'))}</td><td>{e(edge.get('future_fill_count'))}</td><td>{badge(edge.get('evidence_status'))}</td></tr>"
        for edge in edges
    )
    return (
        "<h3>空白候选列表</h3><table><thead><tr><th>ID</th><th>概念 A</th><th>概念 B</th><th>Score</th><th>状态</th><th>计数</th><th>接地叙述</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table><h3>关系矩阵边</h3><table><thead><tr><th>Source</th><th>Target</th><th>历史共现</th><th>未来填补</th><th>状态</th></tr></thead><tbody>"
        + edge_rows
        + "</tbody></table>"
    )


def render_metrics(metrics: dict[str, Any]) -> str:
    lit = metrics["litsearch"]
    rsq = metrics["realscholarquery"]
    gap = metrics["research_gaps"]["prediction_vs_random"]
    return (
        "<ul>"
        f"<li>LitSearch A-v2 F1={e(lit['a_v2']['F1'])}, BM25 F1={e(lit['bm25']['F1'])}; source={e(lit['source_path'])}</li>"
        f"<li>RealScholarQuery A-v2 F1={e(rsq['a_v2_resolvable']['F1'])}, BM25 F1={e(rsq['bm25_resolvable']['F1'])}; source={e(rsq['source_path'])}</li>"
        f"<li>M070 gap fill={e(gap['candidate_fill_rate'])}, random={e(gap['baseline_fill_rate'])}, delta={e(gap['paired_delta'])}; source={e(metrics['research_gaps']['source_path'])}</li>"
        f"<li>Offline demo: 0 LLM calls/request; A-v2 avg tokens/query={e(lit['efficiency'].get('a_v2_avg_tokens_per_query'))}; p95 query s={e(lit['efficiency'].get('p95_query_s'))}</li>"
        "</ul>"
    )


def render_page(demo: dict[str, Any], view: dict[str, Any]) -> str:
    summaries = [
        {"query_id": q["query_id"], "query": q["query"]}
        for q in demo["queries"]
    ]
    css = """
    body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#f7f8fa;color:#1f2937}
    header{background:#111827;color:#fff;padding:20px 28px} main{padding:24px;max-width:1280px;margin:auto}
    section{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin:16px 0;box-shadow:0 1px 2px #0001}
    table{border-collapse:collapse;width:100%;font-size:13px} th,td{border:1px solid #e5e7eb;padding:7px;vertical-align:top} th{background:#f3f4f6}
    .table-wrap{overflow:auto}.badge{border-radius:999px;padding:2px 8px;background:#e5e7eb}.ok{background:#dcfce7}.warn{background:#fef3c7}.dispute{background:#fee2e2}
    .muted{color:#6b7280}.reason{max-width:520px}.snippet{color:#374151}.metric-line{font-family:ui-monospace,Menlo,Consolas,monospace}
    select{max-width:100%;padding:8px}
    """
    return (
        "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>ScholarLoop M080 Demo</title>"
        f"<style>{css}</style><header><h1>ScholarLoop M080 整合 Demo</h1><p>offline · 0 LLM 调用 · verified JSON 忠实呈现</p></header><main>"
        "<form><label>选择查询：<select name=\"qid\" onchange=\"this.form.submit()\">"
        + render_query_options(summaries, view["query_id"])
        + "</select></label></form>"
        f"<section><h2>① 查询理解与分解</h2><p><b>{e(view['query_id'])}</b> · {e(view['query'])}</p>{render_decomposition(view)}</section>"
        f"<section><h2>② A-v2 论文综合排序</h2>{render_ranking(view)}</section>"
        f"<section><h2>③ B-lite 逐条证据矩阵</h2>{render_evidence_matrix(view)}</section>"
        f"<section><h2>④ 真实学术连接器富化</h2>{render_enrichment(view)}</section>"
        f"<section><h2>⑤ 研究空白发现</h2>{render_gaps(demo['gaps'])}</section>"
        f"<section><h2>效率/成本与指标来源</h2>{render_metrics(demo['metrics'])}</section>"
        "</main></html>"
    )

