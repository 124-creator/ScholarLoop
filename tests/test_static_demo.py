from pathlib import Path


def test_public_demo_contains_recruiter_links_and_truth_boundary():
    html = Path("index.html").read_text(encoding="utf-8")
    assert "ScholarLoop" in html
    assert "https://124-creator.github.io/ScholarLoop/" in html
    assert "source_text[char_span] == field value" in html
    assert "mismatch = 0" in html
    assert "public-safe" in html
    assert "/api/verify_span" in html
    assert "llm_calls = 0" in html


def test_public_validation_summary_present():
    text = Path("reports/m120/public_validation_summary.json").read_text(encoding="utf-8")
    assert "989" in text
    assert "fabrication" in text
