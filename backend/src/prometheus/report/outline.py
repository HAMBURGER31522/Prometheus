"""Report outline: h1, intro, every h2 with its section time, h3 titles (PLAN 8.8).

Shared by classification and mind maps, so it lives with the report.
"""

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
        sections.append({"title": clean_title, "start_label": start_label, "h3": h3s,
                         "start_s": None, "end_s": None, "text": ""})
    return {"title": title, "intro": intro, "sections": sections}
