"""精读.md: the report rendered as Markdown for AI readers (PLAN 15.4.1)."""

from pathlib import Path

from prometheus.report.markdown_export import report_to_markdown

EXAMPLE = Path("vendor/video-report-agent/docs/examples/report.html")


def _markdown():
    return report_to_markdown(EXAMPLE.read_text(encoding="utf-8"))


def test_title_and_section_headings_with_times():
    md = _markdown()
    assert md.startswith("# 削藩与分配：中国财政再平衡的逻辑与路径\n")
    assert "## " in md
    assert "00:00–02:27" in md


def test_body_text_survives_without_markup():
    md = _markdown()
    assert "水獭国" in md
    for tag in ("<div", "<span", "<section", "<style", "<script", "</p>"):
        assert tag not in md


def test_tables_become_pipe_tables():
    md = _markdown()
    assert "| --- |" in md


def test_inline_images_are_not_copied():
    html = ('<html><body><h1>T</h1><figure class="report-figure"><img src="data:image/jpeg;base64,AAAA">'
            "<figcaption>画面要点 · 05:32</figcaption></figure></body></html>")
    md = report_to_markdown(html)
    assert "data:image" not in md
    assert "画面要点 · 05:32" in md
