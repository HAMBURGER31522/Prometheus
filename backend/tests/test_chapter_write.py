"""What one chapter's writer is given (PLAN 15.4.11 step 4): the rules in full, the whole plan, its
own points and transcript and nothing of the other chapters' sources, and how to mark the points."""

import re

from prometheus.report import chapter_write as write

PLAN = {"title": "手冲咖啡的三个变量", "subtitle": "", "lead": "水温、研磨和粉水比。", "profile": "mechanism",
        "chapters": [{"id": "c1", "title": "水温", "ranges": [["00:00", "02:00"]], "target_chars": 600},
                     {"id": "c2", "title": "研磨", "ranges": [["02:00", "04:00"]], "target_chars": 900},
                     {"id": "c3", "title": "粉水比", "ranges": [["04:00", "06:00"]], "target_chars": 600}],
        "glossary": [{"term": "萃取", "chapter": "c1"}, {"term": "细粉", "chapter": "c2"}],
        "moves": {"K005": "c2"}, "skips": []}
UNITS = [{"unit_id": f"unit-{i:06d}", "start_ms": i * 30_000, "end_ms": (i + 1) * 30_000,
          "canonical_text": f"第{i}句原话"} for i in range(12)]
POINTS = {
    "K003": {"id": "K003", "type": "定义", "text": "细粉是研磨时产生的极细颗粒", "anchor": "第4句原话",
             "units": ["unit-000004", "unit-000004"], "start_ms": 120_000, "end_ms": 150_000},
    "K004": {"id": "K004", "type": "论断", "text": "磨得越细萃取越快", "anchor": "第6句原话",
             "units": ["unit-000006", "unit-000006"], "start_ms": 180_000, "end_ms": 210_000},
    "K005": {"id": "K005", "type": "例子", "text": "讲者用面粉比喻细粉", "anchor": "第10句原话",
             "units": ["unit-000010", "unit-000010"], "start_ms": 300_000, "end_ms": 330_000},
    "K001": {"id": "K001", "type": "数字", "text": "水温九十二度", "anchor": "第1句原话",
             "units": ["unit-000001", "unit-000001"], "start_ms": 30_000, "end_ms": 60_000},
}
OWNED = ["K003", "K004", "K005"]


def prompt(**overrides):
    options = {"figures": False, "attached": "【附件全文】"}
    return write.chapter_prompt(PLAN, 2, OWNED, POINTS, UNITS, **{**options, **overrides})


def test_the_writer_sees_its_units_and_the_units_of_points_moved_in_and_nothing_else():
    ids = [unit["unit_id"] for unit in write.chapter_units(PLAN["chapters"][1], OWNED, POINTS, UNITS)]
    assert ids == ["unit-000004", "unit-000005", "unit-000006", "unit-000007", "unit-000010"]
    text = prompt()
    assert "第5句原话" in text and "第10句原话" in text
    assert "第1句原话" not in text
    assert "[unit-000002 " not in text and "[unit-000011 " not in text


def test_every_owned_point_is_listed_with_its_words_and_no_other_chapters_points():
    text = prompt()
    for point_id in OWNED:
        assert point_id in text and POINTS[point_id]["text"] in text and POINTS[point_id]["anchor"] in text
    assert "K001" not in text and "水温九十二度" not in text


def test_the_writer_knows_its_place_its_file_its_heading_and_its_length():
    text = prompt()
    assert "第 2/3 章" in text and "研磨" in text and "水温" in text and "粉水比" in text
    assert "ch-02.html" in text
    assert '<span class="num">2</span>' in text and "02:00–04:00" in text
    task = text[text.index("## 任务"):]
    assert "900" not in task and not re.search(r"\d+\s*字", task)
    assert "零基础" in task and "四步" in task and "第一次出现" in task
    assert 'data-points="' in text and "data-source-units" in text
    assert "supplement" in text


def test_terms_are_explained_once():
    text = prompt()
    first, before = text.index("本章首次解释的术语"), text.index("前面章节已经解释过的术语")
    assert "细粉" in text[first:first + 40] and "萃取" in text[before:before + 60]


def test_the_rules_are_attached_in_full_and_not_read_again():
    text = prompt()
    assert "【附件全文】" in text and "不用再读取" in text
    assert text.index("【附件全文】") < text.index("K003")  # long documents first, the task last


def test_figures_only_when_the_run_has_frames():
    assert "figures.md" not in prompt()
    assert "figures.md" in prompt(figures=True)


def test_frames_are_chosen_by_what_they_show_with_no_count_limit():
    """User 2026-09-28: more pictures, no cap; a frame is used when it shows what words cannot."""
    task = prompt(figures=True)
    task = task[task.index("## 任务"):]
    assert "不受" in task and "张数" in task and "宁多勿少" in task
    assert "只配一次" in task and "口播" in task
    assert not re.search(r"最多\s*\d+\s*张", task)


def test_an_hour_long_video_uses_hours_in_the_section_time():
    long_plan = {**PLAN, "chapters": [{**chapter, "ranges": [["01:02:00", "01:04:00"]]} for chapter in PLAN["chapters"]]}
    text = write.chapter_prompt(long_plan, 2, [], POINTS, UNITS, figures=False, attached="")
    assert "01:02:00–01:04:00" in text


def test_a_revision_starts_from_the_draft_with_the_problems_listed():
    text = write.revision_prompt("【本章任务】", ["要点 K004 没有写到"], "ch-02.html")
    assert text.startswith("【本章任务】")
    assert "ch-02.html" in text and "K004" in text and "其余" in text
