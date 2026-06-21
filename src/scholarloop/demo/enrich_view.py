from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

M050_ENRICHED_DIR = Path("reports") / "m050" / "enriched"
ENRICHED_FIELDS = ("authors_year", "source_or_doi")

FIELD_LABELS = {
    "title": {"zh": "论文标题", "en": "Paper title"},
    "recommendation_reason": {"zh": "推荐理由", "en": "Why it is recommended"},
    "supported_research_question": {"zh": "支撑的问题", "en": "Question supported"},
    "method": {"zh": "方法", "en": "Method"},
    "data_or_scenario": {"zh": "数据/场景", "en": "Data or scenario"},
    "main_conclusion": {"zh": "主要结论", "en": "Main conclusion"},
    "limitations": {"zh": "局限", "en": "Limitations"},
    "authors_year": {"zh": "作者与年份", "en": "Authors and year"},
    "source_or_doi": {"zh": "来源与 DOI", "en": "Source and DOI"},
}

STATUS_LABELS = {
    "已有证据支持": {"zh": "原文支持", "en": "Supported by source text"},
    "存在争议": {"zh": "有边界/争议", "en": "Bounded or disputed"},
    "已有外部来源支持": {"zh": "OpenAlex 核验", "en": "Checked via OpenAlex"},
}

MANUAL_REVIEW_TEXT = {
    "zh": "该字段暂无已核验外部来源，保留为人工核验，不补写、不猜测。",
    "en": "No verified external source is available for this field; it remains for manual review and is not guessed.",
}


def _lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def field_label(field_name: str, lang: str | None = None) -> str:
    return FIELD_LABELS.get(field_name, {}).get(_lang(lang), field_name)


def status_label(status: str | None, lang: str | None = None) -> str:
    if not status:
        return {"zh": "需人工核验", "en": "Manual review"}[_lang(lang)]
    return STATUS_LABELS.get(status, {}).get(_lang(lang), status)


@lru_cache(maxsize=None)
def load_m050_enriched(qid: str) -> dict[str, Any]:
    path = M050_ENRICHED_DIR / f"{qid}.json"
    if not path.exists():
        return {"query_id": qid, "cards": [], "missing": True, "source_path": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source_path"] = str(path)
    return data


@lru_cache(maxsize=None)
def _card_lookup(qid: str) -> dict[int, dict[str, Any]]:
    data = load_m050_enriched(qid)
    return {int(card["corpusid"]): card for card in data.get("cards", []) if "corpusid" in card}


def m050_field(qid: str, corpusid: int, field_name: str) -> dict[str, Any] | None:
    card = _card_lookup(qid).get(int(corpusid))
    if card is None:
        return None
    field = (card.get("fields") or {}).get(field_name)
    return dict(field) if isinstance(field, dict) else None


def display_field_from_m050(qid: str, corpusid: int, field_name: str, lang: str | None = None) -> dict[str, Any]:
    """Return a display-safe field model backed only by M050 cached metadata.

    No online connector is called here. A populated value is surfaced exactly as
    it appears in `reports/m050/enriched/<qid>.json`; missing values remain an
    explicit manual-review placeholder.
    """

    field = m050_field(qid, corpusid, field_name)
    value = (field or {}).get("value")
    provenance = (field or {}).get("external_provenance") or {}
    if value:
        source = provenance.get("source") or "external cache"
        return {
            "field": field_name,
            "label": field_label(field_name, lang),
            "value": value,
            "display_value": value,
            "status": (field or {}).get("status") or "已有外部来源支持",
            "display_status": status_label((field or {}).get("status") or "已有外部来源支持", lang),
            "badge": "OpenAlex verified" if source == "openalex" else f"{source} verified",
            "external_provenance": provenance,
            "matched_m050": True,
            "manual_review": False,
            "fabricated": False,
            "source_path": str(M050_ENRICHED_DIR / f"{qid}.json"),
        }
    return {
        "field": field_name,
        "label": field_label(field_name, lang),
        "value": "",
        "display_value": MANUAL_REVIEW_TEXT[_lang(lang)],
        "status": "需人工核验",
        "display_status": status_label(None, lang),
        "badge": "No verified external cache",
        "external_provenance": (field or {}).get("external_provenance"),
        "matched_m050": False,
        "manual_review": True,
        "fabricated": False,
        "source_path": str(M050_ENRICHED_DIR / f"{qid}.json"),
    }


def audit_m050_display(query_views: list[dict[str, Any]], visible_cards_per_query: int = 3) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    matched = 0
    manual = 0
    mismatches: list[dict[str, Any]] = []
    for view in query_views:
        qid = str(view["query_id"])
        for card in (view.get("evidence", {}).get("cards") or [])[:visible_cards_per_query]:
            corpusid = int(card["corpusid"])
            for field_name in ENRICHED_FIELDS:
                display = display_field_from_m050(qid, corpusid, field_name, "zh")
                cached = m050_field(qid, corpusid, field_name) or {}
                cached_value = cached.get("value") or ""
                row = {
                    "query_id": qid,
                    "corpusid": corpusid,
                    "field": field_name,
                    "display_value": display["value"] if display["matched_m050"] else "",
                    "cached_value": cached_value,
                    "matched_m050": display["matched_m050"],
                    "manual_review": display["manual_review"],
                    "source_path": display["source_path"],
                    "external_source": (display.get("external_provenance") or {}).get("source"),
                }
                if display["matched_m050"]:
                    matched += 1
                    if display["value"] != cached_value:
                        mismatches.append(row)
                else:
                    manual += 1
                    if cached_value:
                        mismatches.append(row)
                rows.append(row)
    return {
        "schema_version": "m160.fabrication_zero.v1",
        "status": "PASS" if not mismatches else "BLOCKED",
        "source_dir": str(M050_ENRICHED_DIR),
        "field_names": list(ENRICHED_FIELDS),
        "visible_cards_per_query": visible_cards_per_query,
        "checked_field_count": len(rows),
        "m050_matched_count": matched,
        "manual_review_count": manual,
        "fabricated": 0,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
        "rows": rows,
        "policy": "Display values for authors_year/source_or_doi are exact copies from M050 cache; unresolved fields stay manual-review placeholders.",
    }
