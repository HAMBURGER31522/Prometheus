"""The key-point ledger (PLAN 15.4.11 step 2): every point of substance in each ~5-minute block,
checked against the transcript, with every unit either in a point or in a reasoned skip."""

import json

from prometheus.report import keypoints as kp


def units(count=30, seconds_each=10.0):
    return [{"unit_id": f"unit-{i + 1:06d}", "start_ms": int(i * seconds_each * 1000),
             "end_ms": int((i + 1) * seconds_each * 1000), "canonical_text": f"第{i + 1}句原话讲的是咖啡豆的烘焙程度{i + 1}。"}
            for i in range(count)]


def point(first, last, anchor=None, kind="论断", text="浅烘豆酸味明显。"):
    return {"type": kind, "text": text, "units": [f"unit-{first:06d}", f"unit-{last:06d}"],
            "anchor": anchor or f"第{first}句原话讲的是咖啡豆的烘焙程度{first}"}


def reply(points, skips=()):
    return json.dumps({"points": points, "skips": list(skips)}, ensure_ascii=False)


def test_the_prompt_carries_the_block_and_asks_for_everything():
    prompt = kp.keypoint_prompt(units(3))
    assert "[unit-000002 00:00:10] 第2句原话讲的是咖啡豆的烘焙程度2。" in prompt
    assert "所有" in prompt and "skips" in prompt and "anchor" in prompt


def test_a_good_point_is_kept_and_bad_ones_say_why():
    block = units(10)
    points, skips, problems = kp.parse_points(reply([
        point(1, 2),
        point(3, 3, anchor="完全不在原文里的一句话呀"),
        point(4, 4, kind="闲话"),
        point(5, 99),
    ], [{"units": ["unit-000006", "unit-000007"], "reason": "寒暄与课堂管理"},
        {"units": ["unit-000008", "unit-000008"], "reason": "我觉得不重要"}]), block)
    assert [p["units"] for p in points] == [["unit-000001", "unit-000002"]]
    assert skips == [{"units": ["unit-000006", "unit-000007"], "reason": "寒暄与课堂管理"}]
    assert len(problems) == 4
    assert any("原话" in problem for problem in problems)


def test_an_anchor_with_a_misheard_character_still_counts():
    block = units(3)
    anchor = "第2句原话讲的是咖啡逗的烘焙程度2"  # 豆 heard as 逗
    points, _skips, problems = kp.parse_points(reply([point(2, 2, anchor=anchor)]), block)
    assert len(points) == 1 and problems == []


def test_stretches_of_thirty_seconds_or_more_without_a_home_are_found():
    block = units(10)  # 10 s per unit
    stretches = kp.unassigned(block, [point(1, 2), point(7, 10)], [{"units": ["unit-000003", "unit-000003"]}])
    assert stretches == [("unit-000004", "unit-000006")]  # 30 s
    assert kp.unassigned(block, [point(1, 2), point(5, 10)], [{"units": ["unit-000003", "unit-000003"]}]) == []


def test_the_ledger_asks_again_once_for_problems_and_for_uncovered_stretches():
    rows = units(60)  # two blocks of 30 units
    calls = []

    def ask(prompt):
        calls.append(prompt)
        if "没有归属" in prompt:
            return reply([point(21, 30, text="补上的要点。")])
        if "上次的问题" in prompt:
            return reply([point(1, 20)])
        if "unit-000001 " in prompt:
            return reply([point(1, 20, anchor="根本找不到的原话啊啊")])
        return reply([point(31, 60)])

    ledger = kp.build_ledger(rows, ask, seconds=300, workers=1)
    assert [p["id"] for p in ledger["points"]] == ["K001", "K002", "K003"]
    assert [p["units"][0] for p in ledger["points"]] == ["unit-000001", "unit-000021", "unit-000031"]
    assert ledger["points"][1]["text"] == "补上的要点。"
    assert ledger["points"][0]["start_ms"] == 0 and ledger["points"][2]["end_ms"] == 600_000
    assert len(calls) == 4
    assert ledger["uncovered"] == []


def test_the_ledger_markdown_and_transcript_parts_are_written(tmp_path):
    rows = units(60)
    ledger = kp.build_ledger(rows, lambda prompt: reply([point(1, 30)]) if "unit-000001 " in prompt
                             else reply([point(31, 60)]), seconds=300, workers=1)
    markdown = kp.ledger_markdown(ledger)
    assert "K001" in markdown and "00:00:00–00:05:00" in markdown
    parts = kp.write_parts(rows, tmp_path, seconds=300)
    assert [path.name for path in parts] == ["part-01.md", "part-02.md"]
    assert "[unit-000031 00:05:00]" in parts[1].read_text(encoding="utf-8")
