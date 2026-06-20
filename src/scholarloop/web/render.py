from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

STATUS_CLASS = {
    '已有证据支持': 'status-supported',
    '证据不足': 'status-insufficient',
    '存在争议': 'status-disputed',
    '需人工核验': 'status-review',
}
FIELD_LABELS = {
    'title': '论文标题',
    'authors_year': '作者/年份',
    'source_or_doi': '来源/DOI',
    'recommendation_reason': '推荐理由',
    'supported_research_question': '支持的研究问题',
    'method': '使用的方法',
    'data_or_scenario': '使用的数据/实验场景',
    'main_conclusion': '主要结论',
    'limitations': '局限性',
    'relevance_strength': '与用户问题的关联强度',
}


def _e(value: Any) -> str:
    return escape('' if value is None else str(value), quote=True)


def status_badge(status: str | None) -> str:
    label = status or '未知状态'
    cls = STATUS_CLASS.get(label, 'status-unknown')
    return f'<span class="badge {cls}">{_e(label)}</span>'


def render_query_options(queries: list[dict[str, Any]], selected: str | None = None) -> str:
    out = []
    for q in queries:
        label = f"{q['query_id']} — {q['query'][:90]}"
        if q.get('demo_label'):
            label = f"★ {q['demo_label']} / {label}"
        sel = ' selected' if q['query_id'] == selected else ''
        out.append(f'<option value="{_e(q["query_id"])}"{sel}>{_e(label)}</option>')
    return '\n'.join(out)


def render_decomposition(view: dict[str, Any]) -> str:
    items = ''.join(f'<li>{_e(x)}</li>' for x in view.get('decomposition') or [])
    return f'<ol>{items}</ol>'


def render_ranking(view: dict[str, Any]) -> str:
    rows = []
    evidence_titles = {int(c['corpusid']): (c.get('fields') or {}).get('title', {}).get('value', '') for c in view['evidence'].get('cards', [])}
    for row in view.get('ranking', [])[:20]:
        cid = int(row['corpusid'])
        title = evidence_titles.get(cid, '')
        reason = row.get('reason')
        reason_html = _e(reason) if reason else '<span class="muted">M010 per_query 未存储该论文 reason；不补写</span>'
        score = '' if row.get('score') is None else f"{float(row['score']):.4f}"
        rows.append(
            '<tr>'
            f'<td>{row["rank"]}</td><td>{cid}</td><td>{_e(title)}</td>'
            f'<td>{_e(score)}</td><td>{reason_html}</td><td>{"✅" if row.get("has_evidence_card") else "—"}</td>'
            '</tr>'
        )
    return '<table><thead><tr><th>Rank</th><th>CorpusID</th><th>标题（如有证据卡）</th><th>Score</th><th>M010 reason</th><th>证据卡</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


def render_matrix(view: dict[str, Any]) -> str:
    criteria = view['evidence'].get('criteria') or []
    head = '<tr><th>Rank</th><th>CorpusID</th><th>Title</th>' + ''.join(f'<th>{_e(c)}</th>' for c in criteria) + '</tr>'
    body = []
    for row in view['evidence'].get('matrix', []):
        cells = []
        for cell in row.get('cells', []):
            if cell.get('addresses'):
                cells.append(f'<td>✅ <span class="snippet">{_e(cell.get("snippet"))}</span><br>{status_badge(cell.get("status"))}</td>')
            else:
                cells.append(f'<td>—<br>{status_badge(cell.get("status"))}</td>')
        body.append(f'<tr><td>{row.get("rank")}</td><td>{row.get("corpusid")}</td><td>{_e(row.get("title"))}</td>' + ''.join(cells) + '</tr>')
    return '<div class="table-wrap"><table class="matrix"><thead>' + head + '</thead><tbody>' + ''.join(body) + '</tbody></table></div>'


def render_cards(view: dict[str, Any]) -> str:
    cards_html = []
    for card in view['evidence'].get('cards', []):
        fields = card.get('fields') or {}
        rows = []
        for name, field in fields.items():
            status = field.get('status')
            value = field.get('value') or ''
            hint = field.get('resolution_hint') or ''
            display = value if value else hint
            rows.append(
                '<tr>'
                f'<th>{_e(FIELD_LABELS.get(name, name))}</th>'
                f'<td>{status_badge(status)}</td>'
                f'<td class="field-value">{_e(display)}</td>'
                f'<td>{_e(field.get("source_field"))}</td>'
                f'<td>{_e(field.get("char_span"))}</td>'
                '</tr>'
            )
        cards_html.append(
            '<article class="card">'
            f'<h3>CorpusID {card.get("corpusid")}</h3>'
            '<table><thead><tr><th>字段</th><th>状态</th><th>值/提示</th><th>source</th><th>char_span</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></article>'
        )
    return ''.join(cards_html)


def render_status_legend() -> str:
    statuses = ['已有证据支持', '证据不足', '存在争议', '需人工核验']
    return '<div class="legend">' + ''.join(status_badge(s) for s in statuses) + '</div>'


def render_query_page(view: dict[str, Any], queries: list[dict[str, Any]]) -> str:
    template = (Path(__file__).parent / 'templates' / 'index.html').read_text(encoding='utf-8')
    demo = view.get('demo') or {}
    replacements = {
        '{{query_id}}': _e(view.get('query_id')),
        '{{query}}': _e(view.get('query')),
        '{{query_options}}': render_query_options(queries, view.get('query_id')),
        '{{demo_label}}': _e(demo.get('demo_label') or '基准查询'),
        '{{status_legend}}': render_status_legend(),
        '{{decomposition}}': render_decomposition(view),
        '{{ranking}}': render_ranking(view),
        '{{matrix}}': render_matrix(view),
        '{{cards}}': render_cards(view),
        '{{fabrication_rate}}': _e((view.get('m020_grounding') or {}).get('fabrication_rate')),
        '{{llm_calls}}': _e((view.get('render_contract') or {}).get('llm_calls_per_request')),
    }
    html = template
    for key, val in replacements.items():
        html = html.replace(key, val)
    return html
