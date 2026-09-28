"""Report evaluation (PLAN 15.4.11 「评测」): closed-book questions, faithfulness sampling,
program metrics and a cost estimate. The model is always a fake here."""

import json

from prometheus.report import evaluation as ev

REPORT = """<html><head><style>.paper{}</style></head><body><main class="paper">
<header class="intro"><h1>咖啡的标题</h1><p class="lead">导语。</p></header>
<section id="s1"><h2><span class="num">1</span><span class="section-title">第一章</span><span class="section-time">00:00–00:10</span></h2>
<p data-source-units="unit-000001 unit-000003" data-points="K001 K002">第一句讲的是水温。第二句讲的是研磨粗细！</p>
<ol class="steps"><li data-source-units="unit-000004">步骤一先称量十五克咖啡粉。</li></ol>
<aside class="supplement"><p class="supplement-label">补充说明（非视频内容）</p><p>萃取是溶解可溶物质的过程。</p></aside>
<figure class="report-figure"><img src="data:image/jpeg;base64,AAAA" alt="图"><figcaption>图注。</figcaption></figure>
</section>
<section id="s2"><h2><span class="num">2</span><span class="section-title">第二章</span><span class="section-time">00:10–00:20</span></h2>
<p>这一段没有任何出处标注。</p>
<table><tr><td data-source-units="unit-000015">表格里的内容。</td></tr></table>
<div class="callout"><p data-points="K004">强调。</p></div>
<svg viewBox="0 0 10 10"><circle r="1"/></svg>
</section></main></body></html>"""


def units(count=20):
    return [{"unit_id": f"unit-{i + 1:06d}", "start_ms": i * 1000, "end_ms": (i + 1) * 1000,
             "canonical_text": f"原话{i + 1}。"} for i in range(count)]


# ---------- program metrics ----------

def test_component_counts_follow_the_template_classes():
    counts = ev.component_counts(REPORT)
    assert {name: counts[name] for name in ("figure", "img", "svg", "table", "steps", "callout")} == {
        "figure": 1, "img": 1, "svg": 1, "table": 1, "steps": 1, "callout": 1}
    assert counts["cards"] == 0 and counts["comparison"] == 0
    assert counts["total"] == 6


def test_citation_coverage_takes_each_attribute_as_a_span():
    result = ev.citation_coverage(REPORT, units())
    assert result["covered"] == 5 and result["total"] == 20
    assert result["share"] == 0.25
    assert abs(result["longest_gap_min"] - 10 / 60) < 1e-9


def test_points_coverage_counts_marked_points_and_skips_legal_skips():
    assert ev.points_coverage(REPORT, ["K001", "K002", "K003", "K004"]) == 0.75
    assert ev.points_coverage(REPORT, ["K001", "K002", "K003", "K004"], skipped={"K003"}) == 1.0
    assert ev.points_coverage(REPORT, []) is None


def test_chapter_density_is_characters_per_minute_of_source():
    chapters = ev.chapter_density(REPORT)
    assert [chapter["title"] for chapter in chapters] == ["第一章", "第二章"]
    assert chapters[0]["minutes"] == 10 / 60
    assert chapters[0]["chars"] > chapters[1]["chars"] > 0
    assert chapters[0]["per_minute"] == chapters[0]["chars"] / (10 / 60)


# ---------- faithfulness ----------

def test_sentences_leave_out_supplements_titles_and_scraps():
    sentences = ev.report_sentences(REPORT, units())
    texts = [sentence["text"] for sentence in sentences]
    assert texts == ["第一句讲的是水温。", "第二句讲的是研磨粗细！", "步骤一先称量十五克咖啡粉。",
                     "这一段没有任何出处标注。", "表格里的内容。"]
    assert not any("萃取" in text for text in texts)


def test_a_sentence_brings_its_cited_units_widened_or_its_chapters_range():
    sentences = {s["text"]: s for s in ev.report_sentences(REPORT, units())}
    units_of = lambda text: set((sentences.get(text) or {}).get("units") or [])
    assert {f"unit-{i:06d}" for i in range(1, 6)} <= units_of("第一句讲的是水温。")
    assert {f"unit-{i:06d}" for i in range(2, 7)} <= units_of("步骤一先称量十五克咖啡粉。")
    assert {f"unit-{i:06d}" for i in range(11, 21)} <= units_of("这一段没有任何出处标注。")


def test_a_sentence_also_brings_the_transcript_passage_that_matches_it():
    """Citations are often off (the old 104-minute report cited unrelated units for 23 of 40
    sampled sentences): the passage that best matches the sentence is added to its evidence."""
    rows = units(40)
    for index in (29, 30, 31):
        rows[index]["canonical_text"] = "手冲的时候水温要控制在九十二度左右。"
    evidence = {s["text"]: set(s["units"]) for s in ev.report_sentences(REPORT, rows)}
    matched = {"unit-000030", "unit-000031", "unit-000032"}
    assert matched <= evidence["第一句讲的是水温。"]
    assert {f"unit-{i:06d}" for i in range(1, 6)} <= evidence["第一句讲的是水温。"]
    assert not matched & evidence["表格里的内容。"]


