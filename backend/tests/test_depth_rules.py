"""depth.md, the 完整精读 rules handed to the report agent (PLAN 15.4.11)."""

import re

from prometheus.report.full import DEPTH_MD

RULES = DEPTH_MD.read_text(encoding="utf-8")


def test_it_tells_the_agent_who_reads_and_how_it_is_tested():
    assert "看不到视频" in RULES
    assert "每 5 分钟 4 道题" in RULES


def test_the_reader_is_a_smart_beginner_and_every_point_takes_four_steps():
    """After the ELI5 skill (user 2026-09-28): what it is, an analogy, the layers, so what."""
    assert "零基础" in RULES
    for step in ("是什么", "类比", "所以呢"):
        assert step in RULES, step
    assert "复述" in RULES  # the stopping point is understanding, not a length


def test_terms_are_explained_in_the_sentence_where_they_first_appear():
    assert "第一次出现" in RULES and "一句" in RULES
    for kind in ("术语", "人名", "缩写"):
        assert kind in RULES, kind


def test_it_never_names_a_number_of_characters():
    # A stated minimum becomes the finish line and a range becomes a cap (user 2026-09-28).
    assert not re.search(r"\d+\s*字", RULES)


def test_nothing_of_a_point_goes_missing_lists_reasons_names():
    """PLAN 15.4.11a-1: the omission patterns of the acceptance runs, as rules for any video."""
    assert "列举要全" in RULES and "原因要全" in RULES and "具体名称照写" in RULES


def test_the_editor_may_judge_in_a_box_of_its_own_with_confidence_and_sources():
    """PLAN 15.4.11a-4: contested points get the editor's own view, never the speaker's words."""
    assert '<aside class="viewpoint">' in RULES and "编者观点（非视频内容）" in RULES
    assert "置信度" in RULES and "URL" in RULES
    assert "不写成讲者" in RULES


def test_it_quotes_each_compressing_rule_it_overrides():
    for quoted in ("合并作用相同的例子", "不以篇幅证明完整性", "60 分钟的重复闲聊可以压缩为短报告",
                   "禁止连续出现三段及以上的大段文字", "图中讲清的关系不再在正文重复", "优先删除重复层次"):
        assert quoted in RULES, quoted


def test_it_asks_for_supplements_in_their_own_box():
    assert '<aside class="supplement">' in RULES
    assert "补充说明（非视频内容）" in RULES


def test_it_keeps_the_pictures():
    assert "figures.md" in RULES
    assert "组件" in RULES


def test_diagrams_follow_the_shape_of_the_content_not_a_count():
    # user 2026-09-28: triggered by content, never one per point or per chapter
    for shape in ("步骤", "对照", "关系图", "卡片", "柱图"):
        assert shape in RULES, shape
    assert "不按要点" in RULES


def test_the_picture_and_the_text_do_not_repeat_each_other():
    # user 2026-09-28: 图文不重复是基本 — the diagram carries the structure, the text what it cannot draw
    assert "每个节点和箭头的含义，正文仍要写清楚" not in RULES
    assert "不重复" in RULES and "画不出" in RULES


def test_its_examples_give_nothing_away_about_the_evaluation_samples():
    # The closed-book questions come from these three videos: no example may touch them.
    for topic in ("卡巴拉", "罗素", "微分", "一对一", "AI", "战争", "学习"):
        assert topic not in RULES, topic


def test_only_what_the_video_says_goes_into_a_persons_mouth():
    """Russell on Claude Code (2026-09-30): 「所以罗素说……赢家也是灰烬」 and the like were the writer's own
    explanation put in the subject's mouth; the grader marked them unsupported (user 2026-09-30)."""
    assert "只能是视频里真有的话" in RULES and "不要借人物之口" in RULES and "编者口吻" in RULES


def test_it_gives_the_powershell_way_to_run_python():
    """modes/standard.md gives the bash form, which PowerShell cannot run (user 2026-09-30)."""
    assert "& $env:VIDEO_REPORT_PYTHON" in RULES


def test_a_supplement_is_written_through_what_why_here_and_an_example():
    """R7g (PLAN 15.4.14 B): Codex's supplements said what it is, why it matters at this sentence and gave
    an example or a framework; Claude's stopped at a sentence or two of definition. No length is named."""
    assert "为什么要紧" in RULES and "具体例子、数字或出处" in RULES


def test_limits_are_written_only_where_the_video_is_disputed_or_the_report_adds():
    """R7g (15.4.14 E): GPT's reports carried 10–12 「不能据此断定」 a ten thousand characters, Claude's under one."""
    assert "不能据此断定" in RULES and "确有争议" in RULES and "直接讲清楚" in RULES


def test_the_writing_materials_never_show_in_the_text():
    """R7g (15.4.14 D): 「候选帧已逐张查看」「本章依据转写单元 unit-… 整理」「（K022）」 reached readers."""
    assert "转写单元编号" in RULES and "要点编号" in RULES and "写作用的材料" in RULES
