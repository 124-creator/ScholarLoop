from pathlib import Path


PUBLIC_TEXT_FILES = [
    Path("index.html"),
    Path("README.md"),
    Path("docs/demo/README.md"),
    Path("DESIGN.md"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_demo_contains_links_and_truth_boundary():
    html = read(Path("index.html"))
    assert "ScholarLoop" in html
    assert "https://124-creator.github.io/ScholarLoop/" in html
    assert "source_text[char_span] == field value" in html
    assert "mismatch = 0" in html
    assert "public-safe" in html
    assert "/api/verify_span" in html
    assert "llm_calls = 0" in html


def test_public_demo_encodes_competition_and_loop_story():
    html = read(Path("index.html"))
    assert "人工智能比赛作品" in html
    assert "F1 是主战场" in html
    assert "运行效率要可解释" in html
    assert "结构化展示不是装饰" in html
    assert "Loop 1 · Search Loop" in html
    assert "Loop 2 · Trust Loop" in html
    assert "handoff.query_plan.json" in html
    assert "handoff.trace_report.json" in html


def test_public_demo_chinese_is_not_mojibake():
    html = read(Path("index.html"))
    assert "可信论文搜索 Agent" in html
    assert "不是给列表，而是给证据链" in html
    assert "点即核验" in html
    for bad in ["鍙", "璺", "鎼", "鐨", "乱码"]:
        assert bad not in html


def test_public_pages_do_not_expose_internal_working_context():
    forbidden = [
        "你给",
        "项目文件夹",
        "D:\\",
        "Dreamboat",
        "招聘官",
        "docs/dev",
        "源项目",
    ]
    for path in PUBLIC_TEXT_FILES:
        text = read(path)
        for token in forbidden:
            assert token not in text, f"{path} exposes internal wording: {token}"


def test_visible_demo_uses_public_facing_validation_language():
    html = read(Path("index.html"))
    assert "离线验证报告" in html
    assert "公开演示" in html
    assert "系统的核验红线" in html
    assert "M120" not in html
    assert "M130" not in html
    assert "M140" not in html


def test_design_contract_present():
    design = read(Path("DESIGN.md"))
    assert "Color encodes meaning" in design
    assert "Search Loop" in design
    assert "Trust Loop" in design
    assert "public-safe" in design


def test_public_validation_summary_present():
    text = read(Path("reports/m120/public_validation_summary.json"))
    assert "989" in text
    assert "fabrication" in text
