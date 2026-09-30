"""The 完整精读 pipeline (PLAN 15.4.11 steps 2–8): the key-point ledger, the plan (redone once with
its problems), one Pi run per chapter checked by the program and revised at most twice, the two-step
讲清楚 review, assembly into VRA's template and coverage.json. finalize then runs as for any report.

The model is injected: ``ask(prompt) -> reply`` for one-shot calls and ``run_pi(workspace, prompt,
expect) -> path`` for Pi runs. Every result is kept under work/ with a digest of what produced it,
so retrying a failed item redoes only what is missing or changed: the relay has no prompt cache and
a long video's chapters are the expensive part (D-44).
"""

import hashlib
import json
import re
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prometheus.figures import notes as frame_notes
from prometheus.report import assemble as assembling
from prometheus.report import chapter_checks, chapter_write, keypoints, viewpoints
from prometheus.report import plan as planning
from prometheus.report import review as reviewing
from prometheus.report.evaluation import parse_html
from prometheus.report.pi_run import SKILL_DIR, PiRunError, stage_skill

DEPTH_MD = Path(__file__).with_name("depth.md")
FIGURES_MD = Path(__file__).parents[1] / "figures" / "figures.md"
MAX_REVISIONS = 2
_PROFILE = re.compile(r"^[a-z]+$")


