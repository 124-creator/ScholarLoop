
from __future__ import annotations

import json
import re
from pathlib import Path

from scholarloop.connectors.base import format_authors_year, format_source_or_doi, title_match
from scholarloop.connectors.cache import ResponseCache
from scholarloop.connectors.openalex import OpenAlexConnector

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def read_json(path: str):
    return json.loads(read_text(path))


def by_system(rows: list[dict], name: str) -> dict:
    return next(row for row in rows if row["system"] == name)


def test_public_links_and_static_studio_contract():
    readme = read_text("README.md")
    html = read_text("index.html")

    assert "https://github.com/124-creator/ScholarLoop" in readme
    assert "https://124-creator.github.io/ScholarLoop/" in readme
    assert "ScholarLoop Studio" in html
    assert "GitHub Pages" in html
    assert "isStaticPagesHost" in html
    assert "staticSearchPayload" in html
    assert "GitHub Pages static demo" in html
    assert "Unexpected " + "token" not in html
    assert "static Studio" in read_text("docs/demo/README.md")
    assert "No recommendation rows were fabricated" in html
    assert "react.development" not in html.lower()
    assert "vue.global" not in html.lower()
    assert "cdn.jsdelivr" not in html.lower()


def test_latest_reports_are_present_and_passed():
    m180 = read_json("reports/m180/validation_summary.json")
    m140 = read_json("reports/m140/i18n_coverage.json")
    m130 = read_json("reports/m130/studio_fidelity.json")

    assert m180["status"] == "PASS"
    assert m140["status"] == "PASS"
    assert m130["status"] == "PASS"
    assert m130["mismatch_count"] == 0
    assert "77 passed" in read_text("reports/m180/pytest.txt")


def test_verified_metric_artifacts_are_available():
    m040 = read_json("reports/m040/results.json")
    m060 = read_json("reports/m060/results.json")

    assert round(m040["by_system"]["scholarloop_a_v2"]["F1"], 4) == 0.1312
    assert round(m040["by_system"]["bm25"]["F1"], 4) == 0.0964
    resolvable = m060["metrics"]["resolvable"]["aggregate"]
    assert round(by_system(resolvable, "scholarloop_a_v2")["F1"], 4) == 0.1972
    assert round(by_system(resolvable, "bm25")["F1"], 4) == 0.1058


def test_openalex_fixture_and_cache_are_offline_safe(tmp_path: Path):
    exact = "Contrastive Distillation on Intermediate Representations for Language Model Compression"
    assert title_match(exact, exact).strong
    assert not title_match(exact, "A Survey of Carbon Pricing Policy").strong

    cache = ResponseCache(tmp_path)
    path = cache.path_for("openalex", "GET", "https://api.openalex.org/works", {"search": "x", "api_key": "secret"})
    cache.write(
        path,
        source="openalex",
        method="GET",
        url="https://api.openalex.org/works",
        params={"search": "x", "api_key": "secret"},
        fetched_at="2026-06-20T00:00:00Z",
        status_code=200,
        headers={"content-type": "application/json"},
        body_json={"ok": True},
    )
    assert json.loads(path.read_text(encoding="utf-8"))["params"]["api_key"] == "<redacted>"

    fixture = read_json("tests/fixtures/m050/openalex_search.json")
    cache_entry = ResponseCache(tmp_path / "fixture_cache").write(
        tmp_path / "openalex_fixture.json",
        source=fixture["source"],
        method=fixture["method"],
        url=fixture["url"],
        params=fixture["params"],
        fetched_at=fixture["fetched_at"],
        status_code=fixture["status_code"],
        headers=fixture["headers"],
        body_json=fixture["body_json"],
    )
    record = OpenAlexConnector.parse_work(fixture["body_json"]["results"][0], cache_entry)
    assert record.doi == "10.18653/v1/2020.emnlp-main.552"
    assert record.year == 2020
    assert format_authors_year(record).startswith("Xiaoqi Jiao, Yichun Yin")
    assert "DOI: 10.18653/v1/2020.emnlp-main.552" in format_source_or_doi(record)


def test_public_snapshot_excludes_large_private_artifacts():
    manifest = read_json("PUBLIC_SNAPSHOT.json")
    assert manifest["total_bytes"] < 40_000_000
    assert "m180" in manifest["included_reports"]
    for forbidden in ("secrets", ".omx", "raw", "cache", "*.npy", "*.parquet"):
        assert forbidden in manifest["excluded"]

    forbidden_paths = [p for p in ROOT.rglob("*") if ".git" not in p.parts and ".pytest_cache" not in p.parts and any(part in {"secrets", ".omx", ".omc", "cache", "raw"} for part in p.parts)]
    assert not forbidden_paths
    assert not list(ROOT.rglob("*.npy"))
    assert not list(ROOT.rglob("*.parquet"))


def test_no_high_risk_secret_or_phone_patterns_in_public_files():
    token_prefix = "gho" + "_"
    secret_prefix = "s" + "k-"
    ark_prefix = "a" + "rk-"
    phone = "155" + "178" + "37680"
    email_domains = ("163" + ".com", "qq" + ".com", "gmail" + ".com", "outlook" + ".com")
    high_risk = re.compile(rf"({token_prefix}[A-Za-z0-9_]+|{secret_prefix}[A-Za-z0-9_\-]{{12,}}|{ark_prefix}[A-Za-z0-9_\-]{{12,}}|{phone}|[A-Za-z0-9._%+-]+@({'|'.join(re.escape(d) for d in email_domains)}))", re.I)
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".pytest_cache" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".html", ".txt", ".json", ".csv", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if high_risk.search(text):
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []
