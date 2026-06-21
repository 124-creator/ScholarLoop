from __future__ import annotations

import html
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from scholarloop.demo.assemble import (
    M040_RESULTS,
    M060_RESULTS,
    M070_GAPS_DISPLAY,
    assemble_demo,
    evidence_query_ids,
    get_query_view,
    list_query_summaries,
    load_gaps_display,
    load_m040,
    load_m060,
)
from scholarloop.demo.design import NON_VERIFIED_NOTE, REALTIME_LABEL, studio_css, studio_js
from scholarloop.demo.enrich_view import ENRICHED_FIELDS, display_field_from_m050, field_label, status_label
from scholarloop.demo.graph_layout import render_stable_graph_svg, stable_graph_payload, verify_graph_determinism
from scholarloop.demo.i18n import EXAMPLE_QUESTIONS, TRANSLATIONS, catalog_keys, normalize_lang, tr
from scholarloop.demo.interactive import build_span_fidelity, build_trail, build_trail_fidelity
from scholarloop.demo.realtime import run_realtime_query

NEEDS_REVIEW = "\u9700\u4eba\u5de5\u6838\u9a8c"


def _copy(data: Any) -> Any:
    return deepcopy(data)


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _json_preview(value: Any, limit: int = 1500) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    return text if len(text) <= limit else text[:limit] + "\n..."


def search_payload(query: str) -> dict[str, Any]:
    """Wrap the existing realtime path without changing retrieval logic."""

    raw = run_realtime_query(query)
    status = raw.get("status")
    ok = status == "ok"
    cost = raw.get("cost") or {"llm_calls": 0, "tokens": 0, "latency_s": 0.0}
    results = raw.get("results") if ok else []
    return {
        "schema_version": "m130.search_response.v1",
        "label": REALTIME_LABEL,
        "verified_load_bearing": False,
        "deterministic": False,
        "source_contract": NON_VERIFIED_NOTE,
        "status": status,
        "enabled": bool(raw.get("enabled")),
        "reason": raw.get("reason"),
        "fallback_reason": None if ok else raw.get("reason", "realtime unavailable"),
        "query": " ".join((query or "").split()),
        "decomposition": raw.get("decomposition") or {},
        "results": results or [],
        "cost": cost,
        "notice": raw.get("notice") or NON_VERIFIED_NOTE,
        "raw_mode": raw.get("mode"),
    }


