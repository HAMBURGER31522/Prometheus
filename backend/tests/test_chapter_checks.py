"""Checking one written chapter (PLAN 15.4.11 step 5): every owned point marked and really there,
not pasted from the transcript, not far too short; problems come back as a list to fix."""

from prometheus.report import chapter_checks as checks

POINTS = {
    "K001": {"id": "K001", "type": "数字", "text": "浅烘豆用九十二到九十六度的水", "anchor": "浅烘的话水温九十二到九十六度",
             "start_ms": 0, "end_ms": 30_000},
    "K002": {"id": "K002", "type": "定义", "text": "萃取是热水溶解咖啡粉里可溶物质的过程", "anchor": "萃取就是把可溶物泡出来",
             "start_ms": 30_000, "end_ms": 60_000},
    "K003": {"id": "K003", "type": "例子", "text": "讲者用泡茶比喻萃取时间的长短", "anchor": "就像泡茶一样",
             "start_ms": 60_000, "end_ms": 90_000},
}
TRANSCRIPT = "然后我们讲水温对吧浅烘的话水温九十二到九十六度然后萃取就是把可溶物泡出来就像泡茶一样泡太久就苦了对吧"

GOOD = """<section id="s1"><h2><span class="num">1</span><span class="section-title">水温</span></h2>
<p data-points="K001">浅烘豆适合用九十二到九十六度的水：水温越高，酸味越少、苦味越多。</p>
<p data-points="K002">萃取指热水把咖啡粉里的可溶物质溶解出来的过程，溶出太少偏酸，太多偏苦。</p>
</section>"""


def test_marked_points_are_read_from_data_points():
    assert checks.marked_points(GOOD) == {"K001", "K002"}


def test_a_missing_point_is_named_with_its_words_and_time():
    result = checks.check_chapter(GOOD, ["K001", "K002", "K003"], POINTS, TRANSCRIPT)
    assert result["missing"] == ["K003"]
    assert any("K003" in problem and "就像泡茶一样" in problem and "01:00" in problem for problem in result["problems"])


def test_a_mark_without_the_points_substance_is_weak():
    hollow = GOOD.replace("浅烘豆适合用九十二到九十六度的水：水温越高，酸味越少、苦味越多。", "这一点很重要，需要注意。")
    result = checks.check_chapter(hollow, ["K001", "K002"], POINTS, TRANSCRIPT)
    assert result["weak"] == ["K001"]
    assert checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT)["weak"] == []


def test_text_pasted_from_the_transcript_is_measured():
    pasted = GOOD.replace("</section>", "<p>然后我们讲水温对吧浅烘的话水温九十二到九十六度然后萃取就是把可溶物泡出来</p></section>")
    result = checks.check_chapter(pasted, ["K001", "K002"], POINTS, TRANSCRIPT)
    assert result["copy_ratio"] > 0.25
    assert any("照抄" in problem for problem in result["problems"])
    assert checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT)["copy_ratio"] == 0.0


def test_a_chapter_far_below_its_floor_is_flagged():
    short = """<section id="s1"><p data-points="K001 K002">九十二度，萃取。</p></section>"""
    result = checks.check_chapter(short, ["K001", "K002"], POINTS, TRANSCRIPT)
    assert result["chars"] < result["floor"]
    assert any("字" in problem and "下限" in problem for problem in result["problems"])
    assert not any("下限" in p for p in checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT)["problems"])


def test_a_clean_chapter_has_no_problems():
    assert checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT)["problems"] == []


def test_the_feedback_prompt_lists_the_problems_and_keeps_the_rest():
    prompt = checks.feedback_prompt(["要点 K003 没有写到"], "chapter.html")
    assert "K003" in prompt and "chapter.html" in prompt and "其余" in prompt
