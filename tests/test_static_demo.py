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


def test_public_demo_encodes_competition_and_loop_story():
    html = Path("index.html").read_text(encoding="utf-8")
    assert "人工智能比赛作品" in html
    assert "F1 是主战场" in html
    assert "运行效率要可解释" in html
    assert "结构化展示不是装饰" in html
    assert "Loop 1 · Search Loop" in html
    assert "Loop 2 · Trust Loop" in html
    assert "handoff.query_plan.json" in html
    assert "handoff.trace_report.json" in html


def test_public_demo_chinese_is_not_mojibake():
    html = Path("index.html").read_text(encoding="utf-8")
    assert "可信论文搜索 Agent" in html
    assert "不是给列表，而是给证据链" in html
    assert "点即核验" in html
    for bad in ["鍙", "璺", "鎼", "鐨", "乱码"]:
        assert bad not in html


def test_design_contract_present():
    design = Path("DESIGN.md").read_text(encoding="utf-8")
    assert "Color encodes meaning" in design
    assert "Search Loop" in design
    assert "Trust Loop" in design
    assert "public-safe" in design


def test_public_validation_summary_present():
    text = Path("reports/m120/public_validation_summary.json").read_text(encoding="utf-8")
    assert "989" in text
    assert "fabrication" in text