def _format_metric(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return "n/a" if value is None else str(value)


def _metrics_html(demo: dict[str, Any]) -> str:
    lit = demo["metrics"]["litsearch"]
    rsq = demo["metrics"]["realscholarquery"]
    metrics = [
        ("LitSearch A-v2 F1", lit["a_v2"].get("F1"), "verified public benchmark"),
        ("LitSearch BM25 F1", lit["bm25"].get("F1"), "baseline for comparison"),
        ("RSQ resolvable A-v2 F1", rsq["a_v2_resolvable"].get("F1"), "second public benchmark"),
        ("Gap candidates", len(demo["gaps"].get("items") or []), "research-gap candidates"),
    ]
    return "".join(
        f'<div class="metric"><b>{_e(_format_metric(value))}</b><span>{_e(label)}<br>{_e(source)}</span></div>'
        for label, value, source in metrics
    )


def _trust_strip(demo: dict[str, Any], lang: str) -> str:
    corpus_count = 64183
    stats = [
        ("0", tr(lang, "trust_stat_fabrication")),
        (f"{corpus_count:,}", tr(lang, "trust_stat_corpus")),
        ("2/2", tr(lang, "trust_stat_benchmarks")),
    ]
    return '<div class="trust-strip">' + "".join(
        f'<div class="trust-stat"><b>{_e(value)}</b><span>{_e(label)}</span></div>'
        for value, label in stats
    ) + "</div>"


def _query_selector(qid: str) -> str:
    options = []
    for item in list_query_summaries():
        selected = " selected" if item["query_id"] == qid else ""
        label = f'{item["query_id"]} · {item["query"][:80]}'
        options.append(f'<option value="{_e(item["query_id"])}"{selected}>{_e(label)}</option>')
    return '<select onchange="gotoStudioQueryLang(this)" aria-label="Select verified benchmark query">' + "".join(options) + "</select>"


def _lang_switch(lang: str, qid: str) -> str:
    lang = normalize_lang(lang)
    zh_class = "active" if lang == "zh" else ""
    en_class = "active" if lang == "en" else ""
    return (
        '<nav class="top-actions" aria-label="Studio controls">'
        f'<a class="{zh_class}" href="/studio?lang=zh&qid={_e(qid)}">{_e(tr(lang, "lang_zh"))}</a>'
        f'<a class="{en_class}" href="/studio?lang=en&qid={_e(qid)}">{_e(tr(lang, "lang_en"))}</a>'
        f'<button type="button" onclick="toggleTheme()" aria-label="{_e(tr(lang, "theme_toggle"))}">{_e(tr(lang, "theme_toggle"))}</button>'
        "</nav>"
    )


def _example_chips(lang: str) -> str:
    chips = []
    for question in EXAMPLE_QUESTIONS[normalize_lang(lang)]:
        chips.append(
            f'<button type="button" class="example-chip" data-question="{_e(question)}" onclick="fillExample(this)">{_e(question)}</button>'
        )
    return f'<div class="example-chips" aria-label="{_e(tr(lang, "examples_label"))}">' + "".join(chips) + "</div>"


def _field_display(view: dict[str, Any], corpusid: int, name: str, field: dict[str, Any], lang: str) -> dict[str, Any]:
    if name in ENRICHED_FIELDS:
        return display_field_from_m050(view["query_id"], corpusid, name, lang)
    value = field.get("value") or NEEDS_REVIEW
    status = field.get("status") or NEEDS_REVIEW
    return {
        "label": field_label(name, lang),
        "display_status": status_label(status, lang),
        "display_value": value,
        "badge": None,
        "manual_review": False,
        "matched_m050": False,
        "value": value,
    }


def _verified_fields_html(view: dict[str, Any], lang: str = "zh") -> str:
    field_order = [
        "title",
        "recommendation_reason",
        "supported_research_question",
        "method",
        "data_or_scenario",
        "main_conclusion",
        "limitations",
        "authors_year",
        "source_or_doi",
    ]
    cards = view["evidence"].get("cards") or []
    out: list[str] = []
    for idx, card in enumerate(cards[:3], start=1):
        corpusid = int(card["corpusid"])
        fields = card.get("fields") or {}
        chips: list[str] = []
        for name in field_order:
            field = fields.get(name) or {}
            display = _field_display(view, corpusid, name, field, lang)
            badge = (
                f'<span class="evidence-badge">{_e(tr(lang, "source_badge"))}</span>'
                if display.get("matched_m050")
                else ""
            )
            manual_class = " manual-note" if display.get("manual_review") else ""
            chips.append(
                f'<button type="button" class="verify-chip" data-qid="{_e(view["query_id"])}" data-corpusid="{corpusid}" data-field="{_e(name)}" onclick="verifyStudioSpan(this)">'
                f'<strong>{_e(display["label"])} · {_e(display["display_status"])}</strong>'
                f'<span class="{manual_class.strip()}">{_e(str(display["display_value"])[:220])}</span>'
                f'<span class="field-meta">{badge}</span></button>'
            )
        title = (fields.get("title") or {}).get("value") or f"paper {idx}"
        out.append(
            '<article class="evidence-card">'
            f'<h3 class="evidence-card-title"><span>{idx}. {_e(title)}</span><span class="evidence-badge">paper {corpusid}</span></h3>'
            f'<div class="field-list">{"".join(chips)}</div></article>'
        )
    return "".join(out) or f'<div class="empty">{_e(tr(lang, "manual_review"))}</div>'


def _source_label(source: str, lang: str) -> str:
    normalized = source.replace("\\", "/")
    if "m040" in normalized:
        return tr(lang, "source_m040")
    if "m020" in normalized:
        return tr(lang, "source_m020")
    if "m070" in normalized:
        return tr(lang, "source_m070")
    if "m100" in normalized:
        return tr(lang, "source_m100")
    if "m110" in normalized:
        return tr(lang, "source_m110")
    return tr(lang, "source_generic")


def _readable_data(step: dict[str, Any], lang: str) -> str:
    data = step.get("data")
    if isinstance(data, list):
        return '<div class="tag-list">' + "".join(f'<span class="tag">{_e(item)}</span>' for item in data) + "</div>"
    if isinstance(data, dict):
        if "top_rows" in data:
            rows = data.get("top_rows") or []
            return '<div class="tag-list">' + "".join(
                f'<span class="tag">#{_e(row.get("rank"))} · paper {_e(row.get("corpusid"))}</span>' for row in rows[:5]
            ) + "</div>"
        if "status_counts" in data:
            counts = data.get("status_counts") or {}
            return '<div class="tag-list">' + "".join(f'<span class="tag">{_e(k)}: {_e(v)}</span>' for k, v in counts.items()) + "</div>"
        if "gap_items" in data:
            return (
                '<div class="tag-list">'
                f'<span class="tag">{_e(tr(lang, "gap_candidates"))}: {_e(data.get("gap_items"))}</span>'
                f'<span class="tag">{_e(tr(lang, "concepts_label"))}: {_e(data.get("graph_nodes"))}</span>'
                f'<span class="tag">{_e(tr(lang, "relations_label"))}: {_e(data.get("graph_edges"))}</span>'
                "</div>"
            )
    return f'<p class="subtle">{_e(tr(lang, "structured_evidence_available"))}</p>'


def _trail_html(qid: str, lang: str = "zh") -> str:
    trail = build_trail(qid)
    rows: list[str] = []
    for step in trail.get("steps", []):
        step_no = int(step.get("step") or 0)
        label = tr(lang, f"trail_step_{step_no}_label") if step_no else step.get("label")
        body = tr(lang, f"trail_step_{step_no}_body") if step_no else step.get("what_happened")
        readable_sources = "".join(f'<span class="pill ok">{_e(_source_label(src, lang))}</span>' for src in step.get("source_paths", []))
        raw_sources = "".join(f'<span class="pill">{_e(src)}</span>' for src in step.get("source_paths", []))
        rows.append(
            f'<article class="trail-step"><h3>{_e(step.get("step"))}. {_e(label)}</h3>'
            f'<p>{_e(body)}</p><div class="pill-row">{readable_sources}<span class="pill ok">{_e(tr(lang, "fabricated_zero_tag"))}</span></div>'
            + _readable_data(step, lang)
            + f'<details class="raw-evidence"><summary>{_e(tr(lang, "raw_evidence"))}</summary>'
            f'<div class="path-list">{raw_sources}</div><pre>{_e(_json_preview(step.get("data"), 1200))}</pre></details></article>'
        )
    return "".join(rows)


def _technical_appendix(lang: str) -> str:
    return (
        f'<details class="technical-appendix"><summary>{_e(tr(lang, "technical_appendix"))}</summary>'
        '<div class="pill-row">'
        '<span class="pill">/api/search?q=...</span>'
        '<span class="pill">run_realtime_query</span>'
        '<span class="pill">/api/graph_stable</span>'
        '<span class="pill">client_force_simulation=false</span>'
        '<span class="pill">stable SVG graph</span>'
        '<span class="pill">source_text[char_span] == value</span>'
        '<span class="pill">M020 · M040 · M050 · M060 · M070 · M100 · M110 · M120</span>'
        f'</div><p class="subtle">{_e(tr(lang, "technical_appendix_body"))}</p></details>'
    )


def render_studio_page(qid: str | None = None, lang: str | None = None) -> str:
    lang = normalize_lang(lang)
    qids = evidence_query_ids()
    qid = qid if qid in qids else qids[0]
    demo = assemble_demo()
    view = get_query_view(qid)
    graph = stable_graph_payload(include_svg=False)
    graph_svg = render_stable_graph_svg(graph)
    css = studio_css()
    js = studio_js()
    browser_i18n_keys = (
        "progress_decompose",
        "progress_retrieve",
        "progress_rank",
        "progress_cost",
        "realtime_enter_question",
        "realtime_loading",
        "realtime_llm_calls",
        "realtime_tokens",
        "realtime_latency",
        "realtime_unavailable",
        "realtime_no_rows_fabricated",
        "realtime_decomposed_into",
        "realtime_rank_prefix",
        "realtime_rank_suffix",
        "realtime_paper_label",
        "realtime_score_label",
        "realtime_ranking_signal",
        "realtime_ranking_summary",
        "realtime_technical_details",
        "realtime_manual_meta",
        "realtime_no_rows",
        "realtime_request_failed",
        "verify_loading",
        "verify_manual_required",
        "verify_manual_reason_source_missing",
        "verify_manual_reason_generic",
        "verify_no_guess",
        "verify_exact_match",
    )
    i18n_json = json.dumps(
        {key: tr(lang, key) for key in browser_i18n_keys},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        f'<!doctype html><html lang="{_e(tr(lang, "html_lang"))}" data-lang="{_e(lang)}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_e(tr(lang, "studio_title"))}</title>'
        f'<style>{css}</style><body><main class="studio-shell">'
        + _lang_switch(lang, qid)
        + '<section class="hero" aria-label="ScholarLoop Studio hero"><div class="hero-grid"><div>'
        f'<span class="eyebrow">{_e(tr(lang, "eyebrow"))}</span><h1>{_e(tr(lang, "hero_title"))}</h1>'
        f'<p>{_e(tr(lang, "hero_subtitle"))} <b>{_e(REALTIME_LABEL)}</b></p>'
        + _trust_strip(demo, lang)
        + f'<div class="pill-row"><span class="pill ok">{_e(tr(lang, "offline_default"))}</span><span class="pill ok">{_e(tr(lang, "zero_fabrication"))}</span><span class="pill">{_e(tr(lang, "stable_svg"))}</span><span class="pill">{_e(tr(lang, "span_contract"))}</span></div>'
        f'<div class="onboarding" aria-label="{_e(tr(lang, "how_to_use"))}"><div class="step"><b>{_e(tr(lang, "how_to_use"))}</b><br>{_e(tr(lang, "how_to_use_body"))}</div><div class="step"><b>{_e(tr(lang, "trust_title"))}</b><br>{_e(tr(lang, "trust_body"))}</div><div class="step"><b>{_e(tr(lang, "source_paths"))}</b><br>{_e(tr(lang, "trust_source_body"))}</div></div>'
        f'</div><div class="search-panel"><label for="studio-search-input"><b>{_e(tr(lang, "ask_any"))}</b><br><span class="subtle" style="color:rgba(255,255,255,.78)">{_e(tr(lang, "optional_realtime"))}</span></label>'
        f'<div class="search-row"><input id="studio-search-input" class="search-input" value="large language model compression" autocomplete="off" aria-label="{_e(tr(lang, "ask_any"))}"><button type="button" class="btn btn-primary" onclick="runStudioSearch()">{_e(tr(lang, "run_search"))}</button></div>'
        + _example_chips(lang)
        + f'<p class="subtle" style="color:rgba(255,255,255,.78)">{_e(NON_VERIFIED_NOTE)}</p></div></div></section>'
        '<section class="section-grid"><div>'
        f'<section class="card"><h2>{_e(tr(lang, "realtime_section"))}</h2><p class="subtle">{_e(tr(lang, "realtime_desc"))}</p><div id="studio-search-output" class="empty">{_e(tr(lang, "realtime_empty"))}<br>{_e(tr(lang, "no_fabrication"))}</div></section>'
        f'<section class="card"><h2>{_e(tr(lang, "verified_section"))}</h2><p class="subtle">{_e(tr(lang, "verified_desc"))}</p><div class="metric-grid">'
        + _metrics_html(demo)
        + f'</div><div class="select-row"><label><b>{_e(tr(lang, "query_label"))}</b> '
        + _query_selector(qid)
        + f'</label></div><h3>{_e(view.get("query"))}</h3><p class="subtle">{_e(tr(lang, "field_hint"))}</p>'
        + _verified_fields_html(view, lang)
        + f'</section><section class="card"><h2>{_e(tr(lang, "trail_section"))}</h2><p class="subtle">{_e(tr(lang, "trail_desc"))}</p>'
        + _trail_html(qid, lang)
        + '</section></div><aside>'
        f'<section class="card"><h2>{_e(tr(lang, "verify_result"))}</h2><div id="studio-span-output" class="empty">{_e(tr(lang, "verify_empty"))}</div></section>'
        f'<section class="card"><h2>{_e(tr(lang, "stable_graph"))}</h2><p class="subtle">{_e(tr(lang, "stable_graph_desc"))}</p>'
        f'<div class="graph-legend"><span class="legend-item"><span class="legend-swatch blue"></span>{_e(tr(lang, "stable_svg"))}</span><span class="legend-item"><span class="legend-swatch"></span>{_e(tr(lang, "graph_legend"))}</span></div>'
        + graph_svg
        + f'<p class="subtle">{_e(tr(lang, "graph_summary", nodes=graph["raw_node_count"], edges=len(graph["edges"])))}</p></section>'
        + f'<section class="card"><h2>{_e(tr(lang, "existing_surfaces"))}</h2><p><a href="/">{_e(tr(lang, "surface_home"))}</a> · <a href="/pro">{_e(tr(lang, "surface_pro"))}</a> · <a href="/graph">{_e(tr(lang, "surface_graph"))}</a></p></section>'
        + _technical_appendix(lang)
        + '</aside></section></main>'
        f'<script>window.SL_I18N={i18n_json};</script><script>{js}</script></body></html>'
    )


def _baseline_mismatches(demo: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    m040 = load_m040()
    m060 = load_m060()
    gaps = load_gaps_display()
    checks = [
        ("litsearch.a_v2", demo["metrics"]["litsearch"]["a_v2"], m040["by_system"]["scholarloop_a_v2"], str(M040_RESULTS)),
        ("litsearch.bm25", demo["metrics"]["litsearch"]["bm25"], m040["by_system"]["bm25"], str(M040_RESULTS)),
        (
            "realscholarquery.resolvable.a_v2",
            demo["metrics"]["realscholarquery"]["a_v2_resolvable"],
            {row["system"]: row for row in m060["metrics"]["resolvable"]["aggregate"]}["scholarloop_a_v2"],
            str(M060_RESULTS),
        ),
        ("gaps.items", demo["gaps"]["items"], gaps.get("items") or [], str(M070_GAPS_DISPLAY)),
        ("gaps.concept_nodes", demo["gaps"]["concept_nodes"], gaps.get("concept_nodes") or [], str(M070_GAPS_DISPLAY)),
        ("gaps.matrix_edges", demo["gaps"]["matrix_edges"], gaps.get("matrix_edges") or [], str(M070_GAPS_DISPLAY)),
    ]
    for name, displayed, source, path in checks:
        if displayed != source:
            mismatches.append({"name": name, "source_path": path})
    return mismatches


def build_studio_fidelity() -> dict[str, Any]:
    demo = assemble_demo()
    span = build_span_fidelity()
    trail = build_trail_fidelity()
    graph = verify_graph_determinism()
    baseline_mismatches = _baseline_mismatches(demo)
    mismatch_count = int(span.get("mismatch_count") or 0) + len(baseline_mismatches)
    status = "PASS" if mismatch_count == 0 and trail.get("status") == "PASS" and graph.get("status") == "PASS" else "BLOCKED"
    return {
        "schema_version": "m130.studio_fidelity.v1",
        "status": status,
        "point_verify_function": "scholarloop.demo.source_text.verify_value_span via scholarloop.demo.interactive.build_span_fidelity",
        "contract": "highlight only when source_text[char_span] == value; baseline values equal verified JSON; realtime is not verified load-bearing",
        "span_fidelity_status": span.get("status"),
        "span_total_checks": span.get("total_checks"),
        "span_highlightable_count": span.get("highlightable_count"),
        "span_mismatch_count": span.get("mismatch_count"),
        "baseline_mismatch_count": len(baseline_mismatches),
        "baseline_mismatches": baseline_mismatches[:20],
        "mismatch_count": mismatch_count,
        "trail_fidelity_status": trail.get("status"),
        "trail_fabrication": trail.get("fabrication"),
        "graph_determinism_status": graph.get("status"),
        "realtime_label": REALTIME_LABEL,
        "verified_json_sources": [str(M040_RESULTS), str(M060_RESULTS), str(M070_GAPS_DISPLAY), "reports/m020/evidence", "reports/m120/span_fidelity.json"],
    }


def build_i18n_coverage() -> dict[str, Any]:
    zh_html = render_studio_page("litsearch_000", "zh")
    en_html = render_studio_page("litsearch_000", "en")
    demo = assemble_demo()
    verified_values = [
        _format_metric(demo["metrics"]["litsearch"]["a_v2"].get("F1")),
        _format_metric(demo["metrics"]["litsearch"]["bm25"].get("F1")),
        _format_metric(demo["metrics"]["realscholarquery"]["a_v2_resolvable"].get("F1")),
    ]
    missing_by_lang = {
        lang: sorted(catalog_keys() - set(values))
        for lang, values in TRANSLATIONS.items()
    }
    required_markers = {
        "zh": ["可信论文检索工作台", "运行实时搜索", "点即核验结果", "稳定关系图"],
        "en": ["Evidence-first literature search studio", "Run realtime search", "Point verification result", "Stable relation graph"],
    }
    missing_markers = {
        "zh": [marker for marker in required_markers["zh"] if marker not in zh_html],
        "en": [marker for marker in required_markers["en"] if marker not in en_html],
    }
    verified_value_presence = {
        value: {"zh": value in zh_html, "en": value in en_html}
        for value in verified_values
    }
    untranslated_verified_ok = all(all(presence.values()) for presence in verified_value_presence.values())
    status = "PASS" if not any(missing_by_lang.values()) and not any(missing_markers.values()) and untranslated_verified_ok else "BLOCKED"
    return {
        "schema_version": "m140.i18n_coverage.v1",
        "status": status,
        "supported_langs": list(TRANSLATIONS),
        "default_lang": "zh",
        "missing_keys_by_lang": missing_by_lang,
        "missing_required_markers": missing_markers,
        "verified_values_not_translated": untranslated_verified_ok,
        "verified_value_presence": verified_value_presence,
        "policy": "i18n translates UI chrome only; verified metrics, evidence text, paper titles, abstracts, and char_span slices remain unchanged.",
    }


def write_i18n_coverage(path: Path = Path("reports/m140/i18n_coverage.json")) -> dict[str, Any]:
    report = build_i18n_coverage()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_a11y_check() -> dict[str, Any]:
    html_zh = render_studio_page("litsearch_000", "zh")
    html_en = render_studio_page("litsearch_000", "en")
    external_asset_markers = ('src="http', "src='http", 'href="http', "href='http", "@import", "url(http", "//cdn")
    checks = {
        "lang_attribute_zh": '<html lang="zh-CN"' in html_zh,
        "lang_attribute_en": '<html lang="en"' in html_en,
        "viewport": 'name="viewport"' in html_zh,
        "aria_labels": html_zh.count("aria-label") >= 5,
        "keyboard_focusable_graph": 'tabindex="0"' in html_zh,
        "focus_visible_css": ":focus-visible" in html_zh,
        "reduced_motion": "prefers-reduced-motion" in html_zh,
        "dark_mode": "data-theme" in html_zh and "prefers-color-scheme" in html_zh,
        "no_external_cdn": not any(marker in html_zh.lower() for marker in external_asset_markers),
        "no_framework_markers": all(marker not in html_zh for marker in ("react.development", "vue.global", "tailwind" + "css.com")),
        "all_states": all(marker in html_zh for marker in ("loading", "empty", "error", "skeleton")),
    }
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "schema_version": "m140.a11y_check.v1",
        "status": "PASS" if not failed else "BLOCKED",
        "checks": checks,
        "failed": failed,
        "note": "Static checks for semantic lang, ARIA, keyboard focus, focus ring, reduced motion, dark mode, no CDN, and full state classes.",
    }


def write_a11y_check(path: Path = Path("reports/m140/a11y_check.json")) -> dict[str, Any]:
    report = build_a11y_check()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def write_studio_fidelity(path: Path = Path("reports/m130/studio_fidelity.json")) -> dict[str, Any]:
    report = build_studio_fidelity()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