def _digest(*parts) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(json.dumps(part, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _prepare(space: Path, *, figures: bool) -> None:
    space.mkdir(parents=True, exist_ok=True)
    stage_skill(space)
    shutil.copy2(DEPTH_MD, space / "depth.md")
    if figures:
        shutil.copy2(FIGURES_MD, space / "figures.md")


# ---------- step 2: key points ----------

def run_keypoints(work, units: list, ask) -> dict:
    """keypoints.json, keypoints.md and transcript/part-NN.md; the same transcript reuses the ledger."""
    work = Path(work)
    source = _digest(units)
    saved = _read_json(work / "keypoints.json")
    if isinstance(saved, dict) and saved.get("source") == source:
        ledger = {key: value for key, value in saved.items() if key != "source"}
    else:
        ledger = keypoints.build_ledger(units, ask)
        _write_json(work / "keypoints.json", {**ledger, "source": source})
    (work / "keypoints.md").write_bytes(keypoints.ledger_markdown(ledger).encode("utf-8"))
    keypoints.write_parts(units, work / "transcript")
    return ledger


# ---------- step 3: the plan ----------

def _usable(plan: dict) -> dict:
    """The chapters the writers can work from: a title and readable time ranges."""
    chapters = [chapter for chapter in plan.get("chapters") or []
                if isinstance(chapter, dict) and chapter.get("id") and str(chapter.get("title") or "").strip()
                and planning.chapter_ranges(chapter) is not None]
    return {**plan, "chapters": chapters}


def run_plan(work, ledger: dict, run_pi, *, figures: bool, input_json: dict) -> tuple:
    """(plan, problems left after one redo); raises when there is no usable plan at all."""
    work = Path(work)
    key = _digest(ledger, figures)
    meta, saved = _read_json(work / "plan.meta.json"), _read_json(work / "plan.json")
    if isinstance(meta, dict) and meta.get("key") == key and isinstance(saved, dict):
        return saved, meta.get("problems") or []
    space = work / "plan"
    _prepare(space, figures=figures)
    _write_json(space / "input.json", input_json)
    shutil.copy2(work / "keypoints.md", space / "keypoints.md")
    shutil.copytree(work / "transcript", space / "transcript", dirs_exist_ok=True)
    base = planning.plan_prompt(figures=figures)
    prompt, plan, problems = base, None, []
    for _attempt in range(2):
        plan = planning.read_plan(run_pi(space, prompt, "plan.json").read_text(encoding="utf-8"))
        problems = planning.validate_plan(plan, ledger) if plan is not None else ["plan.json 不是合法的 JSON 对象"]
        if not problems:
            break
        prompt = (base + "\nplan.json 里是上一版规划，检查出下面这些问题。先读它，逐条改正，其余保持不变，"
                  "然后写回 plan.json：\n" + "".join(f"- {problem}\n" for problem in problems))
    if plan is None:
        raise PiRunError("规划失败：两次写出的 plan.json 都不是合法的 JSON")
    plan = _usable(plan)
    if not plan["chapters"]:
        raise PiRunError("规划失败：plan.json 里没有可用的章节")
    _write_json(work / "plan.json", plan)
    _write_json(work / "plan.meta.json", {"key": key, "problems": problems})
    return plan, problems


# ---------- steps 4–6: chapters, checks, review ----------

def _attachments(profile, figures: bool) -> str:
    files = [("SKILL.md", SKILL_DIR / "SKILL.md"), ("modes/standard.md", SKILL_DIR / "modes" / "standard.md"),
             ("assets/report-template.html", SKILL_DIR / "assets" / "report-template.html"), ("depth.md", DEPTH_MD)]
    if isinstance(profile, str) and _PROFILE.match(profile) and (SKILL_DIR / "references" / f"{profile}.md").is_file():
        files.append((f"references/{profile}.md", SKILL_DIR / "references" / f"{profile}.md"))
    if figures:
        files.append(("figures.md", FIGURES_MD))
    return "\n\n".join(f"=== 附件：{name} ===\n{path.read_text(encoding='utf-8')}\n=== 附件结束：{name} ==="
                       for name, path in files)


def _frames_in(work: Path, chapter: dict) -> list:
    """The candidate frames inside the chapter's time ranges."""
    listed = _read_json(work / "frames" / "frames.json") or []
    spans = planning.chapter_ranges(chapter) or []
    return [frame for frame in listed if isinstance(frame, dict)
            and any(start <= float(frame.get("t", -1)) <= end for start, end in spans)
            and (work / "frames" / str(frame.get("file"))).is_file()]


def _copy_frames(work: Path, space: Path, kept: list) -> None:
    """Only the chapter's frames in its workspace, with their own frames.json."""
    target = space / "frames"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    for frame in kept:
        shutil.copy2(work / "frames" / frame["file"], target / frame["file"])
    _write_json(target / "frames.json", kept)


def _frame_ledger(work: Path, space: Path, number: int, kept: list, look):
    """What each of the chapter's frames shows, from one look (多配图 ①); kept per frame list.
    A failed look only means the writer opens the frames itself, as before."""
    record = work / "chapters" / f"ch-{number:02d}.frames.json"
    key = _digest(kept)
    saved = _read_json(record)
    if isinstance(saved, dict) and saved.get("key") == key:
        return saved["notes"]
    if look is None or not kept:
        return None
    _copy_frames(work, space, kept)
    try:
        found = frame_notes.parse_notes(
            look(frame_notes.notes_prompt(kept), [space / "frames" / frame["file"] for frame in kept]), kept)
    except Exception:  # noqa: BLE001 - see the docstring
        return None
    _write_json(record, {"key": key, "notes": found})
    return found


def _lost(check: dict) -> int:
    return (len(check["missing"]) + len(check["weak"]) + len(check["thin"]) + len(check["unused_frames"])
            + sum(len(items) for items in check.get("incomplete", {}).values()))


def _failing(check: dict, points: dict, sources: dict) -> list:
    """The points a targeted run should fix, each with what is wrong and its full source."""
    ids = list(dict.fromkeys(check["missing"] + check["weak"] + check["thin"] + list(check.get("incomplete", {}))))
    return [{"id": point_id, "text": points[point_id]["text"], "source": sources.get(point_id, ""),
             "problem": "；".join(problem for problem in check["problems"] if f"要点 {point_id} " in problem)}
            for point_id in ids]


def _review(fragment: str, check: dict, transcript: str, ask, revise, recheck) -> tuple:
    """(fragment, check, stats, details) after the two-step review and at most one revision; the
    details keep what was asked and how it was judged, so a review that led nowhere can be read."""
    stats = {"questions": 0, "answered": 0, "background": 0, "revised": False, "reverted": False}
    reply = ask(reviewing.reader_prompt(fragment))
    questions, pictures = reviewing.parse_reader(reply, fragment), reviewing.parse_pictures(reply, fragment)
    stats["questions"] = len(questions)
    verdicts, judged = [], ""
    if questions:
        judged = ask(reviewing.judge_prompt(questions, transcript)) or ""
        verdicts = reviewing.parse_judge(judged, len(questions))
    details = {"questions": [{**question, "verdict": verdict} for question, verdict in zip(questions, verdicts)]
               if verdicts else [{**question, "verdict": None} for question in questions],
               "pictures": pictures, "judge_reply": judged}
    kinds = Counter((verdict or {}).get("kind") for verdict in verdicts)
    stats["answered"], stats["background"] = kinds[reviewing.ANSWERED], kinds[reviewing.BACKGROUND]
    fixes = reviewing.fixes(questions, verdicts, pictures)
    if not fixes:
        return fragment, check, stats, details
    revised = revise(fixes)
    stats["revised"] = True
    again = recheck(revised)
    if _lost(again) > _lost(check):  # a clearer chapter must not cost points
        stats["reverted"] = True
        return fragment, check, stats, details
    return revised, again, stats, details


def _write_one(work: Path, plan: dict, number: int, owned: list, points: dict, units: list, run_pi, ask, *,
               attached: str, figures: bool, review: bool, progress, look, verify_links=None) -> dict:
    chapter, total = plan["chapters"][number - 1], len(plan["chapters"])
    filename = f"ch-{number:02d}.html"
    space = work / "chapters" / f"ch-{number:02d}"
    kept = _frames_in(work, chapter) if figures else []
    ledger = _frame_ledger(work, space, number, kept, look) if figures else None
    # a chapter with no frames is not told about frames: the writer went looking anyway (a paid turn)
    base = chapter_write.chapter_prompt(plan, number, owned, points, units, figures=figures and bool(kept),
                                        attached=attached, frame_notes=ledger)
    key = _digest(base, review)
    record = work / "chapters" / f"ch-{number:02d}.json"
    done = _read_json(record)
    if isinstance(done, dict) and done.get("key") == key:
        return done
    _prepare(space, figures=figures)
    if figures:
        _copy_frames(work, space, kept)
    mine = chapter_write.chapter_units(chapter, owned, points, units)
    spoken = "".join(unit.get("canonical_text", "") for unit in mine)
    index = {unit["unit_id"]: position for position, unit in enumerate(units)}
    sources = {point_id: "".join(unit.get("canonical_text", "") for unit in
                                 units[index[points[point_id]["units"][0]]:index[points[point_id]["units"][1]] + 1])
               for point_id in owned}

    def write(prompt: str) -> str:
        return run_pi(space, prompt, filename).read_text(encoding="utf-8")

    def recheck(fragment: str) -> dict:
        return chapter_checks.check_chapter(fragment, owned, points, spoken, sources=sources, frames=ledger)

    progress("写作", number, total)
    fragment = write(base)
    check, rounds = recheck(fragment), 0
    while check["problems"] and rounds < MAX_REVISIONS:
        rounds += 1
        fragment = write(chapter_write.revision_prompt(base, check["problems"], filename, fragment))
        check = recheck(fragment)
    targeted = False
    failing = _failing(check, points, sources)
    if failing:  # still failing after two rounds: one small run for just these points (15.4.11a-3)
        targeted = True
        patched = write(chapter_write.targeted_prompt(DEPTH_MD.read_text(encoding="utf-8"), fragment, failing, filename))
        again = recheck(patched)
        if _lost(again) <= _lost(check):
            fragment, check = patched, again
        else:
            (space / filename).write_bytes(fragment.encode("utf-8"))
    stats = {"questions": 0, "answered": 0, "background": 0, "revised": False, "reverted": False}
    details = None
    if review:
        progress("审校", number, total)
        transcript = "\n".join(unit.get("canonical_text", "") for unit in mine)
        fragment, check, stats, details = _review(
            fragment, check, transcript, ask,
            lambda fixes: write(chapter_write.revision_prompt(base, fixes, filename, fragment)), recheck)
        (space / filename).write_bytes(fragment.encode("utf-8"))
    # every chapter ends with an editor's-viewpoint pass of its own, as --patch does: one-go runs wrote
    # 0–5 boxes where this pass wrote 12–34 (user 2026-09-30); undone if it loses a point
    progress("编者观点", number, total)
    viewed = write(chapter_write.viewpoint_prompt(DEPTH_MD.read_text(encoding="utf-8"), fragment, filename))
    again = recheck(viewed)
    if _lost(again) <= _lost(check):
        fragment, check = viewed, again
    else:
        (space / filename).write_bytes(fragment.encode("utf-8"))
    links = dict.fromkeys(viewpoints.STATS, 0)
    if verify_links is not None:  # the editor's links, opened one by one (15.4.11a-4)
        fragment, links = viewpoints.verify(fragment, verify_links)
        (space / filename).write_bytes(fragment.encode("utf-8"))
    result = {"key": key, "number": number, "id": chapter["id"], "title": chapter["title"], "points": owned,
              "fragment": fragment, "check": check, "rounds": rounds, "targeted": targeted, "review": stats,
              "review_details": details, "links": links}
    _write_json(record, result)
    return result


def write_chapters(work, plan: dict, ledger: dict, units: list, run_pi, ask, *, figures: bool, review: bool,
                   progress, workers: int = 3, look=None, verify_links=None) -> list:
    """`look(prompt, files) -> reply`: a call that sees images, for the frame ledger (多配图 ①)."""
    work = Path(work)
    points = {point["id"]: point for point in ledger["points"]}
    owned = planning.assign(plan, ledger)
    attached = _attachments(plan.get("profile"), figures)

    def one(number: int) -> dict:
        chapter = plan["chapters"][number - 1]
        return _write_one(work, plan, number, owned.get(chapter["id"], []), points, units, run_pi, ask,
                          attached=attached, figures=figures, review=review, progress=progress, look=look,
                          verify_links=verify_links)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, range(1, len(plan["chapters"]) + 1)))


