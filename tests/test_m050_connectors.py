from __future__ import annotations

import json
from pathlib import Path

from scholarloop.connectors.base import AcademicHttpClient, format_authors_year, format_source_or_doi, title_match
from scholarloop.connectors.cache import ResponseCache
from scholarloop.connectors.openalex import OpenAlexConnector
from scholarloop.connectors.resolver import enrich_card_with_record


def test_m050_title_match_strong_and_weak() -> None:
    exact = "Contrastive Distillation on Intermediate Representations for Language Model Compression"
    assert title_match(exact, exact).strong
    weak = title_match(exact, "A Survey of Carbon Pricing Policy")
    assert not weak.strong
    assert weak.normalized_score < 0.5


def test_m050_response_cache_roundtrip(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path)
    path = cache.path_for("openalex", "GET", "https://api.openalex.org/works", {"search": "x", "api_key": "secret"})
    entry = cache.write(
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
    assert entry.body_json == {"ok": True}
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["params"]["api_key"] == "<redacted>"


def test_m050_openalex_fixture_parse(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/m050/openalex_search.json").read_text(encoding="utf-8"))
    cache_entry = ResponseCache().write(
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
    assert record.external_id == "https://openalex.org/W3101066076"
    assert record.doi == "10.18653/v1/2020.emnlp-main.552"
    assert record.year == 2020
    assert format_authors_year(record).startswith("Xiaoqi Jiao, Yichun Yin")
    assert "DOI: 10.18653/v1/2020.emnlp-main.552" in format_source_or_doi(record)


def test_m050_resolver_enriches_only_strong_match(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/m050/openalex_search.json").read_text(encoding="utf-8"))
    cache_entry = ResponseCache().write(
        tmp_path / "openalex_fixture_for_resolver.json",
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
    card = {
        "corpusid": 1,
        "fields": {
            "title": {"value": record.title, "status": "已有证据支持"},
            "authors_year": {"field": "authors_year", "value": "", "status": "需人工核验", "resolution_hint": "online_connector_required_for_author_year_source_doi"},
            "source_or_doi": {"field": "source_or_doi", "value": "", "status": "需人工核验", "resolution_hint": "online_connector_required_for_author_year_source_doi"},
        },
    }
    enriched, result = enrich_card_with_record(card, record)
    assert result["resolved"]
    assert enriched["fields"]["authors_year"]["status"] == "已有外部来源支持"
    assert enriched["fields"]["source_or_doi"]["external_provenance"]["source"] == "openalex"

    weak_card = dict(card)
    weak_card["fields"] = dict(card["fields"])
    weak_card["fields"]["title"] = {"value": "A Survey of Carbon Pricing Policy", "status": "已有证据支持"}
    weak, weak_result = enrich_card_with_record(weak_card, record)
    assert not weak_result["resolved"]
    assert weak["fields"]["authors_year"]["status"] == "需人工核验"
    assert weak["fields"]["authors_year"]["m050_resolution_attempt"]["strong_match"] is False


def test_m050_offline_fixture_client_reads_cache(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/m050/openalex_search.json").read_text(encoding="utf-8"))
    cache = ResponseCache(tmp_path)
    path = cache.path_for("openalex", "GET", "https://api.openalex.org/works", {"search": "fixture", "per-page": 1})
    cache.write(
        path,
        source="openalex",
        method="GET",
        url="https://api.openalex.org/works",
        params={"search": "fixture", "per-page": 1},
        fetched_at=fixture["fetched_at"],
        status_code=200,
        headers=fixture["headers"],
        body_json=fixture["body_json"],
    )
    client = AcademicHttpClient(cache=cache, offline=True)
    entry = client.get_json("openalex", "https://api.openalex.org/works", {"search": "fixture", "per-page": 1})
    assert entry.body_json["results"][0]["id"] == "https://openalex.org/W3101066076"
