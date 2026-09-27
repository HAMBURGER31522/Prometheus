"""思维导图.md: the knowledge tree as a Markdown outline (Obsidian / XMind) (PLAN 15.4.2)."""

import re


def moment_link(platform: str, video_id: str, seconds: float) -> str:
    seconds = int(seconds)
    if platform == "bilibili":
        bare = video_id.split("?")[0]
        page_match = re.search(r"[?&]p=(\d+)", video_id)
        page = page_match.group(1) if page_match else "1"
        return f"https://www.bilibili.com/video/{bare}/?p={page}&t={seconds}"
    return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"


def _stamp(seconds) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _link(node: dict, platform: str, video_id: str) -> str:
    time = node.get("time")
    if not isinstance(time, (int, float)):
        return ""
    return f" [{_stamp(time)}]({moment_link(platform, video_id, time)})"


def tree_to_markdown(tree: dict, platform: str, video_id: str) -> str:
    root = tree["root"]
    lines = [f"# {root['label']}"]
    if root.get("summary"):
        lines += ["", f"> {root['summary']}"]
    for theme in root.get("children") or []:
        lines += ["", f"## {theme['label']}{_link(theme, platform, video_id)}"]
        if theme.get("summary"):
            lines += ["", theme["summary"], ""]
        for child in theme.get("children") or []:
            if child.get("type") == "topic":
                lines += ["", f"### {child['label']}{_link(child, platform, video_id)}"]
                if child.get("summary"):
                    lines += ["", child["summary"], ""]
                leaves = child.get("children") or []
            else:
                leaves = [child]
            for leaf in leaves:
                summary = f"：{leaf['summary']}" if leaf.get("summary") else ""
                lines.append(f"- **{leaf['label']}**{summary}{_link(leaf, platform, video_id)}")
                if leaf.get("detail"):
                    lines.append(f"  {leaf['detail']}")  # continuation of the list item (PLAN 15.4.9)
    return "\n".join(lines).replace("\n\n\n", "\n\n") + "\n"
