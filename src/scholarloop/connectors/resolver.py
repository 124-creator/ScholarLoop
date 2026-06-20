from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import scholarloop.config as config  # noqa: F401 - approved self-load path; keys are never printed

from .base import WorkMetadata, format_authors_year, format_source_or_doi, title_match
from .cache import ResponseCache
from .crossref import CrossrefConnector
from .openalex import OpenAlexConnector
from .base import AcademicHttpClient


AUTHOR_YEAR_FIELD = "authors_year"
SOURCE_DOI_FIELD = "source_or_doi"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def needs_online_resolution(field: dict[str, Any]) -> bool:
    return (
        field.get("status") == "需人工核验"
        and field.get("resolution_hint") == "online_connector_required_for_author_year_source_doi"
    )


def field_provenance(record: WorkMetadata) -> dict[str, str]:
    return record.provenance.to_dict()


def resolved_field(original: dict[str, Any], value: str, record: WorkMetadata, confidence: float) -> dict[str, Any]:
    out = deepcopy(original)
    out["value"] = value
    out["status"] = "已有外部来源支持"
    out["source_field"] = "external_metadata"
    out["char_span"] = None
    out["confidence"] = float(confidence)
    out["external_provenance"] = field_provenance(record)
    out["resolution_hint"] = None
    return out


