from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(".")
M020_EVIDENCE_DIR = ROOT / "reports" / "m020" / "evidence"
M040_RESULTS = ROOT / "reports" / "m040" / "results.json"
M050_REPLAY_DIR = ROOT / "reports" / "m050" / "enriched_replay"
M050_DATA_SOURCES = ROOT / "reports" / "m050" / "data-sources.md"
M060_RESULTS = ROOT / "reports" / "m060" / "results.json"
M060_SIGNIFICANCE = ROOT / "reports" / "m060" / "significance.json"
M070_RESULTS = ROOT / "reports" / "m070" / "results.json"
M070_SIGNIFICANCE = ROOT / "reports" / "m070" / "significance.json"
M070_GAPS_DISPLAY = ROOT / "reports" / "m070" / "gaps_display.json"

MISSING_PLACEHOLDER = "需人工核验（verified JSON 未提供；不补写）"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy(data: Any) -> Any:
    return copy.deepcopy(data)


@lru_cache(maxsize=1)
def load_m040() -> dict[str, Any]:
    return read_json(M040_RESULTS)


@lru_cache(maxsize=1)
def load_m060() -> dict[str, Any]:
    return read_json(M060_RESULTS)


@lru_cache(maxsize=1)
def load_m060_significance() -> dict[str, Any]:
    return read_json(M060_SIGNIFICANCE)


@lru_cache(maxsize=1)
def load_m070() -> dict[str, Any]:
    return read_json(M070_RESULTS)


@lru_cache(maxsize=1)
def load_m070_significance() -> dict[str, Any]:
    return read_json(M070_SIGNIFICANCE)


@lru_cache(maxsize=1)
def load_gaps_display() -> dict[str, Any]:
    return read_json(M070_GAPS_DISPLAY)


@lru_cache(maxsize=1)
def m040_by_query() -> dict[str, dict[str, Any]]:
    return {str(item["query_id"]): item for item in load_m040().get("per_query", [])}


@lru_cache(maxsize=None)
def load_evidence(qid: str) -> dict[str, Any]:
    path = M020_EVIDENCE_DIR / f"{qid}.json"
    if not path.exists():
        raise KeyError(f"M020 evidence not found for query_id={qid}")
    return read_json(path)


@lru_cache(maxsize=None)
def load_enriched(qid: str) -> dict[str, Any]:
    path = M050_REPLAY_DIR / f"{qid}.json"
    if not path.exists():
        raise KeyError(f"M050 enriched replay not found for query_id={qid}")
    return read_json(path)


@lru_cache(maxsize=1)
def evidence_query_ids() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in M020_EVIDENCE_DIR.glob("*.json")))


