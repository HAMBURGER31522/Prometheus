"""Planning a 完整精读 (PLAN 15.4.11 step 3): chapters, the points each one owns, reasoned skips."""

from prometheus.report import plan as planning


def ledger(count=8, seconds_each=60):
    return {"points": [{"id": f"K{i:03d}", "type": "论断", "text": f"要点{i}", "anchor": "原话",
                        "units": [f"unit-{i:06d}", f"unit-{i:06d}"],
                        "start_ms": (i - 1) * seconds_each * 1000, "end_ms": i * seconds_each * 1000}
                       for i in range(1, count + 1)], "skips": [], "problems": [], "uncovered": []}


def plan(**extra):
    base = {"title": "手冲咖啡的三个变量", "subtitle": "", "lead": "这是一段导语。", "profile": "mechanism",
            "chapters": [{"id": "c1", "title": "水温", "ranges": [["00:00", "04:00"]], "target_chars": 600},
                         {"id": "c2", "title": "研磨", "ranges": [["04:00", "08:00"]], "target_chars": 600}],
            "glossary": [{"term": "萃取", "chapter": "c1"}], "moves": {}, "skips": []}
    return {**base, **extra}


def test_points_fall_into_chapters_by_time_and_moves_override():
    owned = planning.assign(plan(moves={"K002": "c2"}), ledger())
    assert owned == {"c1": ["K001", "K003", "K004"], "c2": ["K002", "K005", "K006", "K007", "K008"]}


def test_a_moment_in_an_overview_chapter_goes_to_the_narrowest_one():
    overview = plan(chapters=[{"id": "c0", "title": "总览", "ranges": [["00:00", "08:00"]], "target_chars": 300},
                              {"id": "c1", "title": "水温", "ranges": [["00:00", "04:00"]], "target_chars": 600},
                              {"id": "c2", "title": "研磨", "ranges": [["04:00", "08:00"]], "target_chars": 600}])
    owned = planning.assign(overview, ledger())
    assert owned.get("c0") == [] and owned.get("c1") == ["K001", "K002", "K003", "K004"]


def test_a_good_plan_has_no_problems():
    assert planning.validate_plan(plan(), ledger()) == []


def test_every_problem_is_named():
    problems = planning.validate_plan(plan(
        title="",
        chapters=[{"id": "c1", "title": "水温", "ranges": [["00:00", "03:00"]], "target_chars": 600}],
        moves={"K999": "c1", "K001": "c9"},
        skips=[{"point": "K004", "reason": "我觉得不重要"},
               {"point": "K005", "reason": "重复", "duplicate_of": "K006"},
               {"point": "K006", "reason": "重复", "duplicate_of": "K005"}],
    ), ledger())
    text = "\n".join(problems)
    assert "主标题" in text
    assert "K999" in text and "c9" in text
    assert "K004" in text and "理由" in text
    assert "K006" in text and "被跳过" in text
    assert "K007" in text and "没有归属" in text  # 06:00–07:00 is outside every chapter


def test_skipping_more_than_a_quarter_asks_for_a_review():
    skips = [{"point": f"K00{i}", "reason": "离题闲聊"} for i in range(1, 4)]
    problems = planning.validate_plan(plan(skips=skips), ledger())
    assert any("25%" in problem for problem in problems)
    assert not any("25%" in problem for problem in planning.validate_plan(plan(skips=skips[:2]), ledger()))


def test_the_plan_is_read_from_a_reply_with_extra_words():
    text = "好的，规划如下：\n```json\n" + '{"title": "标题", "chapters": []}' + "\n```"
    assert (planning.read_plan(text) or {}).get("title") == "标题"
    assert planning.read_plan("没有 JSON") is None


def test_the_prompt_names_the_inputs_and_the_output():
    prompt = planning.plan_prompt(figures=False)
    for name in ("keypoints.md", "depth.md", "input.json", "plan.json", "SKILL.md", "modes/standard.md"):
        assert name in prompt
    assert "figures.md" not in prompt and "figures.md" in planning.plan_prompt(figures=True)
