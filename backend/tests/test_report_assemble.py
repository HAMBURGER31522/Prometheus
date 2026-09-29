"""Assembling the chapters into VRA's template (PLAN 15.4.11 step 7)."""

from prometheus.report import assemble
from prometheus.report.pi_run import SKILL_DIR

TEMPLATE = (SKILL_DIR / "assets" / "report-template.html").read_text(encoding="utf-8")
PLAN = {"title": "手冲咖啡的三个变量", "subtitle": "", "lead": "水温、研磨和粉水比 & 它们的关系。",
        "chapters": [{"id": "c1", "title": "水温"}, {"id": "c2", "title": "研磨"}]}
INPUT = {"attribution": "Bilibili；示例UP主；《手冲 <入门>》；https://www.bilibili.com/video/BV1xJYT6EEYc/"}
FRAGMENTS = [
    '<section><h2><span class="num">1</span><span class="section-title">水温</span></h2><p>第一章正文。</p></section>',
    '<style>.local-note{font-size:14px}</style>\n<section id="s2"><h2>研磨</h2><p class="local-note">第二章正文。</p></section>',
]


def test_the_template_is_filled_and_only_the_description_placeholder_stays():
    html = assemble.assemble(TEMPLATE, PLAN, FRAGMENTS, INPUT, sources="要点 12 条，写到 12 条。")
    assert html.count("手冲咖啡的三个变量") == 2  # <title> and <h1>
    assert "水温、研磨和粉水比 &amp; 它们的关系。" in html
    assert "《手冲 &lt;入门&gt;》" in html
    assert html.count("{{VIDEO_DESCRIPTION}}") == 1
    assert "{{" not in html.replace("{{VIDEO_DESCRIPTION}}", "")
    assert "要点 12 条，写到 12 条。" in html


def test_an_empty_subtitle_leaves_no_empty_line_and_the_guidance_comments_go():
    html = assemble.assemble(TEMPLATE, PLAN, FRAGMENTS, INPUT, sources="")
    assert 'class="subtitle"' not in html
    assert "<!--" not in html
    with_subtitle = assemble.assemble(TEMPLATE, {**PLAN, "subtitle": "一个新角度"}, FRAGMENTS, INPUT, sources="")
    assert '<p class="subtitle">一个新角度</p>' in with_subtitle


def test_chapters_come_in_order_with_ids_and_a_nav_links_them():
    html = assemble.assemble(TEMPLATE, PLAN, FRAGMENTS, INPUT, sources="")
    assert "第一章正文" in html and "第二章正文" in html
    assert html.index("第一章正文") < html.index("第二章正文")
    assert '<section id="s1">' in html and '<section id="s2">' in html
    assert '<a href="#s1">水温</a>' in html and '<a href="#s2">研磨</a>' in html


def test_a_chapters_own_style_moves_into_the_head():
    html = assemble.assemble(TEMPLATE, PLAN, FRAGMENTS, INPUT, sources="")
    head, body = html.split("</head>", 1)
    assert ".local-note{font-size:14px}" in head
    assert ".local-note{font-size:14px}" not in body
