"""The key-point ledger (PLAN 15.4.11 step 2; after FActScore's atomic facts and FineSurE's key facts).

Each ~5-minute block of the transcript gets one model call listing every point of substance, with
the units it rests on and a verbatim anchor, and the skipped stretches with a reason. The program
checks every point against the transcript, asks once more about the bad ones and once more about
stretches of 30 s or longer that nothing covers, then numbers the points K001… in time order. The
chapter writers must then account for every point (data-points), which is what 要点覆盖率 counts.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

from prometheus.llm.replies import first_json_object
from prometheus.report.chunks import chunk_units

TYPES = ("定义", "论断", "理由", "例子", "数字", "人名书名", "步骤", "条件", "推导", "经历", "问答")
SKIP_REASONS = ("口头禅", "寒暄与课堂管理", "广告推广", "重复", "离题闲聊", "技术故障")
ANCHOR_SIMILARITY = 0.8
MIN_ANCHOR = 4
MIN_UNASSIGNED_S = 30
_NOT_WORDY = re.compile(r"[^一-鿿A-Za-z0-9]")


def _clock(ms: int) -> str:
    seconds = int(ms // 1000)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _lines(block: list) -> str:
    return "\n".join(f"[{u['unit_id']} {_clock(u['start_ms'])}] {u.get('canonical_text', '')}" for u in block)


def keypoint_prompt(block: list, *, note: str = "") -> str:
    return (
        "下面是一段视频转写（约 5 分钟），每行开头是单元编号和时间。请列出这一段里**所有**有实质内容的要点，"
        "一个都不要漏：\n"
        f"- type 只能是：{'、'.join(TYPES)}；\n"
        "- text 用一两句能独立看懂的话写清这个要点（写明主语和对象，不写「讲者说」）；\n"
        '- units 写出这个要点依据的起止单元编号，例如 ["unit-000120", "unit-000126"]；\n'
        "- anchor 从这些单元里照抄一句原话（10–30 字，保持原样，识别错字也照抄）；\n"
        f"- 不算要点的片段放进 skips，reason 只能是：{'、'.join(SKIP_REASONS)}；\n"
        "- 这一段的每个单元，都要么属于某个要点，要么落在某个 skips 片段里。\n"
        + note
        + '只输出 JSON：{"points": [{"type": "定义", "text": "…", "units": ["unit-000120", "unit-000126"], '
        '"anchor": "…"}], "skips": [{"units": ["unit-000127", "unit-000130"], "reason": "寒暄与课堂管理"}]}\n\n'
        f"转写：\n{_lines(block)}\n"
    )


def _norm(text: str) -> str:
    return _NOT_WORDY.sub("", (text or "").lower())


def _span(ids: list, index: dict):
    picked = [index[unit_id] for unit_id in ids if unit_id in index]
    if not ids or len(ids) > 2 or len(picked) != len(ids):
        return None
    return min(picked), max(picked)


def _anchored(anchor: str, block: list, span: tuple) -> bool:
    """The anchor is (nearly) verbatim in the point's units, one unit of slack on each side."""
    wanted = _norm(anchor)
    if len(wanted) < MIN_ANCHOR:
        return False
    low, high = max(0, span[0] - 1), min(len(block) - 1, span[1] + 1)
    text = _norm("".join(unit.get("canonical_text", "") for unit in block[low:high + 1]))
    if wanted in text:
        return True
    size = len(wanted)
    return any(SequenceMatcher(None, wanted, text[start:start + size]).ratio() >= ANCHOR_SIMILARITY
               for start in range(max(1, len(text) - size + 1)))


def parse_points(text: str, block: list) -> tuple:
    """(points, skips, problems) from one reply, every point checked against the block."""
    value = first_json_object(text or "")
    if not isinstance(value, dict):
        return [], [], ["回复不是合法 JSON"]
    index = {unit["unit_id"]: position for position, unit in enumerate(block)}
    points, skips, problems = [], [], []
    for number, item in enumerate(value.get("points") or [], 1):
        item = item if isinstance(item, dict) else {}
        kind, body, anchor = (str(item.get(key) or "").strip() for key in ("type", "text", "anchor"))
        span = _span([u for u in item.get("units") or [] if isinstance(u, str)], index)
        if kind not in TYPES:
            problems.append(f"要点 {number}：类型「{kind}」不在允许的范围里")
        elif not body:
            problems.append(f"要点 {number}：没有写要点内容")
        elif span is None:
            problems.append(f"要点 {number}：units 不是这一段里的一两个单元编号")
        elif not _anchored(anchor, block, span):
            problems.append(f"要点 {number}：原话锚点「{anchor[:30]}」在这些单元里找不到")
        else:
            points.append({"type": kind, "text": body, "anchor": anchor,
                           "units": [block[span[0]]["unit_id"], block[span[1]]["unit_id"]]})
    for number, item in enumerate(value.get("skips") or [], 1):
        item = item if isinstance(item, dict) else {}
        reason = str(item.get("reason") or "").strip()
        span = _span([u for u in item.get("units") or [] if isinstance(u, str)], index)
        if reason not in SKIP_REASONS:
            problems.append(f"跳过 {number}：理由「{reason}」不在允许的范围里")
        elif span is None:
            problems.append(f"跳过 {number}：units 不是这一段里的一两个单元编号")
        else:
            skips.append({"units": [block[span[0]]["unit_id"], block[span[1]]["unit_id"]], "reason": reason})
    return points, skips, problems


