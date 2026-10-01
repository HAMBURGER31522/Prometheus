"""The frame ledger (PLAN 15.4.11, 多配图 ①): one look at a chapter's candidate frames says what each
one shows, so the writer can pick without opening them one by one and the program can tell which
informative frames were left out."""

import json

from prometheus.figures import notes

FRAMES = [{"file": "f_000030.jpg", "t": 30.0, "label": "00:30"}, {"file": "f_000400.jpg", "t": 400.0, "label": "06:40"}]


def test_the_prompt_names_every_frame_in_the_order_they_are_attached_and_every_kind():
    prompt = notes.notes_prompt(FRAMES)
    assert prompt.index("f_000030.jpg") < prompt.index("f_000400.jpg")
    assert "00:30" in prompt and "06:40" in prompt
    for kind in notes.KINDS:
        assert kind in prompt


def test_notes_keep_the_known_frames_in_order_and_mark_the_informative_ones():
    reply = json.dumps({"frames": {
        "f_000400.jpg": {"kind": "口播人像", "what": "讲者对着镜头"},
        "f_000030.jpg": {"kind": "幻灯片", "what": "三种萃取曲线的对比"},
        "f_999999.jpg": {"kind": "图表", "what": "不存在的帧"},
    }}, ensure_ascii=False)
    got = notes.parse_notes(reply, FRAMES)
    assert got == [
        {"file": "f_000030.jpg", "t": 30.0, "label": "00:30", "kind": "幻灯片", "what": "三种萃取曲线的对比", "useful": True},
        {"file": "f_000400.jpg", "t": 400.0, "label": "06:40", "kind": "口播人像", "what": "讲者对着镜头", "useful": False},
    ]


def test_an_unknown_kind_or_an_empty_description_is_dropped():
    reply = json.dumps({"frames": {"f_000030.jpg": {"kind": "好看", "what": "某页"},
                                   "f_000400.jpg": {"kind": "图表", "what": ""}}}, ensure_ascii=False)
    assert notes.parse_notes(reply, FRAMES) == []
    assert notes.parse_notes("不是 JSON", FRAMES) == []


def test_the_informative_kinds_are_the_ones_words_cannot_carry():
    assert set(notes.USEFUL) == {"幻灯片", "图表", "板书公式", "代码", "软件界面", "实物演示", "地图"}
    assert "口播人像" not in notes.USEFUL and "转场片头" not in notes.USEFUL
