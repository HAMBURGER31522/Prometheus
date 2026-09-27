"""Knowledge-tree mind maps: parse and validate the model's JSON (PLAN 15.4.2).

Node = {"label", "type": root|theme|topic|leaf, "summary", "time", "children"}.
Every rule here is deterministic, so a failed check can be fed back to the model
verbatim for its one retry.
"""

import json

THEMES = (3, 6)
MAX_DEPTH = 4                 # root -> theme -> topic -> leaf
MAX_LABEL = 20
MAX_ROOT_LABEL = 40
MAX_SUMMARY = 60
MAX_THEME_SUMMARY = 40  # themes stay short; leaves grow (PLAN 15.4.9)
TIME_SLACK_S = 5              # section ranges are rounded to whole seconds
MIN_COVERAGE = 0.8
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


def _walk(node: dict, depth: int, errors: list, leaves: list) -> None:
    kind = node.get("type")
    label = str(node.get("label") or "")
    summary = str(node.get("summary") or "")
    children = node.get("children") or []
    limit = MAX_ROOT_LABEL if kind == "root" else MAX_LABEL
    if not label:
        errors.append(f"第 {depth} 层有节点缺少 label")
    elif len(label) > limit:
        errors.append(f"节点「{label[:12]}…」的 label 超过 {limit} 字")
    if kind != "root" and not summary:
        errors.append(f"节点「{label}」缺少 summary")
    elif len(summary) > (limit := MAX_THEME_SUMMARY if kind == "theme" else MAX_SUMMARY):
        errors.append(f"节点「{label}」的 summary 超过 {limit} 字")
    if depth > MAX_DEPTH:
        errors.append(f"节点「{label}」超过 {MAX_DEPTH} 层（root → theme → topic → leaf）")
        return
    if kind == "leaf":
        leaves.append(node)
    for child in children:
        if child.get("type") not in _CHILD_TYPES.get(kind, set()):
            errors.append(f"「{label}」（{kind}）下不能挂 {child.get('type')} 节点「{child.get('label')}」，"
                          f"也就是层级超过 {MAX_DEPTH} 层或类型错误")
        _walk(child, depth + 1, errors, leaves)


def validate_tree(tree: dict, outline: dict) -> list:
    """Human-readable problems; an empty list means the tree is usable."""
    errors: list = []
    root = tree.get("root") if isinstance(tree, dict) else None
    if not isinstance(root, dict) or root.get("type") != "root":
        return ["缺少 type 为 root 的根节点"]
    themes = root.get("children") or []
    if not THEMES[0] <= len(themes) <= THEMES[1]:
        errors.append(f"一级主题数量 {len(themes)} 不在 {THEMES[0]}-{THEMES[1]} 之间")
    leaves: list = []
    _walk(root, 1, errors, leaves)

    ranges = _ranges(outline)
    covered = set()
    for leaf in leaves:
        time = leaf.get("time")
        if not isinstance(time, (int, float)):
            errors.append(f"叶子「{leaf.get('label')}」没有时间（time 秒数）")
            continue
        hits = [index for index, (start, end) in enumerate(ranges)
                if start - TIME_SLACK_S <= time <= end + TIME_SLACK_S]
        if ranges and not hits:
            errors.append(f"叶子「{leaf.get('label')}」的时间 {time} 不在任何章节的时间范围内")
        covered.update(hits)
    if ranges and len(covered) / len(ranges) < MIN_COVERAGE:
        errors.append(f"叶子只覆盖了 {len(covered)}/{len(ranges)} 个章节，至少要覆盖 80%")
    return errors
