"""The two-step 讲清楚 review (PLAN 15.4.11 step 6): a reader who never saw the video lists what
is unclear from the chapter alone; then the transcript decides what can be fixed from the source,
what a supplement may explain, and what stays as it is."""

import json
import re

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


def test_the_reader_may_ask_for_a_picture_where_one_would_help():
    assert "图" in review.reader_prompt(CHAPTER) and "pictures" in review.reader_prompt(CHAPTER)
    reply = json.dumps({"questions": [], "pictures": [
        {"quote": "水温和研磨一起决定萃取率", "want": "水温、研磨和萃取率的关系图"},
        {"quote": "不在本章里的一句话", "want": "随便一张图"},
    ]}, ensure_ascii=False)
    pictures = review.parse_pictures(reply, CHAPTER)
    assert pictures == [{"quote": "水温和研磨一起决定萃取率", "want": "水温、研磨和萃取率的关系图"}]
    fixes = review.fixes([], [], pictures)
    assert len(fixes) == 1 and "关系图" in fixes[0] and "只画本章正文已经写到的内容" in fixes[0]


LONG = ("<section><h2>水温</h2>" + "".join(f"<p>第{i}段讲水温和研磨怎样一起决定萃取率，浅烘和深烘各有讲究。</p>"
                                          for i in range(40)) + "</section>")


def test_the_second_reader_gets_the_first_list_and_never_a_number():
    """R7g (PLAN 15.4.14 A): every chapter gets a second reader who looks for what the first one missed."""
    first = [{"quote": "浅烘和深烘各有讲究", "question": "讲究什么？"}]
    prompt = review.second_reader_prompt(LONG, first)
    assert "没看过视频" in prompt and "已经问过" in prompt and "讲究什么？" in prompt and "第3段讲水温" in prompt
    assert "为什么" in prompt and "例子" in prompt and "pictures" in prompt
    assert not re.search(r"\d+\s*条|千字", prompt)


def test_a_background_question_left_without_its_supplement_is_found():
    """R7g (15.4.14 F): the sonnet baseline raised 34 background questions and wrote 22 supplements."""
    label = '<p class="supplement-label">补充说明（非视频内容）</p>'
    chapter = (f'<section><h2>水温</h2><p>萃取率决定味道。</p><aside class="supplement">{label}<p>萃取率是溶出的比例。</p>'
               '</aside><p>浅烘豆要用高一点的水温。</p><p>其他。</p><p>其他二。</p><p>其他三。</p></section>')
    asked = [{"quote": "萃取率决定味道", "question": "萃取率是什么？"},
             {"quote": "浅烘豆要用高一点的水温", "question": "浅烘是什么？"},
             {"quote": "已经改写掉的一句", "question": "随便"}]
    assert review.missing_supplements(chapter, asked) == [asked[1]]


def test_the_two_readers_are_merged_without_repeats():
    first = [{"quote": "浅烘和深烘各有讲究", "question": "讲究什么？"}]
    second = [{"quote": "浅烘和深烘各有讲究", "question": "讲究什么？"}, {"quote": "萃取率", "question": "怎么算？"}]
    assert review.merge(first, second) == first + second[1:]


def test_a_background_supplement_is_asked_for_in_three_steps():
    """R7g (15.4.14 B): what it is, why it matters at this sentence, an example, a number or a source."""
    fixes = review.fixes([{"quote": "萃取率", "question": "萃取率是什么？"}], [{"kind": "术语或背景"}])
    assert "是什么" in fixes[0] and "为什么要紧" in fixes[0] and "具体例子、数字或出处" in fixes[0]


def test_a_supplement_of_a_sentence_or_two_is_found():
    label = '<p class="supplement-label">补充说明（非视频内容）</p>'
    short = f'<aside class="supplement">{label}<p>萃取率是溶出的比例。</p></aside>'
    full = f'<aside class="supplement">{label}<p>' + "萃取率是咖啡粉里的可溶物被水溶解出来的比例，" * 8 + "</p></aside>"
    found = review.thin_supplements(f"<section><p>正文</p>{short}{full}</section>")
    assert len(found) == 1 and "溶出的比例" in found[0] and "补充说明（非视频内容）" not in found[0]


def test_a_picture_asked_for_and_not_drawn_is_found():
    """R7g (15.4.14 C): a place the reader wanted a picture must have one close by after the revision."""
    chapter = ('<section><h2>水温</h2><p>水温和研磨一起决定萃取率。</p><figure><svg></svg><figcaption>关系图</figcaption>'
               '</figure><p>浅烘豆要用高一点的水温。</p><p>其他。</p><p>其他二。</p><p>其他三。</p><p>其他四。</p>'
               '<figure><img src="frames/f_001.jpg"></figure></section>')
    pictures = [{"quote": "水温和研磨一起决定萃取率", "want": "关系图"},
                {"quote": "浅烘豆要用高一点的水温", "want": "温度对照"},
                {"quote": "已经改写掉的一句", "want": "随便"}]
    assert review.missing_pictures(chapter, pictures) == [pictures[1]]


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
