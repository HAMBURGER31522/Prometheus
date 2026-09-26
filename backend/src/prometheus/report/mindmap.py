"""Mindmap generation from the final report (PLAN 8.8)."""

import re

SECTION_TIME_RE = re.compile(
    r"(\d{1,2}:\d{2}(?::\d{2})?)\s*[–—-]\s*(\d{1,2}:\d{2}(?::\d{2})?)"
)
_H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _seconds(label: str) -> int:
    parts = [int(p) for p in label.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def extract_outline(html: str) -> dict:
    """h1 + intro + every h2 (title, section-time start) + h3 titles (PLAN 8.8)."""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    title = _TAG_RE.sub("", h1.group(1)).strip() if h1 else ""
    intro_match = re.search(r"</h1>(.*?)(?:<h2|\Z)", html, re.DOTALL)
    intro = _TAG_RE.sub("", intro_match.group(1)).strip() if intro_match else ""

    sections = []
    h2_spans = list(_H2_RE.finditer(html))
    for index, match in enumerate(h2_spans):
        inner = match.group(1)
        heading_text = _TAG_RE.sub("", inner).strip()
        time_match = SECTION_TIME_RE.search(heading_text)
        start_label = time_match.group(1) if time_match else None
        clean_title = SECTION_TIME_RE.sub("", heading_text).strip(" -–—")
        clean_title = re.sub(r"^\d+[.、]?\s*", "", clean_title).strip()
        body_end = h2_spans[index + 1].start() if index + 1 < len(h2_spans) else len(html)
        body = html[match.end():body_end]
        h3s = [
            _TAG_RE.sub("", h).strip()
            for h in re.findall(r"<h3[^>]*>(.*?)</h3>", body, re.DOTALL)
        ]
        sections.append({"title": clean_title, "start_label": start_label, "h3": h3s})
    return {"title": title, "intro": intro, "sections": sections}


def moment_link(platform: str, video_id: str, seconds: float) -> str:
    seconds = int(seconds)
    if platform == "bilibili":
        bare = video_id.split("?")[0]
        page_match = re.search(r"[?&]p=(\d+)", video_id)
        page = page_match.group(1) if page_match else "1"
        return f"https://www.bilibili.com/video/{bare}/?p={page}&t={seconds}"
    return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"


def build_mindmap_prompt(outline: dict, platform: str, video_id: str) -> str:
    lines = [f"报告标题：{outline['title']}"]
    for index, section in enumerate(outline["sections"], start=1):
        start = section["start_label"] or "00:00"
        h, m, s = 0, 0, 0
        parts = [int(p) for p in start.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, s = parts
        link = moment_link(platform, video_id, h * 3600 + m * 60 + s)
        lines.append(f"{index}. 章节「{section['title']}」起点 {start}，时刻链接 {link}")
        if section["h3"]:
            lines.append("   小节：" + "；".join(section["h3"][:8]))
    return (
        "根据报告大纲生成思维导图 Markdown。硬性要求：\n"
        "1. 第一行是 `# ` 加报告标题；\n"
        "2. 恰好 3-7 个 `## ` 一级分支，顺序与大纲章节一致，"
        "每个一级分支行末必须带 `[MM:SS](时刻链接)`，链接用大纲里给的；\n"
        "3. 分支下可用 `### ` 小节与 `- ` 列表，最深到 `####`；\n"
        "4. 每个节点文字不超过 40 个字（不含行末时间链接）；\n"
        "5. 只使用大纲给出的内容，不要编造。\n\n" + "\n".join(lines)
    )


_LINK_RE = re.compile(r"\[(\d{1,2}:\d{2})\]\((<视频时刻链接>|https?://[^)]+)\)\s*$")


def validate_mindmap(text: str, *, expect_title: str, branch_count: tuple = (3, 7)) -> list:
    errors = []
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        errors.append("第一行必须是 `# ` 加报告标题")
    h2_lines = [line for line in lines if line.startswith("## ")]
    if not branch_count[0] <= len(h2_lines) <= branch_count[1]:
        errors.append(f"一级分支数量 {len(h2_lines)} 不在 {branch_count[0]}-{branch_count[1]} 之间")
    for line in h2_lines:
        body = line[3:]
        if not _LINK_RE.search(body):
            errors.append(f"一级分支缺少行末时间链接：{body[:30]}")
            continue
        plain = _LINK_RE.sub("", body).strip()
        if len(plain) > 40:
            errors.append(f"节点超过 40 字：{plain[:30]}")
    # Every node (### / #### / list items) is capped at 40 chars too (PLAN 8.8).
    for line in lines:
        stripped = re.sub(r"^(#{3,4}\s+|-\s+)", "", line).strip()
        if not stripped or stripped.startswith("#"):
            continue
        plain = _LINK_RE.sub("", stripped).strip()
        if len(plain) > 40:
            errors.append(f"节点超过 40 字：{plain[:30]}")
    if re.search(r"^#####", text, re.MULTILINE):
        errors.append("层级超过 ####")
    if expect_title and lines and lines[0].startswith("# ") and expect_title not in lines[0]:
        errors.append("标题与报告不一致")
    return errors
