"""Checking one written chapter (PLAN 15.4.11 step 5; after Self-Refine and Chain of Density: the
feedback is a concrete list, never "write more").

- every point the plan gives the chapter is marked in a data-points attribute (the second level of
  coverage; the ledger itself was the first);
- a marked point is really there: its wording shows up in the marking elements (character bigrams);
- the chapter does not paste the spoken transcript (runs of 30+ identical characters);
- every point gets enough words for what the video says about it. The bar lives only here (never
  in a prompt or in the feedback: a stated minimum becomes the finish line, D-44); it grows with the
  point's own source, so long and short videos need no separate numbers, and the feedback names the
  steps of depth.md to add instead of a count.
"""

import re

from prometheus.report.evaluation import parse_html

GROUNDING_MIN = 0.3      # share of a point's bigrams found in the text that marks it
COPY_RUN = 30            # identical characters that count as pasted
COPY_MAX = 0.15          # pasted share of the chapter that asks for a rewrite
THIN_BASE = 24           # the bar for a point the video only mentions (to calibrate, D-44)
THIN_RATIO = 1.0         # the bar per unit of what the video says about the point (to calibrate, D-44)
SOURCE_WORD = 1.5        # an English word of the source counts as this many characters of Chinese
_NOT_WORDY = re.compile(r"[^一-鿿A-Za-z0-9]")
_CJK = re.compile(r"[一-鿿]")
_WORD = re.compile(r"[A-Za-z0-9]+")
_FRAME_USED = re.compile(r"""src=["']frames/([^"']+)["']""")
_FRAME_DECLINED = re.compile(r"<!--\s*不用\s*(f_\d+\.jpg)\s*[：:]\s*\S")


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


def _size(text: str, *, word: float = 1.0) -> float:
    return len(_CJK.findall(text or "")) + word * len(_WORD.findall(text or ""))


def point_chars(fragment: str) -> dict:
    """{point id: how much text explains it}: an element's own text (not that of marked elements
    inside it), shared equally by the points it marks."""
    sizes: dict = {}
    for node in parse_html(fragment).walk():
        ids = (node.attrs.get("data-points") or "").split()
        if not ids:
            continue
        own = _size(node.text(lambda inner: bool(inner.attrs.get("data-points"))))
        for point_id in ids:
            sizes[point_id] = sizes.get(point_id, 0.0) + own / len(ids)
    return sizes


def _bar(source: str) -> float:
    return max(THIN_BASE, THIN_RATIO * _size(source, word=SOURCE_WORD))


def unused_frames(fragment: str, frames) -> list:
    """Informative frames of the ledger neither shown nor declined with a reason (<!-- 不用 f_…：… -->)."""
    shown = set(_FRAME_USED.findall(fragment)) | set(_FRAME_DECLINED.findall(fragment))
    return [frame["file"] for frame in frames or [] if frame.get("useful") and frame["file"] not in shown]


def check_chapter(fragment: str, owned: list, points: dict, transcript: str, *, sources=None, frames=None) -> dict:
    """`sources`: {point id: the text of the units it rests on}; without it there is no length check.
    `frames`: the chapter's frame ledger (figures/notes.py); without it frames are not checked."""
    marking = _marking(fragment)
    root = parse_html(fragment)
    text = root.text(lambda node: node.tag == "h2")
    missing = [point_id for point_id in owned if point_id not in marking]
    weak = [point_id for point_id in owned if point_id in marking and not _grounded(points[point_id], marking[point_id])]
    copy_ratio = _copy_ratio(text, transcript)
    chars = len(_CJK.findall(text))
    sizes = point_chars(fragment)
    thin = [point_id for point_id in owned if sources and point_id in marking and point_id not in weak
            and sizes.get(point_id, 0.0) < _bar(sources.get(point_id, ""))]
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
    for point_id in thin:
        problems.append(f"要点 {point_id} 讲得太简略，比视频里讲的少（{points[point_id]['text']}）：按 depth.md 的四步补全——"
                        "一句话说清是什么；类比到读者熟悉的东西；展开原理、理由、条件和例子；"
                        "最后说所以呢：它对读者意味着什么、和前后要点是什么关系。讲到零基础读者能自己复述为止")
    unused = unused_frames(fragment, frames)
    by_file = {frame["file"]: frame for frame in frames or []}
    for file in unused:
        frame = by_file[file]
        problems.append(f"候选帧 {file}（{frame['label']}，{frame['kind']}：{frame['what']}）没有用上：在讲到它的段落后面配上这张图，"
                        f"图注写画面里的关键信息；如果它和已用的图是同一个画面，或者正文已经完整写出了它的信息，"
                        f"就在片段里写一行 <!-- 不用 {file}：理由 -->")
    return {"missing": missing, "weak": weak, "thin": thin, "unused_frames": unused, "copy_ratio": copy_ratio,
            "chars": chars, "problems": problems}


def feedback_prompt(problems: list, filename: str, draft: str = "") -> str:
    """With `draft` the previous version rides along, so the run spends no turn reading it back."""
    listed = "".join(f"- {problem}\n" for problem in problems)
    if draft:
        return (
            f"### 上一稿（{filename} 现在的内容）\n{draft}\n\n"
            f"上面这一稿检查出下面这些问题。在原稿基础上逐条改正，其余内容保持不变，"
            f"然后把整章写回 {filename}（可以用 edit 局部修改）：\n{listed}"
        )
    return (
        f"{filename} 里是这一章的上一稿，检查出下面这些问题。先读它，在原稿基础上逐条改正，其余内容保持不变，"
        f"然后把整章写回 {filename}（可以用 edit 局部修改）：\n{listed}"
    )


def point_items(text: str) -> list:
    return []