def test_sampling_is_seeded_and_bounded():
    sentences = ev.report_sentences(REPORT, units())
    first = ev.sample_sentences(sentences, 3, seed=7)
    assert first == ev.sample_sentences(sentences, 3, seed=7)
    assert len(first) == 3 and len(ev.sample_sentences(sentences, 40, seed=7)) == len(sentences)


def test_supplements_are_collected_with_their_chapter():
    supplements = ev.report_supplements(REPORT, units())
    assert [s["text"] for s in supplements] == ["萃取是溶解可溶物质的过程。"]
    assert supplements[0]["units"] == [f"unit-{i:06d}" for i in range(1, 11)]


# ---------- closed-book questions ----------

def test_the_question_prompt_carries_the_block_and_the_rules():
    block = units(5)
    prompt = ev.question_prompt(block)
    assert "[unit-000003 00:00:02] 原话3。" in prompt
    assert "4 道" in prompt and "只根据这段转写" in prompt


def test_questions_are_validated_and_capped_at_four():
    block_ids = [f"unit-{i:06d}" for i in range(1, 6)]
    reply = "```json\n" + json.dumps({"questions": [
        {"q": f"问题{i}", "answer": f"答案{i}", "units": ["unit-000002"]} for i in range(5)
    ] + [{"q": "来源不对", "answer": "答", "units": ["unit-999999"]}, {"q": "", "answer": "空题", "units": []}]},
        ensure_ascii=False) + "\n```"
    questions, problems = ev.parse_questions(reply, block_ids)
    assert [q["q"] for q in questions] == ["问题0", "问题1", "问题2", "问题3"]
    assert len(problems) == 2
    assert ev.parse_questions("不是 JSON", block_ids) == ([], ["回复不是合法 JSON"])


def test_answers_and_grades_are_read_by_number():
    assert ev.parse_answers('{"answers": {"1": "九十二度", "3": "未提及"}}', 3) == ["九十二度", "未提及", "未提及"]
    assert ev.parse_grades('{"grades": {"1": "正确", "2": "部分正确", "3": "乱写"}}', 3) == ["正确", "部分正确", None]


def test_the_score_counts_half_for_partly_right():
    score = ev.qa_score(["正确", "部分正确", "未提及", "错误", None])
    assert score == {"total": 5, "correct": 1, "partial": 1, "missing": 1, "wrong": 1, "ungraded": 1,
                     "score": 0.3}


# ---------- cost ----------

def test_cost_is_estimated_from_characters():
    assert ev.estimate_tokens("中文四字") == 4
    assert ev.estimate_tokens("abcdefgh") == 2
    calls = [{"in": "中" * 1_000_000, "out": ""}, {"in": "", "out": "文" * 100_000}]
    assert ev.estimate_cost(calls) == {"calls": 2, "tokens_in": 1_000_000, "tokens_out": 100_000,
                                       "usd": 5.0 + 2.5}


# ---------- the whole evaluation with a fake model ----------

def fake_ask(prompt: str) -> str:
    if "出 4 道" in prompt:
        return json.dumps({"questions": [{"q": "水温多少", "answer": "九十二度", "units": ["unit-000001"]}]},
                          ensure_ascii=False)
    if '"answers"' in prompt:
        return json.dumps({"answers": {"1": "九十二度"}}, ensure_ascii=False)
    if '"grades"' in prompt:
        return json.dumps({"grades": {"1": "正确"}}, ensure_ascii=False)
    if "不矛盾" in prompt:
        return json.dumps({"verdicts": {"1": "不矛盾"}}, ensure_ascii=False)
    return json.dumps({"verdicts": {str(i): "有依据" for i in range(1, 41)}}, ensure_ascii=False)


def test_a_whole_evaluation_with_a_fake_model(tmp_path):
    questions_file = tmp_path / "questions.json"
    result = ev.evaluate_report(units(), REPORT, questions_file, fake_ask, points=["K001", "K002", "K004"])
    assert result.get("qa", {}).get("score") == 1.0 and result.get("qa", {}).get("total") == 1
    assert result.get("faithfulness") == {"sampled": 5, "有依据": 5, "部分有依据": 0, "无依据": 0, "ungraded": 0}
    assert result.get("supplements") == {"checked": 1, "矛盾": 0, "不矛盾": 1, "ungraded": 0}
    assert result.get("points_coverage") == 1.0
    assert result.get("components", {}).get("total") == 6
    assert result.get("cost", {}).get("calls", 0) >= 4
    # The questions are kept, so an old and a new report meet exactly the same ones.
    saved = json.loads(questions_file.read_text(encoding="utf-8")) if questions_file.is_file() else {}
    assert [q["q"] for q in saved.get("questions", [])] == ["水温多少"]
    again = ev.evaluate_report(units(), REPORT, questions_file, lambda prompt: fake_ask(prompt.replace("出 4 道", "")))
    assert again.get("qa", {}).get("total") == 1