# ---------- steps 7–8: assembly and coverage ----------

def _marked(html: str) -> set:
    return {token for node in parse_html(html).walk() for token in (node.attrs.get("data-points") or "").split()}


def _minutes(chapter: dict) -> float:
    return sum(end - start for start, end in planning.chapter_ranges(chapter) or []) / 60


def _sources(coverage: dict, chapters: int) -> str:
    reasons = Counter(skip["reason"] for skip in coverage["skipped"])
    listed = "、".join(f"{reason} {count} 条" for reason, count in reasons.items())
    return (
        f"本报告按「完整精读」流程生成：先从转写中逐段提取要点 {coverage['points_total']} 条，"
        f"再按规划分 {chapters} 章分别写作，每章经程序检查和「讲清楚」审校后拼装。"
        f"写到 {coverage['written']} 条；跳过 {len(coverage['skipped'])} 条"
        + (f"（{listed}）" if listed else "")
        + f"；未写到 {len(coverage['uncovered'])} 条。"
        "「补充说明（非视频内容）」框里是报告作者用通用知识补充的背景，不是视频里的说法。"
    )


def finish(work, plan: dict, plan_problems: list, ledger: dict, chapters: list, input_json: dict) -> dict:
    """report.html (the template filled with the chapters) and coverage.json, checked on the page."""
    work = Path(work)
    template = (SKILL_DIR / "assets" / "report-template.html").read_text(encoding="utf-8")
    fragments = [chapter["fragment"] for chapter in chapters]
    by_id = {point["id"]: point for point in ledger["points"]}
    legal = planning.valid_skips(plan, set(by_id))
    marked = _marked(assembling.assemble(template, plan, fragments, input_json, sources=""))

    def timed(point: dict) -> dict:
        return {"text": point["text"], "start_ms": point["start_ms"], "end_ms": point["end_ms"]}

    skipped = []
    for point in ledger["points"]:
        if point["id"] in legal:
            skip = legal[point["id"]]
            entry = {"id": point["id"], "reason": skip["reason"], **timed(point)}
            if skip.get("duplicate_of"):
                entry["duplicate_of"] = skip["duplicate_of"]
            skipped.append(entry)
    coverage = {
        "points_total": len(by_id),
        "written": len(marked & set(by_id)),
        "skipped": skipped,
        "uncovered": [{"id": point["id"], **timed(point)} for point in ledger["points"]
                      if point["id"] not in marked and point["id"] not in legal],
        "skipped_spans": [{"reason": skip["reason"], "start_ms": skip["start_ms"], "end_ms": skip["end_ms"]}
                          for skip in ledger["skips"]],
        "chapters": [],
        "problems": {"ledger": ledger["problems"], "unassigned_spans": ledger["uncovered"], "plan": plan_problems},
        "viewpoints": {name: sum((chapter.get("links") or {}).get(name, 0) for chapter in chapters)
                       for name in viewpoints.STATS},
    }
    for chapter, result in zip(plan["chapters"], chapters):
        minutes = _minutes(chapter)
        check = result["check"]
        coverage["chapters"].append({
            "number": result["number"], "title": chapter["title"], "points": len(result["points"]),
            "chars": check["chars"], "minutes": round(minutes, 2),
            "chars_per_minute": round(check["chars"] / minutes, 1) if minutes else 0.0,
            "copy_ratio": round(check["copy_ratio"], 3), "rounds": result["rounds"],
            "missing": check["missing"], "weak": check["weak"], "review": result["review"],
        })
    html = assembling.assemble(template, plan, fragments, input_json, sources=_sources(coverage, len(chapters)))
    (work / "report.html").write_bytes(html.encode("utf-8"))
    _write_json(work / "coverage.json", coverage)
    return coverage
