"""depth.md, the 完整精读 rules handed to the report agent (PLAN 15.4.11)."""

from prometheus.report.workspace import DEPTH_MD

RULES = DEPTH_MD.read_text(encoding="utf-8")


def test_it_tells_the_agent_who_reads_and_how_it_is_tested():
    assert "看不到视频" in RULES
    assert "每 5 分钟 4 道题" in RULES


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


def test_its_examples_give_nothing_away_about_the_evaluation_samples():
    # The closed-book questions come from these three videos: no example may touch them.
    for topic in ("卡巴拉", "罗素", "微分", "一对一", "AI", "战争", "学习"):
        assert topic not in RULES, topic
