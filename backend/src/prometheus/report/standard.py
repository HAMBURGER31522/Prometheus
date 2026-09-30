"""「标准」精读 (PLAN 15.4.15-10): VRA writes the report in one go as its own 精读; then every chapter gets an
editor's-viewpoint pass of its own under 完整's rules (a confidence and a source for every point, the links
opened and checked), and a report of two chapters or more gets the template's jump TOC.

VRA's chapters are `<section aria-labelledby="sN-title">` with a section-title, not the `id="sN"` sections
完整 assembles, and a short video came back without a TOC (BV1EJ4m1t7Zs, 2026-09-30)."""

import html as html_lib
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prometheus.report import chapter_write, viewpoints
from prometheus.report.full import CHAPTERS_AT_ONCE, DEPTH_MD, Gate, _written
from prometheus.report.patch import extract_images
from prometheus.report.pi_run import stage_skill

_SECTION = re.compile(r"<section\b[^>]*>.*?</section>", re.DOTALL)
_TITLE = re.compile(r'<span class="section-title">(.*?)</span>', re.DOTALL)
_ID = re.compile(r'\bid="([^"]+)"')
_ASIDE = re.compile(r'<aside class="viewpoint">.*?</aside>', re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_RULES = "## 编者观点（非视频内容）"
# A pass that leaves less than this share of the chapter's own text rewrote it: the chapter stays as it was.
KEEP_TEXT = 0.9


def chapters(html: str) -> list:
    """[{number, title, id, fragment}] for the sections that carry a chapter title, in order."""
    found = []
    for match in _SECTION.finditer(html):
        fragment = match.group(0)
        title = _TITLE.search(fragment)
        if not title:
            continue
        opening = _ID.search(fragment[: fragment.index(">") + 1])
        found.append({"number": len(found) + 1, "fragment": fragment, "id": opening.group(1) if opening else None,
                      "title": html_lib.unescape(_TAG.sub("", title.group(1))).strip()})
    return found


def add_nav(html: str) -> str:
    """The template's `.report-nav` before the first chapter, each chapter given an id when it has none."""
    found = chapters(html)
    if 'class="report-nav"' in html or len(found) < 2:
        return html
    page, links, first = html, [], None
    for chapter in found:
        target = chapter["id"] or f"s{chapter['number']}"
        fragment = chapter["fragment"]
        if not chapter["id"]:
            fragment = fragment.replace("<section", f'<section id="{target}"', 1)
            page = page.replace(chapter["fragment"], fragment, 1)
        first = first or fragment
        links.append(f'<a href="#{target}">{html_lib.escape(chapter["title"])}</a>')
    nav = ('<nav class="report-nav" aria-label="章节导航"><span class="report-nav-title">目录</span>'
           + "".join(links) + "</nav>")
    at = page.index(first)
    return page[:at] + nav + page[at:]


def viewpoint_rules() -> str:
    """depth.md's 「编者观点」 section alone: the rest is how 完整 writes, not for a chapter VRA wrote."""
    depth = DEPTH_MD.read_text(encoding="utf-8")
    start = depth.index(_RULES)
    end = depth.find("\n## ", start + len(_RULES))
    return depth[start:end if end >= 0 else None].strip()


def _own_text(fragment: str) -> int:
    return len("".join(_TAG.sub("", _ASIDE.sub("", fragment)).split()))


def _one(work: Path, chapter: dict, total: int, rules: str, run_pi, verify_links, progress) -> tuple:
    """(fragment, link stats, 1 if the pass was undone)."""
    number, original = chapter["number"], chapter["fragment"]
    filename = f"ch-{number:02d}.html"
    space = work / "viewpoints" / f"ch-{number:02d}"
    space.mkdir(parents=True, exist_ok=True)
    stage_skill(space)  # Pi is started with the workspace's SKILL.md
    (space / filename).write_bytes(original.encode("utf-8"))
    progress("编者观点", number, total)
    fragment = _written(run_pi, space, chapter_write.viewpoint_prompt(rules, original, filename),
                        filename).read_text(encoding="utf-8")
    links = dict.fromkeys(viewpoints.STATS, 0)
    if not fragment.lstrip().startswith("<section") or _own_text(fragment) < KEEP_TEXT * _own_text(original):
        return original, links, 1
    if verify_links is not None:
        fragment, links = viewpoints.verify(fragment, verify_links)
    return fragment, links, 0


def add_viewpoints(work, run_pi, *, verify_links, progress, gate=None) -> dict:
    """work/report.html with an editor's-viewpoint pass on every chapter (five at a time) and a jump TOC."""
    work = Path(work)
    report = work / "report.html"
    html, _count = extract_images(report.read_text(encoding="utf-8"), work / "frames")  # finalize inlines them
    found = chapters(html)
    rules, gate = viewpoint_rules(), gate or Gate()

    def one(chapter: dict) -> tuple:
        with gate:
            return _one(work, chapter, len(found), rules, run_pi, verify_links, progress)

    with ThreadPoolExecutor(max_workers=CHAPTERS_AT_ONCE) as pool:
        results = list(pool.map(one, found))
    page, stats = html, {**dict.fromkeys(viewpoints.STATS, 0), "reverted": 0}
    for chapter, (fragment, links, reverted) in zip(found, results, strict=True):
        page = page.replace(chapter["fragment"], fragment, 1)
        stats["reverted"] += reverted
        for name in viewpoints.STATS:
            stats[name] += links.get(name, 0)
    report.write_bytes(add_nav(page).encode("utf-8"))
    return stats