def _reason_map(m040_query: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = m040_query.get("scholarloop_a_v2_reasons_top5") or []
    return {int(row["corpusid"]): dict(row) for row in rows if "corpusid" in row}


def _ranking_panel(qid: str, evidence: dict[str, Any], m040_query: dict[str, Any]) -> dict[str, Any]:
    system = m040_query.get("scholarloop_a_v2") or {}
    ranked = [int(x) for x in system.get("ranked_top20", [])]
    gold = {int(x) for x in m040_query.get("gold", [])}
    evidence_ids = {int(card["corpusid"]) for card in evidence.get("cards", [])}
    reason_by_id = _reason_map(m040_query)
    rows: list[dict[str, Any]] = []
    for rank, cid in enumerate(ranked, start=1):
        reason = reason_by_id.get(cid)
        if cid in gold:
            relation_label = "高度相关（LitSearch gold 命中）"
        elif cid in evidence_ids:
            relation_label = "部分相关展示位（有证据卡；非官方 gold 命中）"
        else:
            relation_label = "未命中 gold；不补写相关性"
        rows.append(
            {
                "rank": rank,
                "corpusid": cid,
                "relation_label": relation_label,
                "in_gold": cid in gold,
                "has_evidence_card": cid in evidence_ids,
                "score": None if reason is None else reason.get("score"),
                "reason": None if reason is None else reason.get("reason"),
                "source_path": str(M040_RESULTS),
                "source_json_pointer": f"per_query[{qid}].scholarloop_a_v2.ranked_top20[{rank - 1}]",
            }
        )
    return {
        "system": "scholarloop_a_v2",
        "source_path": str(M040_RESULTS),
        "ranked_top20": ranked,
        "metrics": {
            "P@10": system.get("P@10"),
            "R@20": system.get("R@20"),
            "F1": system.get("F1"),
            "NDCG@20": system.get("NDCG@20"),
        },
        "gold": sorted(gold),
        "rows": rows,
        "top5_reasons_source": _copy(m040_query.get("scholarloop_a_v2_reasons_top5") or []),
    }


def _enrichment_panel(enriched: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for card in enriched.get("cards", []):
        fields = card.get("fields") or {}
        title = fields.get("title") or {}
        authors = fields.get("authors_year") or {}
        source = fields.get("source_or_doi") or {}
        rows.append(
            {
                "corpusid": int(card["corpusid"]),
                "title": title.get("value") or "",
                "authors_year": {
                    "value": authors.get("value") or "",
                    "status": authors.get("status"),
                    "display": authors.get("value") or MISSING_PLACEHOLDER,
                    "external_provenance": _copy(authors.get("external_provenance")),
                    "resolution_hint": authors.get("resolution_hint"),
                },
                "source_or_doi": {
                    "value": source.get("value") or "",
                    "status": source.get("status"),
                    "display": source.get("value") or MISSING_PLACEHOLDER,
                    "external_provenance": _copy(source.get("external_provenance")),
                    "resolution_hint": source.get("resolution_hint"),
                },
            }
        )
    return {
        "source_path": str(M050_REPLAY_DIR / f"{enriched.get('query_id')}.json"),
        "source_mode": "offline_replay",
        "cards": rows,
        "raw_cards": _copy(enriched.get("cards") or []),
    }


def _query_view(qid: str) -> dict[str, Any]:
    evidence = load_evidence(qid)
    enriched = load_enriched(qid)
    m040_query = m040_by_query().get(qid)
    if m040_query is None:
        raise KeyError(f"M040 per_query not found for query_id={qid}")
    return {
        "schema_version": "m080.integrated_query_view.v1",
        "query_id": qid,
        "query": evidence.get("query") or "",
        "decomposition": _copy(m040_query.get("decomposition_from_m010") or evidence.get("criteria") or []),
        "official_function_map": {
            "query_understanding": "decomposition",
            "search_strategy_iteration": "A-v2 uses query decomposition plus multi-source candidate fusion from M040; no live LLM in demo",
            "ranking": "ranking",
            "structured_summary": "evidence + enrichment + gaps",
        },
        "ranking": _ranking_panel(qid, evidence, m040_query),
        "evidence": {
            "source_path": str(M020_EVIDENCE_DIR / f"{qid}.json"),
            "criteria": _copy(evidence.get("criteria") or []),
            "cards": _copy(evidence.get("cards") or []),
            "matrix": _copy(evidence.get("matrix") or []),
            "citation_graph": _copy(evidence.get("citation_graph") or {}),
        },
        "enrichment": _enrichment_panel(enriched),
        "render_contract": {
            "offline": True,
            "llm_calls_per_request": 0,
            "realtime_connectors_enabled": False,
            "missing_field_policy": MISSING_PLACEHOLDER,
            "no_new_metrics": True,
        },
    }


def _metrics_summary() -> dict[str, Any]:
    m040 = load_m040()
    m060 = load_m060()
    m070_sig = load_m070_significance()
    lit_a = m040["by_system"]["scholarloop_a_v2"]
    lit_bm25 = m040["by_system"]["bm25"]
    lit_no_rerank = m040["by_system"]["scholarloop_a_v2_no_rerank"]
    rsq_res = {row["system"]: row for row in m060["metrics"]["resolvable"]["aggregate"]}
    rsq_full = {row["system"]: row for row in m060["metrics"]["full791"]["aggregate"]}
    return {
        "litsearch": {
            "source_path": str(M040_RESULTS),
            "a_v2": _copy(lit_a),
            "bm25": _copy(lit_bm25),
            "a_v2_no_rerank": _copy(lit_no_rerank),
            "a_v2_delta_vs_bm25_f1": lit_a["F1"] - lit_bm25["F1"],
            "cross_encoder_delta_f1_vs_no_rerank": lit_a["F1"] - lit_no_rerank["F1"],
            "cross_encoder_delta_ndcg_vs_no_rerank": lit_a["NDCG@20"] - lit_no_rerank["NDCG@20"],
            "efficiency": _copy(m040.get("efficiency") or {}),
            "protocol": {
                "dense_model": m040.get("protocol", {}).get("dense_model"),
                "rerank_model": m040.get("protocol", {}).get("rerank_model"),
                "final_weights": _copy(m040.get("protocol", {}).get("final_weights")),
                "temperature": m040.get("protocol", {}).get("temperature"),
                "seed": m040.get("protocol", {}).get("seed"),
            },
        },
        "realscholarquery": {
            "source_path": str(M060_RESULTS),
            "a_v2_resolvable": _copy(rsq_res["scholarloop_a_v2"]),
            "bm25_resolvable": _copy(rsq_res["bm25"]),
            "a_v2_no_rerank_resolvable": _copy(rsq_res["scholarloop_a_v2_no_rerank"]),
            "a_v2_full791": _copy(rsq_full["scholarloop_a_v2"]),
            "bm25_full791": _copy(rsq_full["bm25"]),
            "a_v2_delta_vs_bm25_resolvable_f1": rsq_res["scholarloop_a_v2"]["F1"] - rsq_res["bm25"]["F1"],
            "significance": load_m060_significance(),
            "efficiency": _copy(m060.get("efficiency") or {}),
            "cross_encoder_second_benchmark_note": "M060 reports A-v2 and no-rerank rows, but did not run a separate cross-encoder-only ablation on the second benchmark.",
        },
        "research_gaps": {
            "source_path": str(M070_SIGNIFICANCE),
            "prediction_vs_random": _copy(m070_sig["gap_prediction_vs_random"]),
            "claim_boundary": "(高活跃·零历史共现)组合空白填补率显著高于随机概念对；未声称剥离所有频率效应。",
        },
    }


@lru_cache(maxsize=1)
def assemble_demo() -> dict[str, Any]:
    qids = evidence_query_ids()
    queries = [_query_view(qid) for qid in qids]
    gaps = load_gaps_display()
    return {
        "schema_version": "m080.integrated_demo.v1",
        "mode": "offline_zero_llm",
        "llm_calls_per_request": 0,
        "source_paths": {
            "m020_evidence_dir": str(M020_EVIDENCE_DIR),
            "m040_results": str(M040_RESULTS),
            "m050_enriched_replay_dir": str(M050_REPLAY_DIR),
            "m050_data_sources": str(M050_DATA_SOURCES),
            "m060_results": str(M060_RESULTS),
            "m060_significance": str(M060_SIGNIFICANCE),
            "m070_results": str(M070_RESULTS),
            "m070_significance": str(M070_SIGNIFICANCE),
            "m070_gaps_display": str(M070_GAPS_DISPLAY),
        },
        "official_3_1_coverage": [
            {"function": "查询理解与分解", "panel": "decomposition"},
            {"function": "自主搜索策略迭代优化", "panel": "A-v2 decomposition + multi-source fusion protocol"},
            {"function": "论文综合排序", "panel": "ranking"},
            {"function": "搜索结果归纳整理", "panel": "evidence matrix + enrichment + research gaps"},
        ],
        "metrics": _metrics_summary(),
        "queries": queries,
        "gaps": {
            "source_path": str(M070_GAPS_DISPLAY),
            "format": gaps.get("format"),
            "s5_status_values": _copy(gaps.get("s5_status_values") or []),
            "items": _copy(gaps.get("items") or []),
            "concept_nodes": _copy(gaps.get("concept_nodes") or []),
            "matrix_edges": _copy(gaps.get("matrix_edges") or []),
        },
    }


def list_query_summaries() -> list[dict[str, Any]]:
    demo = assemble_demo()
    return [
        {
            "query_id": q["query_id"],
            "query": q["query"],
            "decomposition_count": len(q["decomposition"]),
            "ranking_count": len(q["ranking"]["ranked_top20"]),
            "evidence_card_count": len(q["evidence"]["cards"]),
            "enriched_card_count": len(q["enrichment"]["cards"]),
        }
        for q in demo["queries"]
    ]


def get_query_view(qid: str) -> dict[str, Any]:
    for query in assemble_demo()["queries"]:
        if query["query_id"] == qid:
            return _copy(query)
    raise KeyError(f"Unknown query_id={qid}")

