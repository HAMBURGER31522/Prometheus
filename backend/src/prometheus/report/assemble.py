"""Assembling the chapters into VRA's Standard template (PLAN 15.4.11 step 7).

Each chapter run wrote one <section> fragment; the program fills the template's fields from the
plan and input.json, links the chapters in the template's nav and keeps {{VIDEO_DESCRIPTION}} once
for finalize to fill, exactly as a whole-report run leaves it.
"""

import html as html_lib
import re

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_SECTION_OPEN = re.compile(r"<section\b([^>]*)>", re.IGNORECASE)
_SUBTITLE = re.compile(r"[ \t]*<p class=\"subtitle\">\{\{SUBTITLE\}\}</p>\n?")


def _with_id(fragment: str, number: int) -> str:
    """The chapter's first <section> gets id="s<number>" (the nav's target), whatever it had."""
    def fix(match: re.Match) -> str:
        attributes = re.sub(r'\s+id="[^"]*"', "", match.group(1))
        return f'<section id="s{number}"{attributes}>'

    return _SECTION_OPEN.sub(fix, fragment, count=1)


def assemble(template: str, plan: dict, fragments: list, input_json: dict, *, sources: str) -> str:
    styles = [style for fragment in fragments for style in _STYLE.findall(fragment)]
    chapters = [_with_id(_STYLE.sub("", fragment).strip(), number) for number, fragment in enumerate(fragments, 1)]
    titles = [str(chapter.get("title") or "") for chapter in plan.get("chapters") or []]
    nav = ('<nav class="report-nav" aria-label="章节导航"><span class="report-nav-title">目录</span>'
           + "".join(f'<a href="#s{number}">{html_lib.escape(title)}</a>' for number, title in enumerate(titles, 1))
           + "</nav>")
    page = _COMMENT.sub("", template)
    subtitle = str(plan.get("subtitle") or "").strip()
    page = page.replace("{{SUBTITLE}}", html_lib.escape(subtitle)) if subtitle else _SUBTITLE.sub("", page)
    fields = {
        "{{TITLE}}": html_lib.escape(str(plan.get("title") or "")),
        "{{LEAD}}": html_lib.escape(str(plan.get("lead") or "")),
        "{{ATTRIBUTION}}": html_lib.escape(str(input_json.get("attribution") or "")),
        "{{SOURCES}}": html_lib.escape(sources or ""),
        "{{BODY}}": nav + "\n" + "\n".join(chapters),
    }
    for placeholder, value in fields.items():
        page = page.replace(placeholder, value)
    if styles:
        page = page.replace("</head>", "\n".join(styles) + "\n</head>", 1)
    return page
