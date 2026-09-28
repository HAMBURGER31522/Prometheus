"""The two-step 讲清楚 review (PLAN 15.4.11 step 6): a reader who never saw the video lists what
is unclear from the chapter alone; then the transcript decides what can be fixed from the source,
what a supplement may explain, and what stays as it is."""

import json

from prometheus.report import review

CHAPTER = """<section id="s1"><h2>水温</h2><p>浅烘豆要用高一点的水温，深烘豆要低一些。</p>
<p>水温和研磨一起决定萃取率。</p></section>"""
TRANSCRIPT = "浅烘豆用九十二到九十六度，深烘豆用八十五到八十八度，因为深烘豆的可溶物更容易泡出来。"


def test_the_reader_sees_only_the_chapter():
    prompt = review.reader_prompt(CHAPTER)
    assert "浅烘豆要用高一点的水温" in prompt and "没看过视频" in prompt
    assert "零基础" in prompt and "第一次出现" in prompt and "术语" in prompt
    assert "九十二" not in prompt


def test_reader_questions_must_quote_the_chapter():
    reply = json.dumps({"questions": [
        {"quote": "浅烘豆要用高一点的水温", "question": "高一点是多少度？"},
        {"quote": "这句话根本不在本章里", "question": "什么意思？"},
        {"quote": "萃取率", "question": "萃取率是什么？"},
    ]}, ensure_ascii=False)
    questions = review.parse_reader(reply, CHAPTER)
    assert [q["question"] for q in questions] == ["高一点是多少度？", "萃取率是什么？"]


def test_the_judge_sees_the_transcript_and_sorts_each_question():
    questions = [{"quote": "浅烘豆要用高一点的水温", "question": "高一点是多少度？"},
                 {"quote": "萃取率", "question": "萃取率是什么？"},
                 {"quote": "深烘豆要低一些", "question": "为什么深烘要低？"}]
    prompt = review.judge_prompt(questions, TRANSCRIPT)
    assert "九十二到九十六度" in prompt and "高一点是多少度？" in prompt
    reply = json.dumps({"verdicts": {
        "1": {"kind": "原文有答案", "answer": "浅烘九十二到九十六度"},
        "2": {"kind": "术语或背景"},
        "3": {"kind": "乱写"},
    }}, ensure_ascii=False)
    verdicts = review.parse_judge(reply, len(questions))
    assert [v["kind"] if v else None for v in verdicts] == ["原文有答案", "术语或背景", None]


def test_fixes_answer_from_the_source_or_with_a_supplement_and_drop_the_rest():
    questions = [{"quote": "浅烘豆要用高一点的水温", "question": "高一点是多少度？"},
                 {"quote": "萃取率", "question": "萃取率是什么？"},
                 {"quote": "深烘豆要低一些", "question": "讲者当时在哪家店？"}]
    verdicts = [{"kind": "原文有答案", "answer": "浅烘九十二到九十六度"}, {"kind": "术语或背景"}, {"kind": "原文没有"}]
    fixes = review.fixes(questions, verdicts)
    assert len(fixes) == 2
    assert "九十二到九十六度" in fixes[0] and "高一点是多少度" in fixes[0]
    assert "萃取率" in fixes[1] and "补充说明" in fixes[1]
    assert not any("哪家店" in fix for fix in fixes)
