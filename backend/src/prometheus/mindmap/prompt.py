"""Mind map prompt adapted from BiliSum's knowledge-tree rules (PLAN 15.4.2).

BiliSum (lycohana/BiliSum, pipeline/real.py) asks for a semantic knowledge
tree instead of a re-levelled table of contents; these rules keep that idea but
feed it the finished report and require real section times on every leaf.
"""

from prometheus.mindmap import tree as tree_rules


def _format_seconds(seconds) -> str:
    seconds = int(seconds or 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def build_prompt(outline: dict) -> str:
    lines = [
        "把下面这篇精读报告整理成一棵适合学习复盘的思维导图知识树。",
        "",
        "写作规则：",
        ("1. 先做语义归纳，再组织层级：以概念、方法、例子、条件、结论之间的关系为骨架，"
         "不要把章节标题原样平移成节点；讲同一概念或同一类例子的多个章节要合并。"),
        f"2. 根节点 root 是整支视频真正的主题，label 不超过 {tree_rules.MAX_ROOT_LABEL} 字。",
        (f"3. 一级主题 theme 给 {tree_rules.THEMES[0]}-{tree_rules.THEMES[1]} 个，彼此区分明显，覆盖主要内容；"
         "不要用「其他」「更多」这类空泛名字凑数。"),
        "4. topic 只在某个 theme 下确实有两三类不同子议题时才出现，否则直接挂 leaf。",
        f"5. 最深 {tree_rules.MAX_DEPTH} 层：root → theme → topic → leaf。",
        f"6. 每个节点 label 不超过 {tree_rules.MAX_LABEL} 字，具体、一眼能懂，禁止「第一部分」「Part 1」这类占位。",
        (f"7. 除 root 外每个节点都要有 summary，越往外越具体：theme 只点题（不超过 {tree_rules.MAX_THEME_SUMMARY} 字），"
         f"topic 和 leaf 不超过 {tree_rules.MAX_SUMMARY} 字，直接写信息本体：定义、数字、条件、结论。"
         "leaf 之后还会依据报告原文单独补充详解，这里不必写长。"),
        "8. 每个 leaf 必须有 time：一个秒数，落在它所依据章节的时间范围内（见下方章节列表）。",
        f"9. leaf 要覆盖至少 {int(tree_rules.MIN_COVERAGE * 100)}% 的章节，但不要把每句话都变成节点。",
        "10. 教程和知识讲解提炼知识结构；评论和资讯提炼观点结构与因果关系。不写报告里没有的内容。",
        "",
        "只输出 JSON，不要输出任何说明文字。格式：",
        ('{"title": "导图标题", "root": {"label": "根主题", "type": "root", "summary": "一句话", "time": null, '
         '"children": [{"label": "主题", "type": "theme", "summary": "…", "time": null, "children": ['
         '{"label": "要点", "type": "leaf", "summary": "…", "time": 125, "children": []}]}]}}'),
        "",
        f"报告标题：{outline.get('title', '')}",
        f"导语：{outline.get('intro', '')[:600]}",
        "",
        "章节（时间范围 · 标题 · 小节 · 正文摘录）：",
    ]
    for section in outline.get("sections", []):
        if section.get("start_s") is None:
            span = "（无时间）"
        else:
            end = section["end_s"] if section.get("end_s") is not None else section["start_s"]
            span = f"{_format_seconds(section['start_s'])}–{_format_seconds(end)}"
        lines.append(f"- {span} · {section['title']}")
        if section.get("h3"):
            lines.append(f"  小节：{'；'.join(section['h3'])}")
        if section.get("text"):
            lines.append(f"  正文：{section['text']}")
    return "\n".join(lines)