def unresolved_field(original: dict[str, Any], *, attempt: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(original)
    out["m050_resolution_attempt"] = attempt
    return out


def enrich_card_with_record(card: dict[str, Any], record: WorkMetadata, *, min_title_score: float = 0.94, min_token_jaccard: float = 0.80) -> tuple[dict[str, Any], dict[str, Any]]:
    title = (card.get("fields") or {}).get("title", {}).get("value") or ""
    match = title_match(title, record.title, threshold=min_title_score, token_threshold=min_token_jaccard)
    enriched = deepcopy(card)
    fields = enriched.setdefault("fields", {})
    attempt = {
        "source": record.source,
        "external_id": record.external_id,
        "candidate_title": record.title,
        "title_score": match.normalized_score,
        "title_token_jaccard": match.token_jaccard,
        "strong_match": match.strong,
        "threshold": {"normalized_score": min_title_score, "token_jaccard": min_token_jaccard},
    }
    if not match.strong:
        for key in (AUTHOR_YEAR_FIELD, SOURCE_DOI_FIELD):
            if key in fields and needs_online_resolution(fields[key]):
                fields[key] = unresolved_field(fields[key], attempt=attempt)
        enriched["m050_external_metadata"] = None
        return enriched, {"resolved": False, "reason": "title_match_below_threshold", **attempt}

    record_public = record.to_public_dict()
    record_public["title_match"] = match.to_dict()
    enriched["m050_external_metadata"] = record_public
    resolved_fields = 0
    if AUTHOR_YEAR_FIELD in fields and needs_online_resolution(fields[AUTHOR_YEAR_FIELD]):
        value = format_authors_year(record)
        if value:
            fields[AUTHOR_YEAR_FIELD] = resolved_field(fields[AUTHOR_YEAR_FIELD], value, record, match.normalized_score)
            resolved_fields += 1
    if SOURCE_DOI_FIELD in fields and needs_online_resolution(fields[SOURCE_DOI_FIELD]):
        value = format_source_or_doi(record)
        if value:
            fields[SOURCE_DOI_FIELD] = resolved_field(fields[SOURCE_DOI_FIELD], value, record, match.normalized_score)
            resolved_fields += 1
    return enriched, {"resolved": resolved_fields > 0, "resolved_fields": resolved_fields, **attempt}


def choose_openalex_record(records: list[WorkMetadata], title: str, *, min_title_score: float, min_token_jaccard: float) -> WorkMetadata | None:
    if not records:
        return None
    best = records[0]
    match = title_match(title, best.title, threshold=min_title_score, token_threshold=min_token_jaccard)
    if not match.strong:
        return best  # Returned as attempted candidate; caller will preserve manual fields.
    return best


def resolve_evidence_file(
    path: Path,
    output_dir: Path,
    openalex: OpenAlexConnector,
    *,
    min_title_score: float = 0.94,
    min_token_jaccard: float = 0.80,
    force_live: bool = False,
) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    enriched = deepcopy(data)
    enriched["schema_version"] = "m050.enriched_query_evidence.v1"
    enriched.setdefault("source", {})["m050_enrichment"] = {
        "upstream_m020": str(path),
        "upstream_read_only": True,
        "primary_connector": "openalex",
        "min_title_score": min_title_score,
        "min_token_jaccard": min_token_jaccard,
    }
    stats = {"query_id": data.get("query_id"), "cards": 0, "resolved_cards": 0, "resolved_fields": 0, "manual_fields_preserved": 0}
    new_cards = []
    for card in data.get("cards") or []:
        stats["cards"] += 1
        fields = card.get("fields") or {}
        title = (fields.get("title") or {}).get("value") or ""
        target_fields = [key for key in (AUTHOR_YEAR_FIELD, SOURCE_DOI_FIELD) if key in fields and needs_online_resolution(fields[key])]
        if not title or not target_fields:
            new_cards.append(card)
            continue
        records = openalex.search_title(title, max_results=5, force_live=force_live)
        candidate = choose_openalex_record(records, title, min_title_score=min_title_score, min_token_jaccard=min_token_jaccard)
        if candidate is None:
            attempt = {"source": "openalex", "candidate_title": "", "title_score": 0.0, "title_token_jaccard": 0.0, "strong_match": False}
            new_card = deepcopy(card)
            for key in target_fields:
                new_card["fields"][key] = unresolved_field(new_card["fields"][key], attempt=attempt)
                stats["manual_fields_preserved"] += 1
            new_cards.append(new_card)
            continue
        new_card, result = enrich_card_with_record(card, candidate, min_title_score=min_title_score, min_token_jaccard=min_token_jaccard)
        if result.get("resolved"):
            stats["resolved_cards"] += 1
            stats["resolved_fields"] += int(result.get("resolved_fields") or 0)
        else:
            stats["manual_fields_preserved"] += len(target_fields)
        new_cards.append(new_card)
    enriched["cards"] = new_cards
    out_path = output_dir / path.name
    write_json(out_path, enriched)
    stats["output_path"] = str(out_path)
    return stats


def run_resolver(
    *,
    evidence_dir: Path = Path("reports/m020/evidence"),
    output_dir: Path = Path("reports/m050/enriched"),
    cache_dir: Path = Path("reports/m050/cache"),
    offline: bool = False,
    force_live: bool = False,
    min_title_score: float = 0.94,
    min_token_jaccard: float = 0.80,
    limit: int | None = None,
) -> dict[str, Any]:
    cache = ResponseCache(cache_dir)
    client = AcademicHttpClient(cache=cache, offline=offline, min_interval_s=0.25)
    openalex = OpenAlexConnector(client)
    files = sorted(evidence_dir.glob("*.json"))
    if limit is not None:
        files = files[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)
    per_file = [
        resolve_evidence_file(
            p,
            output_dir,
            openalex,
            min_title_score=min_title_score,
            min_token_jaccard=min_token_jaccard,
            force_live=force_live,
        )
        for p in files
    ]
    total_cards = sum(x["cards"] for x in per_file)
    resolved_cards = sum(x["resolved_cards"] for x in per_file)
    resolved_fields = sum(x["resolved_fields"] for x in per_file)
    manual = sum(x["manual_fields_preserved"] for x in per_file)
    summary = {
        "schema_version": "m050.resolver_summary.v1",
        "offline": offline,
        "files": len(files),
        "total_cards": total_cards,
        "resolved_cards": resolved_cards,
        "resolved_fields": resolved_fields,
        "manual_fields_preserved": manual,
        "card_resolution_rate": resolved_cards / total_cards if total_cards else 0.0,
        "min_title_score": min_title_score,
        "min_token_jaccard": min_token_jaccard,
        "per_file": per_file,
    }
    write_json(output_dir.parent / ("resolver_summary_offline.json" if offline else "resolver_summary.json"), summary)
    return summary


def crossref_smoke_from_enriched(enriched_dir: Path, cache_dir: Path, *, offline: bool = False) -> dict[str, Any]:
    cache = ResponseCache(cache_dir)
    client = AcademicHttpClient(cache=cache, offline=offline, min_interval_s=0.35)
    crossref = CrossrefConnector(client)
    failures: list[dict[str, str]] = []
    for path in sorted(enriched_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for card in data.get("cards") or []:
            meta = card.get("m050_external_metadata") or {}
            doi = meta.get("doi") or ""
            if not doi:
                continue
            try:
                record = crossref.by_doi(doi)
            except Exception as exc:
                failures.append({"doi": doi, "error": type(exc).__name__})
                continue
            return {
                "status": "ok" if record else "not_found",
                "doi": doi,
                "source": "crossref",
                "external_id": record.external_id if record else "",
                "title": record.title if record else "",
                "cache_path": record.cache_path if record else "",
                "prior_failures": failures[:5],
            }
    return {"status": "skipped_no_resolved_doi", "source": "crossref", "prior_failures": failures[:5]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default="reports/m020/evidence")
    parser.add_argument("--output-dir", default="reports/m050/enriched")
    parser.add_argument("--cache-dir", default="reports/m050/cache")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--force-live", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-title-score", type=float, default=0.94)
    parser.add_argument("--min-token-jaccard", type=float, default=0.80)
    args = parser.parse_args(argv)
    summary = run_resolver(
        evidence_dir=Path(args.evidence_dir),
        output_dir=Path(args.output_dir),
        cache_dir=Path(args.cache_dir),
        offline=args.offline,
        force_live=args.force_live,
        min_title_score=args.min_title_score,
        min_token_jaccard=args.min_token_jaccard,
        limit=args.limit,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
