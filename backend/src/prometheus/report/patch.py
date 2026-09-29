"""Patching a finished 完整 report by the newer rules (PLAN 15.4.11a-5, user 2026-09-29).

The published 精读 is split back into its chapters and each is checked with the kept key-point
ledger (lists and reasons item by item, hollow and thin points); what fails gets one targeted run,
then every chapter gets an editor's-viewpoint pass and its links are verified. No key points are
extracted again, nothing is planned again, no chapter is written again. Embedded pictures go back
to files first, so prompts stay small, and finalize puts them inline again.
"""

import base64
import html as html_lib
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prometheus.report import chapter_checks, chapter_write, viewpoints
from prometheus.report import plan as planning
from prometheus.report.full import (
    DEPTH_MD,
    _digest,
    _failing,
    _lost,
    _marked,
    _prepare,
    _read_json,
    _write_json,
)

_SECTION = re.compile(r'<section id="s(\d+)"[^>]*>.*?</section>', re.DOTALL)
_TITLE = re.compile(r'<span class="section-title">(.*?)</span>', re.DOTALL)
_TIME = re.compile(r'<span class="section-time">(.*?)</span>', re.DOTALL)
_RANGE = re.compile(r"(\d{1,2}(?::\d{2}){1,2})\s*[–—~-]\s*(\d{1,2}(?::\d{2}){1,2})")
_DATA_IMAGE = re.compile(r'src="data:image/(jpeg|jpg|png);base64,([A-Za-z0-9+/=]+)"')
_TAG = re.compile(r"<[^>]+>")


def split_report(html: str) -> list:
    """[{number, title, ranges, fragment}] for the chapter sections of an assembled report."""
    chapters = []
    for match in _SECTION.finditer(html):
        fragment = match.group(0)
        title = _TITLE.search(fragment)
        time = _TIME.search(fragment)
        ranges = [[start, end] for start, end in _RANGE.findall(time.group(1))] if time else []
        chapters.append({"number": int(match.group(1)), "fragment": fragment, "ranges": ranges,
                         "title": html_lib.unescape(_TAG.sub("", title.group(1))).strip() if title else ""})
    return chapters


def extract_images(html: str, folder) -> tuple:
    """(html with frames/embedded-NN.* instead of data URIs, count): finalize inlines them again."""
    folder = Path(folder)
    count = 0

    def to_file(match: re.Match) -> str:
        nonlocal count
        count += 1
        name = f"embedded-{count:02d}.{'png' if match.group(1) == 'png' else 'jpg'}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(base64.b64decode(match.group(2)))
        return f'src="frames/{name}"'

    return _DATA_IMAGE.sub(to_file, html), count


def _source(point: dict, units: list, index: dict) -> str:
    first, last = (index.get(unit_id) for unit_id in point["units"])
    return "".join(unit.get("canonical_text", "") for unit in units[first:last + 1]) if first is not None else ""


def _patch_one(work: Path, chapter: dict, total: int, owned: list, points: dict, units: list, run_pi, *,
               verify_links, progress) -> dict:
    number, fragment = chapter["number"], chapter["fragment"]
    filename = f"ch-{number:02d}.html"
    depth = DEPTH_MD.read_text(encoding="utf-8")
    key = _digest(fragment, owned, depth)
    record = work / "patch" / f"ch-{number:02d}.json"
    done = _read_json(record)
    if isinstance(done, dict) and done.get("key") == key and "unverified" in done:
        return _verified(done, verify_links)
    index = {unit["unit_id"]: position for position, unit in enumerate(units)}
    sources = {point_id: _source(points[point_id], units, index) for point_id in owned}
    mine = chapter_write.chapter_units({"ranges": chapter["ranges"]}, owned, points, units) if chapter["ranges"] else []
    spoken = "".join(unit.get("canonical_text", "") for unit in mine)
    space = work / "patch" / f"ch-{number:02d}"
    _prepare(space, figures=False)
    (space / filename).write_bytes(fragment.encode("utf-8"))

    def write(prompt: str) -> str:
        return run_pi(space, prompt, filename).read_text(encoding="utf-8")

    def recheck(text: str) -> dict:
        return chapter_checks.check_chapter(text, owned, points, spoken, sources=sources)

    def keep_if_not_worse(revised: str, check: dict) -> tuple:
        again = recheck(revised)
        if _lost(again) <= _lost(check):
            return revised, again
        (space / filename).write_bytes(fragment.encode("utf-8"))
        return fragment, check

    check = recheck(fragment)
    failing = _failing(check, points, sources)
    if failing:
        progress("补写", number, total)
        fragment, check = keep_if_not_worse(
            write(chapter_write.targeted_prompt(depth, fragment, failing, filename)), check)
    progress("编者观点", number, total)
    fragment, check = keep_if_not_worse(write(chapter_write.viewpoint_prompt(depth, fragment, filename)), check)
    result = {"key": key, "number": number, "title": chapter["title"], "points": owned, "original": chapter["fragment"],
              "unverified": fragment, "check": check, "targeted": bool(failing)}
    _write_json(record, result)
    return _verified(result, verify_links)


