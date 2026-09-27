"""Simple-to-rich mind maps (PLAN 15.4.9, D-40): retrieval, checks, one rewrite, metrics.
The model is faked throughout."""

import json
import re
from pathlib import Path

from prometheus.mindmap import enrich, retrieve, tree

FIXTURES = Path(__file__).parent / "fixtures"
HTML = (FIXTURES / "report.html").read_text(encoding="utf-8")
TREE = json.loads((FIXTURES / "mindmap.json").read_text(encoding="utf-8"))


def _leaves(node):
    if node["type"] == "leaf":
        yield node
    for child in node["children"]:
        yield from _leaves(child)


# --- retrieval ------------------------------------------------------------------------------

def test_passages_follow_the_chapters():
    passages = retrieve.passages(HTML)
    assert passages, "no passages"
    assert {p["section"] for p in passages} == set(range(9))
    assert all(len(p["text"]) >= 8 for p in passages)


def test_evidence_is_the_chapter_at_the_leaf_time_plus_related_passages():
    index = retrieve.Index(HTML)
    first = TREE["root"]["children"][0]["children"][0]
    evidence = index.evidence(first)
    chapter = retrieve.section_text(HTML, 0)
    assert chapter and evidence
    assert chapter[:40] in evidence
    assert len(evidence) <= retrieve.MAX_EVIDENCE


def test_keyword_retrieval_finds_a_passage_in_another_chapter():
    index = retrieve.Index(HTML)
    target = next(p for p in retrieve.passages(HTML) if p["section"] == 5)
    words = re.sub(r"[^一-鿿]", "", target["text"])[:12]
    leaf = {"label": words, "summary": words, "time": 1, "type": "leaf", "children": []}  # time points at chapter 0
    assert target["text"][:30] in index.evidence(leaf)


# --- checks ---------------------------------------------------------------------------------

EVIDENCE = (
    "1994 年分税制把增值税的 75% 划归中央、25% 留给地方，中央财政收入占比从 22% 升到 55% 左右。"
    "地方事权没有相应减少，财力却收缩了，此后地方转向土地出让金来补缺口，形成土地财政。"
)
GOOD = (
    "1994 年分税制把增值税的 75% 划归中央、25% 留给地方，中央财政收入占比从 22% 升到 55% 左右；"
    "地方事权没有相应减少而财力收缩，于是转向土地出让金补缺口，形成土地财政。"
)


def test_a_grounded_concrete_detail_passes():
    assert enrich.check_detail(GOOD, "中央与地方重新分钱", EVIDENCE) == []


def test_each_failure_is_named():
    short = enrich.check_detail("分税制很重要。", "中央与地方重新分钱", EVIDENCE)
    assert any("字" in problem for problem in short)
    long = enrich.check_detail(GOOD * 3, "中央与地方重新分钱", EVIDENCE)
    assert any("220" in problem for problem in long)
    vague = "这一部分介绍了财政制度改革的背景、内容和影响，说明了它在国家治理中的重要作用，也提到了后续的很多变化与讨论，值得读者关注和思考其中的深层逻辑。"
    problems = enrich.check_detail(vague, "中央与地方重新分钱", EVIDENCE)
    assert any("依据" in problem for problem in problems)
    assert any("具体" in problem for problem in problems)
    echo = "中央与地方重新分钱" * 10
    assert any("复述" in problem for problem in enrich.check_detail(echo, "中央与地方重新分钱" * 10, EVIDENCE))


# --- enrichment -------------------------------------------------------------------------------

def _answer(prompt: str, fix=None) -> str:
    """A fake model: a grounded detail for every leaf id in the prompt (or ``fix`` for some)."""
    ids = re.findall(r"编号 \"([0-9.]+)\"", prompt)
    return json.dumps({i: (fix or {}).get(i, GOOD) for i in ids}, ensure_ascii=False)


def test_every_theme_is_filled_in_one_call_and_details_land_on_the_leaves(monkeypatch):
    monkeypatch.setattr(retrieve.Index, "evidence", lambda self, leaf: EVIDENCE)
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return _answer(prompt)

    filled, stats = enrich.enrich_tree(json.loads(json.dumps(TREE)), HTML, ask=ask)
    assert len(calls) == len(TREE["root"]["children"])
    assert all(leaf.get("detail") == GOOD for leaf in _leaves(filled["root"]))
    assert stats["coverage"] == 1.0 and stats["rewrites"] == 0


def test_a_failing_leaf_is_rewritten_once_with_its_problems(monkeypatch):
    monkeypatch.setattr(retrieve.Index, "evidence", lambda self, leaf: EVIDENCE)
    first_leaf = "0.0.0"
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        if len(prompts) == 1:
            return _answer(prompt, fix={first_leaf: "分税制很重要。"})
        return _answer(prompt)

    _filled, stats = enrich.enrich_tree(json.loads(json.dumps(TREE)), HTML, ask=ask)
    rewrite = [p for p in prompts if "上次写的" in p]
    assert len(rewrite) == 1 and "分税制很重要" in rewrite[0]
    assert stats["rewrites"] == 1 and stats["coverage"] == 1.0


def test_a_leaf_that_fails_twice_keeps_no_detail(monkeypatch):
    monkeypatch.setattr(retrieve.Index, "evidence", lambda self, leaf: EVIDENCE)
    filled, stats = enrich.enrich_tree(
        json.loads(json.dumps(TREE)), HTML, ask=lambda prompt: _answer(prompt, fix={"0.0.0": "太短了。"}),
    )
    first = filled["root"]["children"][0]["children"][0]
    assert "detail" not in first
    assert 0 < stats["coverage"] < 1


def test_the_prompt_asks_for_grounded_concrete_detail_with_examples(monkeypatch):
    monkeypatch.setattr(retrieve.Index, "evidence", lambda self, leaf: EVIDENCE)
    prompts = []
    enrich.enrich_tree(json.loads(json.dumps(TREE)), HTML, ask=lambda p: prompts.append(p) or _answer(p))
    prompt = prompts[0]
    for phrase in ("只依据", "具体信息", "好的示例", "差的示例", "只输出 JSON", "资料"):
        assert phrase in prompt


def test_metrics_show_richness_growing_outwards(monkeypatch):
    monkeypatch.setattr(retrieve.Index, "evidence", lambda self, leaf: EVIDENCE)
    _filled, stats = enrich.enrich_tree(json.loads(json.dumps(TREE)), HTML, ask=_answer)
    levels = stats["chars_by_level"]
    assert levels["root"] < levels["theme"] < levels["leaf"]
    assert stats["grounding"] >= 0.35
    assert stats["concrete"] == 1.0


def test_theme_summaries_are_short():
    theme = TREE["root"]["children"][0]
    long_tree = json.loads(json.dumps(TREE))
    long_tree["root"]["children"][0]["summary"] = "很" * 41
    outline = {"sections": [{"start_s": 0, "end_s": 10_000}]}
    assert any("summary" in problem for problem in tree.validate_tree(long_tree, outline))
    assert len(theme["summary"]) <= 40


def test_markdown_carries_the_details():
    from prometheus.mindmap.markdown import tree_to_markdown

    rich = json.loads(json.dumps(TREE))
    rich["root"]["children"][0]["children"][0]["detail"] = GOOD
    assert GOOD in tree_to_markdown(rich, "bilibili", "BV1xJYT6EEYc")
