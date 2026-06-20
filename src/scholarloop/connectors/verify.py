from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .base import format_authors_year, format_source_or_doi
from .cache import ResponseCache
from .openalex import OpenAlexConnector
from .resolver import AUTHOR_YEAR_FIELD, SOURCE_DOI_FIELD, crossref_smoke_from_enriched


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.glob("*.json")):
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        out[path.name] = h
    return out


def find_openalex_raw(cache_path: str, external_id: str) -> dict[str, Any] | None:
    entry = ResponseCache().read_path(cache_path)
    body = entry.body_json
    if isinstance(body, dict) and body.get("id") == external_id:
        return body
    for item in (body or {}).get("results") or []:
        if item.get("id") == external_id:
            return item
    return None


def verify_enriched(enriched_dir: Path = Path("reports/m050/enriched")) -> dict[str, Any]:
    files = sorted(enriched_dir.glob("*.json"))
    checks: list[dict[str, Any]] = []
    total_cards = resolved_cards = resolved_fields = manual_fields = fabricated = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for card in data.get("cards") or []:
            total_cards += 1
            meta = card.get("m050_external_metadata")
            if meta:
                resolved_cards += 1
            for key in (AUTHOR_YEAR_FIELD, SOURCE_DOI_FIELD):
                field = (card.get("fields") or {}).get(key) or {}
                if field.get("status") == "已有外部来源支持":
                    resolved_fields += 1
                    prov = field.get("external_provenance") or {}
                    missing = [name for name in ("source", "external_id", "fetched_at", "license", "cache_path") if not prov.get(name)]
                    if missing:
                        fabricated += 1
                        checks.append({"ok": False, "path": str(path), "corpusid": card.get("corpusid"), "field": key, "reason": f"missing provenance: {missing}"})
                        continue
                    if prov["source"] != "openalex":
                        fabricated += 1
                        checks.append({"ok": False, "path": str(path), "corpusid": card.get("corpusid"), "field": key, "reason": "unexpected source"})
                        continue
                    raw = find_openalex_raw(prov["cache_path"], prov["external_id"])
                    if raw is None:
                        fabricated += 1
                        checks.append({"ok": False, "path": str(path), "corpusid": card.get("corpusid"), "field": key, "reason": "external_id not found in cache"})
                        continue
                    entry = ResponseCache().read_path(prov["cache_path"])
                    record = OpenAlexConnector.parse_work(raw, entry)
                    expected = format_authors_year(record) if key == AUTHOR_YEAR_FIELD else format_source_or_doi(record)
                    ok = field.get("value") == expected and expected != ""
                    if not ok:
                        fabricated += 1
                    checks.append({"ok": ok, "path": str(path), "corpusid": card.get("corpusid"), "field": key, "expected": expected, "actual": field.get("value"), "external_id": prov["external_id"]})
                elif field.get("status") == "需人工核验":
                    manual_fields += 1
                    if "m050_resolution_attempt" in field and field["m050_resolution_attempt"].get("strong_match"):
                        fabricated += 1
                        checks.append({"ok": False, "path": str(path), "corpusid": card.get("corpusid"), "field": key, "reason": "strong match was not resolved"})
    return {
        "files": len(files),
        "total_cards": total_cards,
        "resolved_cards": resolved_cards,
        "resolved_fields": resolved_fields,
        "manual_fields_preserved": manual_fields,
        "field_resolution_rate": resolved_fields / max(1, resolved_fields + manual_fields),
        "fabricated_count": fabricated,
        "zero_fabrication": fabricated == 0,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enriched-dir", default="reports/m050/enriched")
    parser.add_argument("--cache-dir", default="reports/m050/cache")
    parser.add_argument("--offline-replay-dir", default="reports/m050/enriched_replay")
    parser.add_argument("--skip-crossref-smoke", action="store_true")
    args = parser.parse_args(argv)
    enriched_dir = Path(args.enriched_dir)
    verification = verify_enriched(enriched_dir)
    verification["cache_replay"] = {
        "enriched_hashes": sha256_tree(enriched_dir),
        "offline_replay_hashes": sha256_tree(Path(args.offline_replay_dir)) if Path(args.offline_replay_dir).exists() else {},
    }
    verification["cache_replay"]["offline_replay_equals_enriched"] = (
        bool(verification["cache_replay"]["offline_replay_hashes"])
        and verification["cache_replay"]["offline_replay_hashes"] == verification["cache_replay"]["enriched_hashes"]
    )
    if args.skip_crossref_smoke:
        verification["crossref_smoke"] = {"status": "skipped"}
    else:
        verification["crossref_smoke"] = crossref_smoke_from_enriched(enriched_dir, Path(args.cache_dir), offline=False)
    verification["passed"] = (
        verification["zero_fabrication"]
        and verification["files"] > 0
        and verification["resolved_fields"] > 0
        and verification["cache_replay"]["offline_replay_equals_enriched"]
        and verification["crossref_smoke"].get("status") in {"ok", "skipped_no_resolved_doi"}
    )
    write_json(Path("reports/m050/verification.json"), verification)
    print(json.dumps({k: verification[k] for k in ["passed", "files", "resolved_fields", "manual_fields_preserved", "fabricated_count", "crossref_smoke"]}, ensure_ascii=False, indent=2))
    return 0 if verification["passed"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
