"""Checking one written chapter (PLAN 15.4.11 step 5; after Self-Refine and Chain of Density: the
feedback is a concrete list, never "write more").

- every point the plan gives the chapter is marked in a data-points attribute (the second level of
  coverage; the ledger itself was the first);
- a marked point is really there: its wording shows up in the marking elements (character bigrams);
- the chapter does not paste the spoken transcript (runs of 30+ identical characters);
- the chapter is not far below a floor set by its points.
"""

import re

from prometheus.report.evaluation import parse_html

GROUNDING_MIN = 0.3      # share of a point's bigrams found in the text that marks it
COPY_RUN = 30            # identical characters that count as pasted
COPY_MAX = 0.15          # pasted share of the chapter that asks for a rewrite
MIN_CHARS = {"数字": 15, "人名书名": 15}
MIN_CHARS_DEFAULT = 30   # half the 60–150 per point that depth.md asks for
_NOT_WORDY = re.compile(r"[^一-鿿A-Za-z0-9]")
_CJK = re.compile(r"[一-鿿]")


def _norm(text: str) -> str:
    return _NOT_WORDY.sub("", (text or "").lower())


def _bigrams(text: str) -> list:
    clean = _norm(text)
    return [clean[i:i + 2] for i in range(len(clean) - 1)]


def _clock(ms: int) -> str:
    seconds = int(ms // 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}" if seconds < 3600 else \
        f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _marking(fragment: str) -> dict:
    """{point id: text of every element that marks it}."""
    texts: dict = {}
    for node in parse_html(fragment).walk():
        for point_id in (node.attrs.get("data-points") or "").split():
            texts[point_id] = texts.get(point_id, "") + node.text()
    return texts


def marked_points(fragment: str) -> set:
    return set(_marking(fragment))


def _grounded(point: dict, text: str) -> bool:
    wanted = set(_bigrams(point["text"]))
    if not wanted:
        return True
    found = set(_bigrams(text))
    return len(wanted & found) / len(wanted) >= GROUNDING_MIN


def _copy_ratio(fragment_text: str, transcript: str) -> float:
    body, source = _norm(fragment_text), _norm(transcript)
    if len(body) < COPY_RUN:
        return 0.0
    windows = {source[i:i + COPY_RUN] for i in range(len(source) - COPY_RUN + 1)}
    copied = [False] * len(body)
    for start in range(len(body) - COPY_RUN + 1):
        if body[start:start + COPY_RUN] in windows:
            copied[start:start + COPY_RUN] = [True] * COPY_RUN
    return sum(copied) / len(body)


def check_chapter(fragment: str, owned: list, points: dict, transcript: str) -> dict:
    marking = _marking(fragment)
    root = parse_html(fragment)
    text = root.text(lambda node: node.tag == "h2")
    missing = [point_id for point_id in owned if point_id not in marking]
    weak = [point_id for point_id in owned if point_id in marking and not _grounded(points[point_id], marking[point_id])]
    copy_ratio = _copy_ratio(text, transcript)
    chars = len(_CJK.findall(text))
    floor = sum(MIN_CHARS.get(points[point_id]["type"], MIN_CHARS_DEFAULT) for point_id in owned)
    problems = []
    for point_id in missing:
        point = points[point_id]
        problems.append(f"要点 {point_id} 没有写到（{point['text']}；原话：「{point['anchor']}」，"
                        f"{_clock(point['start_ms'])}）：补写进本章，并用 data-points 标出")
    for point_id in weak:
        problems.append(f"要点 {point_id} 标了 data-points，但那段文字里看不到它的内容（{points[point_id]['text']}）："
                        "把这个要点真正写出来、讲清楚")
    if copy_ratio > COPY_MAX:
        problems.append(f"本章约 {copy_ratio:.0%} 的文字是照抄转写的口语：改写成完整、通顺的书面语")
    if chars < floor:
        problems.append(f"本章只有 {chars} 字，低于按要点估算的下限 {floor} 字：每个要点都要讲清是什么、为什么、怎么用")
    return {"missing": missing, "weak": weak, "copy_ratio": copy_ratio, "chars": chars, "floor": floor,
            "problems": problems}


def feedback_prompt(problems: list, filename: str) -> str:
    listed = "".join(f"- {problem}\n" for problem in problems)
    return (
        f"{filename} 里是这一章的上一稿，检查出下面这些问题。先读它，在原稿基础上逐条改正，其余内容保持不变，"
        f"然后把整章写回 {filename}（可以用 edit 局部修改）：\n{listed}"
    )
