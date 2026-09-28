"""Planning a 完整精读 (PLAN 15.4.11 step 3; after LongWriter's plan-then-write and STORM's outline).

One Pi run with the VRA skill reads the key-point ledger and writes plan.json: titles, the lead, the
chapters with their time ranges and expected length, a glossary, the points that move out of their
time's chapter and the points left out with a reason. The program then gives every point to a
chapter by its time (the narrowest chapter containing it, the rule the reader's 在精读中查看 uses)
and names every problem, so the plan can be redone once with them.
"""

import re

from prometheus.llm.replies import first_json_object

PLAN_SKIPS = ("广告推广", "寒暄与课堂管理", "重复", "离题闲聊", "技术故障")
MAX_SKIP_SHARE = 0.25
END_SLACK_S = 2  # a moment this close to a chapter's end belongs to the next one
_CLOCK = re.compile(r"^\d{1,2}(:\d{2}){1,2}$")


def plan_prompt(*, figures: bool) -> str:
    return (
        "本任务按 video-report skill（SKILL.md、modes/standard.md）和 depth.md 写一份完整精读，"
        "但这一步**只做规划**，不写 report.html。\n"
        "先读 input.json、depth.md、keypoints.md（全部要点，按时间排列）；需要时查看 transcript/ 下的分块原文。"
        + ("开了配图：figures.md 说明了候选帧的用法，规划时可以先不看图。" if figures else "")
        + "\n写出 plan.json：\n"
        '{"title": "主标题", "subtitle": "副标题，没有新角度就留空", "lead": "导语：一段话", '
        '"profile": "mechanism|procedure|evidence|argument|narrative", '
        '"chapters": [{"id": "c1", "title": "章节标题", "ranges": [["00:00:00", "00:07:13"]], "target_chars": 1800}], '
        '"moves": {"K045": "c3"}, "glossary": [{"term": "术语", "chapter": "c1"}], '
        '"skips": [{"point": "K012", "reason": "重复", "duplicate_of": "K003"}]}\n'
        "规则：\n"
        "- 章节按内容组织（按 SKILL.md 选 Profile），时间区间可以不连续；每条要点按它的开始时间落进某一章，"
        "需要放到别的章时写进 moves；\n"
        f"- 不写的要点放进 skips，理由只能是：{'、'.join(PLAN_SKIPS)}；「重复」要写 duplicate_of，"
        "指向保留下来的那一条；跳过的要点不能超过四分之一；\n"
        "- target_chars 按要点条数估算，每条 60–150 字；\n"
        "- glossary 列出需要解释的术语，以及在哪一章第一次解释。\n"
    )


def read_plan(text: str):
    value = first_json_object(text or "")
    return value if isinstance(value, dict) else None


def _seconds(label) -> int | None:
    label = str(label or "").strip()
    if not _CLOCK.match(label):
        return None
    total = 0
    for part in label.split(":"):
        total = total * 60 + int(part)
    return total


def chapter_ranges(chapter: dict) -> list | None:
    spans = []
    for span in chapter.get("ranges") or []:
        if not isinstance(span, list | tuple) or len(span) != 2:
            return None
        start, end = _seconds(span[0]), _seconds(span[1])
        if start is None or end is None or end < start:
            return None
        spans.append((start, end))
    return spans or None


def _chapter_at(seconds: float, chapters: list):
    """The narrowest chapter range containing `seconds`, first leaving out ranges it sits in the last
    seconds of (chapters overlap by a second or so; an overview chapter is the least specific)."""
    timed = [(start, end, index, chapter["id"]) for index, chapter in enumerate(chapters)
             for start, end in (chapter_ranges(chapter) or [])]
    for last in (END_SLACK_S, 0):
        inside = [(end - start, -start, index, cid) for start, end, index, cid in timed
                  if start <= seconds <= end - last]
        if inside:
            return min(inside)[3]
    return None


