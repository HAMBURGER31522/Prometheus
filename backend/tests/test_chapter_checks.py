"""Checking one written chapter (PLAN 15.4.11 step 5): every owned point marked and really there,
not pasted from the transcript, not far too short; problems come back as a list to fix."""

import re

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
# What the video says about each point: the text of the units it rests on.
SOURCES = {"K001": "浅烘的话水温九十二到九十六度", "K002": "萃取就是把可溶物泡出来", "K003": "就像泡茶一样泡太久就苦了"}

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


def test_a_point_explained_too_briefly_for_what_the_video_says_is_sent_back_without_a_number():
    brief = GOOD.replace("萃取指热水把咖啡粉里的可溶物质溶解出来的过程，溶出太少偏酸，太多偏苦。", "萃取指热水把咖啡粉里的可溶物质溶解出来。")
    result = checks.check_chapter(brief, ["K001", "K002"], POINTS, TRANSCRIPT, sources=SOURCES)
    assert result["thin"] == ["K002"]
    problem = next(problem for problem in result["problems"] if "K002" in problem)
    assert "类比" in problem and "所以呢" in problem
    assert not re.search(r"\d", problem.replace("K002", ""))  # never a count to stop at
    assert checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT, sources=SOURCES)["thin"] == []


def test_the_bar_grows_with_what_the_video_says_about_the_point():
    longer = {**SOURCES, "K001": SOURCES["K001"] * 8}
    result = checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT, sources=longer)
    assert result["thin"] == ["K001"]


def test_a_paragraph_marking_several_points_is_shared_between_them():
    both = """<section id="s1"><p data-points="K001 K002">浅烘豆适合用九十二到九十六度的水：水温越高，酸味越少、苦味越多。萃取指热水把咖啡粉里的可溶物质溶解出来。</p></section>"""
    alone = checks.point_chars(both)
    assert alone["K001"] == alone["K002"] and alone["K001"] < len(re.sub(r"[^一-鿿]", "", both)) 


FRAMES = [{"file": "f_000030.jpg", "t": 30.0, "label": "00:30", "kind": "幻灯片", "what": "三种烘焙度的颜色对比", "useful": True},
          {"file": "f_000050.jpg", "t": 50.0, "label": "00:50", "kind": "口播人像", "what": "讲者对着镜头", "useful": False}]


def test_an_informative_frame_left_out_without_a_reason_is_sent_back():
    result = checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT, frames=FRAMES)
    assert result["unused_frames"] == ["f_000030.jpg"]
    problem = next(problem for problem in result["problems"] if "f_000030.jpg" in problem)
    assert "三种烘焙度的颜色对比" in problem and "<!-- 不用 f_000030.jpg：" in problem


def test_a_frame_used_or_declined_with_a_reason_is_fine():
    figure = '<figure class="report-figure"><img src="frames/f_000030.jpg" alt="颜色对比"><figcaption>浅中深三种颜色</figcaption></figure>'
    used = GOOD.replace("</section>", figure + "</section>")
    assert checks.check_chapter(used, ["K001", "K002"], POINTS, TRANSCRIPT, frames=FRAMES)["unused_frames"] == []
    declined = GOOD + "\n<!-- 不用 f_000030.jpg：和正文里的对照表是同一组信息 -->"
    assert checks.check_chapter(declined, ["K001", "K002"], POINTS, TRANSCRIPT, frames=FRAMES)["unused_frames"] == []
    no_reason = GOOD + "\n<!-- 不用 f_000030.jpg -->"
    assert checks.check_chapter(no_reason, ["K001", "K002"], POINTS, TRANSCRIPT, frames=FRAMES)["unused_frames"] == ["f_000030.jpg"]


def test_a_point_is_split_into_its_items_without_the_lead_in():
    """PLAN 15.4.11a-2: lists and reasons are checked item by item (user 2026-09-29)."""
    assert checks.point_items("展示图表有两个原因：一是让学习者更清楚接下来会学什么，二是强制系统把推理讲清楚") == [
        "让学习者更清楚接下来会学什么", "强制系统把推理讲清楚"]
    assert checks.point_items("教学风格只影响两件事：学习弧线；沿途每一步的讲解") == ["学习弧线", "沿途每一步的讲解"]
    assert checks.point_items("浅烘豆用九十二到九十六度的水") == []  # one item: nothing to split


def test_an_item_left_out_of_a_list_is_named():
    points = {"K009": {"id": "K009", "type": "理由", "text": "教学风格只影响两件事：一是学习弧线的走向，二是沿途每一步的讲解",
                       "anchor": "只影响两件事", "start_ms": 0, "end_ms": 30_000}}
    fragment = '<section><p data-points="K009">主要原因是教学风格：它决定了学习弧线的走向，也就是从现有理解走到目标的路径。</p></section>'
    result = checks.check_chapter(fragment, ["K009"], points, "")
    assert result["incomplete"] == {"K009": ["沿途每一步的讲解"]}
    assert any("K009" in problem and "沿途每一步的讲解" in problem for problem in result["problems"])
    full = fragment.replace("路径。", "路径；二是沿途每一步的讲解怎么安排。")
    assert checks.check_chapter(full, ["K009"], points, "")["incomplete"] == {}


def test_a_clean_chapter_has_no_problems():
    assert checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT)["problems"] == []


def test_the_writing_materials_in_the_text_are_sent_back_but_not_in_attributes():
    """R7g (PLAN 15.4.14 D): 「候选帧已逐张查看」「转写单元 unit-000033」「（K022）」 reached readers, while
    data-points and data-source-units are where the ids belong."""
    leaked = GOOD.replace("</section>", "<p>候选帧已逐张查看，没有选用；本章依据转写单元 unit-000033 整理（K022）。</p></section>")
    check = checks.check_chapter(leaked, ["K001", "K002"], POINTS, TRANSCRIPT)
    assert set(check["process"]) == {"候选帧", "转写单元", "unit-000033", "K022"}
    assert any("处理过程" in problem and "候选帧" in problem for problem in check["problems"])
    assert checks.check_chapter(GOOD, ["K001", "K002"], POINTS, TRANSCRIPT)["process"] == []


def test_limiting_sentences_are_listed_only_when_they_crowd_the_chapter():
    """R7g (15.4.14 E): a 「不能据此断定」 now and then is fine; ten a page is a hedge on every claim."""
    crowded = "<section><p>" + "这件事不能据此断定。" * 5 + "水温讲清楚了。" * 20 + "</p></section>"
    calm = "<section><p>这件事不能据此断定。" + "水温和研磨怎样一起决定萃取率讲清楚了。" * 300 + "</p></section>"
    assert checks.hedges(crowded) == ["这件事不能据此断定。"] * 5
    assert checks.hedges(calm) == []


def test_the_feedback_prompt_lists_the_problems_and_keeps_the_rest():
    prompt = checks.feedback_prompt(["要点 K003 没有写到"], "chapter.html")
    assert "K003" in prompt and "chapter.html" in prompt and "其余" in prompt
