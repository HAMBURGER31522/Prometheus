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


def test_its_examples_give_nothing_away_about_the_evaluation_samples():
    # The closed-book questions come from these three videos: no example may touch them.
    for topic in ("卡巴拉", "罗素", "微分", "一对一", "AI", "战争", "学习"):
        assert topic not in RULES, topic
