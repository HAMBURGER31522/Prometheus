"""Knowledge-tree mind maps: parse and validate the model's JSON (PLAN 15.4.2).

Node = {"label", "type": root|theme|topic|leaf, "summary", "time", "children"}.
Every rule here is deterministic, so a failed check can be fed back to the model
verbatim for its one retry.
"""

import json

THEMES = (3, 6)
MAX_DEPTH = 4                 # root -> theme -> topic -> leaf
MAX_LABEL = 20
MAX_ROOT_LABEL = 20           # the root is the simplest node (PLAN 15.4.9)
MAX_SUMMARY = 60
MAX_THEME_SUMMARY = 40  # themes stay short; leaves grow (PLAN 15.4.9)
TIME_SLACK_S = 5              # section ranges are rounded to whole seconds
MIN_COVERAGE = 0.8
MINOR_OVER = 1.2          # up to a fifth over a length limit is a small problem (PLAN 15.4.15-11)
_CHILD_TYPES = {"root": {"theme"}, "theme": {"topic", "leaf"}, "topic": {"leaf"}, "leaf": set()}


def parse_tree(text: str):
    """The first complete JSON object in the text that looks like a tree, else None."""
    decoder = json.JSONDecoder()
    text = text or ""
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text, start)
        except ValueError:
            start = text.find("{", start + 1)
            continue
        if isinstance(value, dict) and isinstance(value.get("root"), dict):
            return value
        start = text.find("{", start + 1)
    return None


def _ranges(outline: dict) -> list:
    return [
        (section["start_s"], section["end_s"] if section["end_s"] is not None else section["start_s"])
        for section in outline.get("sections", [])
        if section.get("start_s") is not None
    ]


def _length(problem: str, length: int, limit: int, major: list, minor: list) -> None:
    """Up to a fifth over a limit is a small problem the map is kept with (PLAN 15.4.15-11)."""
    (minor if length <= limit * MINOR_OVER else major).append(problem)


def _walk(node: dict, depth: int, major: list, minor: list, leaves: list) -> None:
    kind = node.get("type")
    label = str(node.get("label") or "")
    summary = str(node.get("summary") or "")
    children = node.get("children") or []
    limit = MAX_ROOT_LABEL if kind == "root" else MAX_LABEL
    if not label:
        major.append(f"第 {depth} 层有节点缺少 label")
    elif len(label) > limit:
        _length(f"节点「{label[:12]}…」的 label 超过 {limit} 字", len(label), limit, major, minor)
    if kind != "root" and not summary:
        major.append(f"节点「{label}」缺少 summary")
    elif len(summary) > (limit := MAX_THEME_SUMMARY if kind == "theme" else MAX_SUMMARY):
        _length(f"节点「{label}」的 summary 超过 {limit} 字", len(summary), limit, major, minor)
    if depth > MAX_DEPTH:
        major.append(f"节点「{label}」超过 {MAX_DEPTH} 层（root → theme → topic → leaf）")
        return
    if kind == "leaf":
        leaves.append(node)
    for child in children:
        if child.get("type") not in _CHILD_TYPES.get(kind, set()):
            major.append(f"「{label}」（{kind}）下不能挂 {child.get('type')} 节点「{child.get('label')}」，"
                         f"也就是层级超过 {MAX_DEPTH} 层或类型错误")
        _walk(child, depth + 1, major, minor, leaves)


def check_tree(tree: dict, outline: dict) -> tuple:
    """(problems that make the map unusable, small ones it can be kept with) (PLAN 15.4.15-11): a node a
    little over a length limit, or a moment between chapters that is still inside the video, is small."""
    major: list = []
    minor: list = []
    root = tree.get("root") if isinstance(tree, dict) else None
    if not isinstance(root, dict) or root.get("type") != "root":
        return ["缺少 type 为 root 的根节点"], []
    themes = root.get("children") or []
    if not THEMES[0] <= len(themes) <= THEMES[1]:
        major.append(f"一级主题数量 {len(themes)} 不在 {THEMES[0]}-{THEMES[1]} 之间")
    leaves: list = []
    _walk(root, 1, major, minor, leaves)

    ranges = _ranges(outline)
    last = max((end for _start, end in ranges), default=0) + TIME_SLACK_S
    covered = set()
    for leaf in leaves:
        time = leaf.get("time")
        if not isinstance(time, (int, float)):
            major.append(f"叶子「{leaf.get('label')}」没有时间（time 秒数）")
            continue
        hits = [index for index, (start, end) in enumerate(ranges)
                if start - TIME_SLACK_S <= time <= end + TIME_SLACK_S]
        if ranges and not hits:
            problem = f"叶子「{leaf.get('label')}」的时间 {time} 不在任何章节的时间范围内"
            (minor if 0 <= time <= last else major).append(problem)
        covered.update(hits)
    if ranges and len(covered) / len(ranges) < MIN_COVERAGE:
        major.append(f"叶子只覆盖了 {len(covered)}/{len(ranges)} 个章节，至少要覆盖 80%")
    return major, minor


def validate_tree(tree: dict, outline: dict) -> list:
    """Human-readable problems, small ones included (they go back to the model too); empty = usable."""
    major, minor = check_tree(tree, outline)
    return major + minor