def _verified(result: dict, verify_links) -> dict:
    """The links are checked afresh on every patch, from the draft kept before verification: a fixed
    verifier or a page that went away needs no model call (15.4.11a-4)."""
    fragment, links = result["unverified"], dict.fromkeys(viewpoints.STATS, 0)
    if verify_links is not None:
        fragment, links = viewpoints.verify(fragment, verify_links)
    return {**result, "fragment": fragment, "links": links}


def patch_report(work, html: str, ledger: dict, units: list, run_pi, *, skipped, verify_links, progress,
                 workers: int = 3) -> dict:
    """report.html and coverage.json for the patched report; `skipped`: the old coverage's skip list."""
    work = Path(work)
    if not _marked(html):
        raise ValueError("这份精读里没有 data-points 标注：只能补「完整」模式写的报告")
    html, _count = extract_images(html, work / "frames")
    chapters = split_report(html)
    points = {point["id"]: point for point in ledger["points"]}
    skipped_entries = [entry for entry in skipped or [] if isinstance(entry, dict)]
    skipped_ids = {entry["id"] if isinstance(entry, dict) else entry for entry in skipped or []}
    marked = _marked(html) & set(points)
    plan = {"chapters": [{"id": f"c{c['number']}", "title": c["title"], "ranges": c["ranges"]}
                         for c in chapters if c["ranges"]]}
    by_time = planning.assign(plan, ledger) if plan["chapters"] else {}
    order = {point["id"]: position for position, point in enumerate(ledger["points"])}

    def owned(chapter: dict) -> list:
        here = _marked(chapter["fragment"]) & set(points)
        lost = {point_id for point_id in by_time.get(f"c{chapter['number']}", [])
                if point_id not in marked and point_id not in skipped_ids}
        return sorted(here | lost, key=order.get)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda chapter: _patch_one(
            work, chapter, len(chapters), owned(chapter), points, units, run_pi,
            verify_links=verify_links, progress=progress), chapters))
    page = html
    for result in results:
        page = page.replace(result["original"], result["fragment"], 1)
    (work / "report.html").write_bytes(page.encode("utf-8"))
    written = _marked(page) & set(points)
    coverage = {
        "points_total": len(points), "written": len(written), "skipped": skipped_entries,
        "uncovered": [{"id": point_id, "text": point["text"], "start_ms": point["start_ms"], "end_ms": point["end_ms"]}
                      for point_id, point in points.items() if point_id not in written and point_id not in skipped_ids],
        "patched": [{"number": r["number"], "title": r["title"], "points": len(r["points"]), "targeted": r["targeted"],
                     "missing": r["check"]["missing"], "weak": r["check"]["weak"], "thin": r["check"]["thin"],
                     "incomplete": r["check"].get("incomplete", {}), "links": r["links"]} for r in results],
        "viewpoints": {name: sum(r["links"].get(name, 0) for r in results)
                       for name in viewpoints.STATS},
    }
    _write_json(work / "coverage.json", coverage)
    return coverage
