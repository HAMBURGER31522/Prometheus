"""The frame ledger (PLAN 15.4.11, 多配图 ①).

Before a chapter is written, one call looks at all of its candidate frames (each attached on its
own: a contact sheet would be shrunk until slide text is unreadable) and says what each one shows.
The writer then picks from a list instead of opening every image (each look is a paid turn), and
the chapter check can name an informative frame that was left out.
"""

from prometheus.llm.replies import first_json_object

KINDS = ("幻灯片", "图表", "板书公式", "代码", "软件界面", "实物演示", "地图", "口播人像", "转场片头", "其他")
USEFUL = KINDS[:7]  # what words alone cannot carry (figures.md rule 2)


def notes_prompt(frames: list) -> str:
    listed = "\n".join(f"{number}. {frame['file']}（{frame['label']}）" for number, frame in enumerate(frames, 1))
    return (
        "下面按顺序附上一段视频里的几张画面截图，文件名和时间列在后面。逐张看，给每张标一个类型，"
        "再用一句话写出画面里的关键信息：幻灯片写标题和要点，图表写画的是什么，板书写公式或结论，"
        "界面写是哪个软件、在做什么，实物写是什么东西；看不清就写「看不清」。\n"
        f"类型只能是：{'、'.join(KINDS)}。\n"
        '只输出 JSON：{"frames": {"f_000030.jpg": {"kind": "幻灯片", "what": "……"}}}\n\n'
        f"{listed}\n"
    )


def parse_notes(text: str, frames: list) -> list:
    """The frames in their own order, each with a known kind and a description; the rest dropped."""
    value = first_json_object(text or "")
    found = value.get("frames") if isinstance(value, dict) else None
    found = found if isinstance(found, dict) else {}
    kept = []
    for frame in frames:
        item = found.get(frame["file"])
        item = item if isinstance(item, dict) else {}
        kind, what = str(item.get("kind") or "").strip(), str(item.get("what") or "").strip()
        if kind in KINDS and what:
            kept.append({**frame, "kind": kind, "what": what, "useful": kind in USEFUL})
    return kept
