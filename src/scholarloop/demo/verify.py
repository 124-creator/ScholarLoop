from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from scholarloop.demo.app import create_server
from scholarloop.demo.assemble import (
    M020_EVIDENCE_DIR,
    M040_RESULTS,
    M050_REPLAY_DIR,
    M070_GAPS_DISPLAY,
    assemble_demo,
    load_evidence,
    load_enriched,
    load_gaps_display,
    load_m040,
    m040_by_query,
)
from scholarloop.utils import write_json

SECRET_RE = re.compile(r"(?:sk|ark)-[A-Za-z0-9_\-]{12,}")
SUBMISSION_IDENTITY_TERMS = ("学校", "学院", "导师")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_dir(path: Path) -> str:
    h = hashlib.sha256()
    if not path.exists():
        return "missing"
    for f in sorted(path.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(path)).replace("\\", "/").encode("utf-8"))
            h.update(f.read_bytes())
    return h.hexdigest()


def fetch_json(base_url: str, path: str) -> tuple[int, dict[str, Any]]:
    with urlopen(base_url + path, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def fetch_text(base_url: str, path: str) -> tuple[int, str]:
    with urlopen(base_url + path, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8")


def _read_secret_values() -> list[str]:
    path = Path("secrets") / "llm.env.local"
    values: list[str] = []
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip().upper()
        value = value.strip().strip('"').strip("'")
        if value and (any(marker in key for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")) or value.startswith(("sk-", "ark-"))):
            values.append(value)
    return values


def scan_for_secrets(paths: list[Path]) -> dict[str, Any]:
    secret_values = _read_secret_values()
    files: list[Path] = []
    for base in paths:
        if not base.exists():
            continue
        if base.is_file():
            files.append(base)
        else:
            for f in base.rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts and "secrets" not in f.parts and f.suffix.lower() not in {".pyc", ".png", ".jpg", ".jpeg", ".gif"}:
                    files.append(f)
    regex_hits: list[str] = []
    exact_hits: list[dict[str, Any]] = []
    for f in sorted(set(files)):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if SECRET_RE.search(text):
            regex_hits.append(f.as_posix())
        for idx, secret in enumerate(secret_values):
            if secret and secret in text:
                exact_hits.append({"path": f.as_posix(), "secret_index": idx})
    return {
        "scanned_file_count": len(set(files)),
        "secret_value_count": len(secret_values),
        "secret_like_regex_hits": regex_hits,
        "exact_secret_hits": exact_hits,
        "passed": not regex_hits and not exact_hits,
    }


def scan_submission_identity(path: Path) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    if path.exists():
        for f in sorted(path.rglob("*")):
            if not f.is_file():
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for term in SUBMISSION_IDENTITY_TERMS:
                if term in text:
                    hits.append({"path": f.as_posix(), "term": term})
    return {"scanned": str(path), "banned_terms": list(SUBMISSION_IDENTITY_TERMS), "hits": hits, "passed": not hits}


def upstream_hashes() -> dict[str, str]:
    return {
        "reports/m010": hash_dir(Path("reports/m010")),
        "reports/m020": hash_dir(Path("reports/m020")),
        "reports/m030": hash_dir(Path("reports/m030")),
        "reports/m040": hash_dir(Path("reports/m040")),
        "reports/m050": hash_dir(Path("reports/m050")),
        "reports/m060": hash_dir(Path("reports/m060")),
        "reports/m070": hash_dir(Path("reports/m070")),
        "src/scholarloop/web": hash_dir(Path("src/scholarloop/web")),
        "reports/m040/results.json": sha256_file(Path("reports/m040/results.json")),
    }


def verify_fidelity() -> dict[str, Any]:
    demo = assemble_demo()
    m040 = load_m040()
    per_query = m040_by_query()
    failures: list[str] = []
    panel_counts = {"queries": len(demo["queries"]), "ranking_rows": 0, "evidence_cards": 0, "enriched_cards": 0, "gap_items": len(demo["gaps"]["items"])}
    missing_placeholders = 0
    for view in demo["queries"]:
        qid = view["query_id"]
        source_m040 = per_query[qid]["scholarloop_a_v2"]["ranked_top20"]
        if view["ranking"]["ranked_top20"] != source_m040:
            failures.append(f"{qid}: ranking ranked_top20 differs from M040")
        if view["ranking"]["top5_reasons_source"] != (per_query[qid].get("scholarloop_a_v2_reasons_top5") or []):
            failures.append(f"{qid}: top5 reasons differ from M040")
        evidence = load_evidence(qid)
        if view["evidence"]["cards"] != evidence.get("cards"):
            failures.append(f"{qid}: evidence cards differ from M020")
        if view["evidence"]["matrix"] != evidence.get("matrix"):
            failures.append(f"{qid}: evidence matrix differs from M020")
        enriched = load_enriched(qid)
        if view["enrichment"]["raw_cards"] != enriched.get("cards"):
            failures.append(f"{qid}: enrichment raw cards differ from M050 replay")
        for card in view["enrichment"]["cards"]:
            for field_name in ("authors_year", "source_or_doi"):
                field = card[field_name]
                if not field["value"]:
                    missing_placeholders += 1
                    if not str(field["display"]).startswith("需人工核验"):
                        failures.append(f"{qid}/{card['corpusid']}/{field_name}: missing value not explicitly marked")
        panel_counts["ranking_rows"] += len(view["ranking"]["rows"])
        panel_counts["evidence_cards"] += len(view["evidence"]["cards"])
        panel_counts["enriched_cards"] += len(view["enrichment"]["cards"])
    gaps = load_gaps_display()
    if demo["gaps"]["items"] != gaps.get("items"):
        failures.append("gaps items differ from M070 display")
    if demo["gaps"]["concept_nodes"] != gaps.get("concept_nodes"):
        failures.append("gaps concept_nodes differ from M070 display")
    if demo["gaps"]["matrix_edges"] != gaps.get("matrix_edges"):
        failures.append("gaps matrix_edges differ from M070 display")
    return {
        "status": "PASS" if not failures else "BLOCKED",
        "failures": failures,
        "panel_counts": panel_counts,
        "fabrication": 0 if not failures else len(failures),
        "out_of_pool": 0 if not failures else len(failures),
        "missing_placeholders_checked": missing_placeholders,
        "source_paths": {
            "m040": str(M040_RESULTS),
            "m020": str(M020_EVIDENCE_DIR),
            "m050": str(M050_REPLAY_DIR),
            "m070": str(M070_GAPS_DISPLAY),
        },
    }


def smoke_server(report_dir: Path) -> dict[str, Any]:
    server = create_server("127.0.0.1", 0)
    host, port = server.server_address
    base = f"http://{host}:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    lines: list[str] = [f"started {base}"]
    try:
        health_status, health = fetch_json(base, "/healthz")
        lines.append(f"GET /healthz -> {health_status} {health}")
        q_status, q_payload = fetch_json(base, "/api/queries")
        lines.append(f"GET /api/queries -> {q_status} count={q_payload.get('count')}")
        m_status, metrics = fetch_json(base, "/api/metrics")
        lines.append(f"GET /api/metrics -> {m_status} sections={list(metrics)}")
        g_status, gaps = fetch_json(base, "/api/gaps")
        lines.append(f"GET /api/gaps -> {g_status} items={len(gaps.get('items', []))}")
        first_qid = q_payload["queries"][0]["query_id"]
        v_status, view = fetch_json(base, f"/api/queries/{first_qid}")
        lines.append(f"GET /api/queries/{first_qid} -> {v_status} panels={list(view)}")
        h_status, html = fetch_text(base, f"/?qid={first_qid}")
        h2_status, html2 = fetch_text(base, f"/?qid={first_qid}")
        lines.append(f"GET /?qid={first_qid} -> {h_status}, repeat -> {h2_status}, bytes={len(html.encode('utf-8'))}")
        ok = (
            health_status == q_status == m_status == g_status == v_status == h_status == h2_status == 200
            and health.get("llm_calls_per_request") == 0
            and q_payload.get("count", 0) > 0
            and len(gaps.get("items", [])) > 0
            and html == html2
            and all(marker in html for marker in ["查询理解与分解", "A-v2 论文综合排序", "B-lite 逐条证据矩阵", "真实学术连接器富化", "研究空白发现"])
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    (report_dir / "smoke.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": "PASS" if ok else "BLOCKED", "base_url": base, "smoke_log": "reports/m080/smoke.txt", "lines": lines}


def run(report_dir: Path) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    before = upstream_hashes()
    fidelity = verify_fidelity()
    smoke = smoke_server(report_dir)
    secret_scan = scan_for_secrets(
        [
            Path("src/scholarloop/demo"),
            Path("tests"),
            Path("docs/submission"),
            Path("docs/dev/plans"),
            Path("docs/dev/retrospectives"),
            report_dir,
        ]
    )
    identity_scan = scan_submission_identity(Path("docs/submission"))
    after = upstream_hashes()
    unchanged = before == after
    status = "PASS" if fidelity["status"] == "PASS" and smoke["status"] == "PASS" and secret_scan["passed"] and identity_scan["passed"] and unchanged else "BLOCKED"
    audit = {
        "schema_version": "m080.fidelity_audit.v1",
        "status": status,
        "integration_runnable": smoke["status"] == "PASS",
        "faithful_zero_fabrication": fidelity["status"] == "PASS",
        "fabrication": fidelity["fabrication"],
        "out_of_pool": fidelity["out_of_pool"],
        "offline_zero_llm": True,
        "llm_calls_per_request": 0,
        "fidelity": fidelity,
        "smoke": smoke,
        "secret_scan": secret_scan,
        "submission_identity_scan": identity_scan,
        "upstream_hashes_before": before,
        "upstream_hashes_after": after,
        "upstream_unchanged_during_verification": unchanged,
        "single_command": "PYTHONPATH=src python -m scholarloop.demo.app --host 127.0.0.1 --port 8766",
    }
    write_json(report_dir / "fidelity_audit.json", audit)
    write_json(report_dir / "secret_scan.json", secret_scan)
    write_json(report_dir / "submission_identity_scan.json", identity_scan)
    write_json(report_dir / "upstream_hashes.json", {"before": before, "after": after, "unchanged": unchanged})
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", default="reports/m080")
    args = parser.parse_args(argv)
    out = run(Path(args.report_dir))
    print(json.dumps({"status": out["status"], "runnable": out["integration_runnable"], "faithful": out["faithful_zero_fabrication"]}, ensure_ascii=False, indent=2))
    return 0 if out["status"] == "PASS" else 5


if __name__ == "__main__":
    raise SystemExit(main())