def valid_skips(plan: dict, known: set) -> dict:
    skips = {}
    for skip in plan.get("skips") or []:
        if isinstance(skip, dict) and skip.get("point") in known and skip.get("reason") in PLAN_SKIPS:
            skips[skip["point"]] = skip
    return skips


def assign(plan: dict, ledger: dict) -> dict:
    """{chapter id: [point ids]} for every chapter; legally skipped points belong nowhere."""
    chapters = [c for c in plan.get("chapters") or [] if isinstance(c, dict) and c.get("id")]
    known = {point["id"] for point in ledger["points"]}
    skipped = valid_skips(plan, known)
    moves = {k: v for k, v in (plan.get("moves") or {}).items() if k in known}
    ids = {chapter["id"] for chapter in chapters}
    owned = {chapter["id"]: [] for chapter in chapters}
    for point in ledger["points"]:
        if point["id"] in skipped:
            continue
        target = moves.get(point["id"])
        target = target if target in ids else _chapter_at(point["start_ms"] / 1000, chapters)
        if target is not None:
            owned[target].append(point["id"])
    return owned


def _clock(ms: int) -> str:
    seconds = int(ms // 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}" if seconds < 3600 else \
        f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def validate_plan(plan: dict, ledger: dict) -> list:
    problems = []
    if not str(plan.get("title") or "").strip():
        problems.append("主标题为空")
    if not str(plan.get("lead") or "").strip():
        problems.append("导语为空")
    chapters = [c for c in plan.get("chapters") or [] if isinstance(c, dict)]
    if not chapters:
        problems.append("没有章节")
    seen = set()
    for number, chapter in enumerate(chapters, 1):
        cid = str(chapter.get("id") or "")
        if not cid or cid in seen:
            problems.append(f"第 {number} 章的 id 为空或重复")
        seen.add(cid)
        if not str(chapter.get("title") or "").strip():
            problems.append(f"章节 {cid or number} 没有标题")
        if chapter_ranges(chapter) is None:
            problems.append(f"章节 {cid or number} 的时间区间写法不对（应为 [[\"00:00:00\", \"00:07:13\"]]）")
        target = chapter.get("target_chars")
        if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
            problems.append(f"章节 {cid or number} 的 target_chars 应是正整数")
    by_id = {point["id"]: point for point in ledger["points"]}
    for point_id, chapter_id in (plan.get("moves") or {}).items():
        if point_id not in by_id:
            problems.append(f"moves 里的 {point_id} 不是账本里的要点")
        elif chapter_id not in seen:
            problems.append(f"moves 把 {point_id} 移到了不存在的章节 {chapter_id}")
    skipped = {s.get("point") for s in plan.get("skips") or [] if isinstance(s, dict)}
    for skip in plan.get("skips") or []:
        skip = skip if isinstance(skip, dict) else {}
        point_id, reason = skip.get("point"), skip.get("reason")
        if point_id not in by_id:
            problems.append(f"skips 里的 {point_id} 不是账本里的要点")
        elif reason not in PLAN_SKIPS:
            problems.append(f"跳过 {point_id} 的理由「{reason}」不在允许的范围里（{'、'.join(PLAN_SKIPS)}）")
        elif reason == "重复":
            other = skip.get("duplicate_of")
            if other not in by_id:
                problems.append(f"{point_id} 标为重复，但 duplicate_of 指向的 {other} 不存在")
            elif other in skipped:
                problems.append(f"{point_id} 标为重复，但它指向的 {other} 也被跳过了")
    owned = assign(plan, ledger)
    placed = {point_id for ids in owned.values() for point_id in ids}
    legal = set(valid_skips(plan, set(by_id)))
    for point in ledger["points"]:
        if point["id"] not in placed and point["id"] not in legal:
            problems.append(f"{point['id']}（{_clock(point['start_ms'])}–{_clock(point['end_ms'])}）没有归属章节")
    share = len(legal) / len(by_id) if by_id else 0.0
    if share > MAX_SKIP_SHARE:
        problems.append(f"跳过了 {len(legal)} 条（{share:.0%}），超过 25%，请逐条复核")
    return problems