def unassigned(block: list, points: list, skips: list, *, min_seconds: float = MIN_UNASSIGNED_S) -> list:
    """(first, last) unit ids of the stretches no point or skip covers, when they last long enough."""
    index = {unit["unit_id"]: position for position, unit in enumerate(block)}
    covered: set = set()
    for entry in list(points) + list(skips):
        span = _span(entry.get("units") or [], index)
        if span:
            covered.update(range(span[0], span[1] + 1))
    stretches, start = [], None
    for position in range(len(block) + 1):
        if position < len(block) and position not in covered:
            start = position if start is None else start
            continue
        if start is not None:
            end = position - 1
            if block[end]["end_ms"] - block[start]["start_ms"] >= min_seconds * 1000:
                stretches.append((block[start]["unit_id"], block[end]["unit_id"]))
            start = None
    return stretches


def _one_block(block: list, ask) -> tuple:
    points, skips, problems = parse_points(ask(keypoint_prompt(block)), block)
    if problems:
        note = ("上次的问题（改正后把这一段的要点和跳过片段完整重列一遍）：\n"
                + "".join(f"- {problem}\n" for problem in problems))
        again, again_skips, problems = parse_points(ask(keypoint_prompt(block, note=note)), block)
        points, skips = again or points, again_skips or skips
    gaps = unassigned(block, points, skips)
    if gaps:
        index = {unit["unit_id"]: position for position, unit in enumerate(block)}
        missing = [block[position] for first, last in gaps for position in range(index[first], index[last] + 1)]
        note = "下面这些片段在上次的回答里没有归属：为它们补充要点，或写明跳过理由。\n"
        more, more_skips, more_problems = parse_points(ask(keypoint_prompt(missing, note=note)), missing)
        points, skips, problems = points + more, skips + more_skips, problems + more_problems
        gaps = unassigned(block, points, skips)
    return points, skips, problems, gaps


def build_ledger(units: list, ask, *, seconds: float = 300, workers: int = 3) -> dict:
    times = {unit["unit_id"]: (unit["start_ms"], unit["end_ms"]) for unit in units}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda block: _one_block(block, ask), chunk_units(units, seconds=seconds)))

    def timed(entry: dict) -> dict:
        return {**entry, "start_ms": times[entry["units"][0]][0], "end_ms": times[entry["units"][1]][1]}

    points = sorted((timed(p) for result in results for p in result[0]), key=lambda p: (p["start_ms"], p["end_ms"]))
    for number, point in enumerate(points, 1):
        point["id"] = f"K{number:03d}"
    return {
        "points": [{"id": p.pop("id"), **p} for p in points],
        "skips": sorted((timed(s) for result in results for s in result[1]), key=lambda s: s["start_ms"]),
        "problems": [problem for result in results for problem in result[2]],
        "uncovered": [list(gap) for result in results for gap in result[3]],
    }


def ledger_markdown(ledger: dict) -> str:
    lines = ["# 要点账本", "", f"共 {len(ledger['points'])} 条要点。", ""]
    lines += [f"- {p['id']} [{_clock(p['start_ms'])}–{_clock(p['end_ms'])}]（{p['type']}）{p['text']}"
              f"　原话：「{p['anchor']}」" for p in ledger["points"]]
    if ledger["skips"]:
        lines += ["", "## 跳过的片段", ""]
        lines += [f"- [{_clock(s['start_ms'])}–{_clock(s['end_ms'])}] {s['reason']}" for s in ledger["skips"]]
    return "\n".join(lines) + "\n"


def write_parts(units: list, folder, *, seconds: float = 300) -> list:
    """transcript/part-NN.md: the blocks the chapter writers read before writing."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for number, block in enumerate(chunk_units(units, seconds=seconds), 1):
        path = folder / f"part-{number:02d}.md"
        head = f"# 第 {number} 块 {_clock(block[0]['start_ms'])}–{_clock(block[-1]['end_ms'])}\n\n"
        path.write_bytes((head + _lines(block) + "\n").encode("utf-8"))
        written.append(path)
    return written
