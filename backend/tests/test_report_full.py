"""The 完整精读 pipeline end to end with a fake model and a fake Pi (PLAN 15.4.11 steps 2–8):
key points, the plan (redone once with its problems), one run per chapter with at most two
revisions, the 讲清楚 review, assembly into the template and coverage.json."""

import json
import re

import pytest
from prometheus.report import chapter_checks, full, review
from prometheus.report.pi_run import PiRunError

INPUT = {"attribution": "Bilibili；示例UP主；《手冲咖啡》；https://www.bilibili.com/video/BV1xJYT6EEYc/"}


def make_units(count=24, seconds_each=30):
    return [{"unit_id": f"unit-{i:06d}", "start_ms": i * seconds_each * 1000, "end_ms": (i + 1) * seconds_each * 1000,
             "canonical_text": f"第{i}句原话讲咖啡豆的烘焙和萃取{i}。"} for i in range(count)]


def keypoint_reply(prompt: str) -> str:
    ids = re.findall(r"^\[(unit-\d{6}) ", prompt, flags=re.MULTILINE)
    points = [{"type": "论断", "text": f"咖啡豆的烘焙和萃取之{int(first[-6:])}", "units": [first, first],
               "anchor": f"第{int(first[-6:])}句原话讲咖啡豆的烘焙"} for first in ids]
    return json.dumps({"points": points, "skips": []}, ensure_ascii=False)


class Model:
    """ask(): key points per unit; the reader asks one question; the judge finds it in the source."""

    def __init__(self, *, reader_questions=True):
        self.prompts = []
        self.reader_questions = reader_questions

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "列出这一段里" in prompt:
            return keypoint_reply(prompt)
        if "没看过视频" in prompt:
            quote = re.search(r"咖啡豆的烘焙和萃取之\d+", prompt)
            questions = [{"quote": quote.group(0), "question": "烘焙到什么程度？"}] if self.reader_questions and quote else []
            return json.dumps({"questions": questions}, ensure_ascii=False)
        if "逐条判断" in prompt:
            return json.dumps({"verdicts": {"1": {"kind": "原文有答案", "answer": "中深烘"}}}, ensure_ascii=False)
        raise AssertionError("unexpected prompt")


GOOD_PLAN = {"title": "手冲咖啡", "subtitle": "", "lead": "烘焙与萃取。", "profile": "mechanism",
             "chapters": [{"id": "c1", "title": "烘焙", "ranges": [["00:00", "06:00"]], "target_chars": 100},
                          {"id": "c2", "title": "萃取", "ranges": [["06:00", "12:00"]], "target_chars": 100}],
             "moves": {}, "glossary": [{"term": "萃取", "chapter": "c2"}], "skips": []}


def section(prompt: str, *, leave_out=()) -> str:
    number = int(re.search(r"本章是第 (\d+)/", prompt).group(1))
    owned = re.findall(r"^- (K\d{3})（[^）]*）(\S+)", prompt, flags=re.MULTILINE)
    body = "".join(f'<p data-points="{point_id}">{text}：这一点讲清楚了是什么、为什么、怎么用，并举了例子说明。</p>'
                   for point_id, text in owned if point_id not in leave_out)
    return f'<section><h2><span class="num">{number}</span><span class="section-title">第{number}章</span></h2>{body}</section>'


class Pi:
    """run_pi(workspace, prompt, expect): writes the plan, then chapters; hooks change one run."""

    def __init__(self, plans=(GOOD_PLAN,), chapter=None):
        self.plans = list(plans)
        self.chapter = chapter or (lambda prompt, attempt: section(prompt))
        self.calls = []

    def __call__(self, workspace, prompt, expect):
        assert (workspace / "SKILL.md").is_file()
        self.calls.append((expect, prompt))
        if expect == "plan.json":
            plan = self.plans.pop(0) if len(self.plans) > 1 else self.plans[0]
            text = plan if isinstance(plan, str) else json.dumps(plan, ensure_ascii=False)
            (workspace / expect).write_text(text, encoding="utf-8")
        else:
            attempt = sum(1 for name, _ in self.calls if name == expect)
            first = next(text for name, text in self.calls if name == expect)
            # a targeted run and the viewpoint pass rewrite the draft: the chapter comes from the first prompt
            later = "只补" in prompt or "加编者观点" in prompt
            # every run leaves its mark, as a real one never writes the same bytes twice (R7g: an unchanged
            # file means the run did nothing and gets one more go)
            text = self.chapter(first if later else prompt, attempt) + f"<!-- run {len(self.calls)} -->"
            (workspace / expect).write_text(text, encoding="utf-8")
        return workspace / expect

    def runs(self, expect):
        return [prompt for name, prompt in self.calls if name == expect]

    def writes(self, expect):
        """The writing runs: every run but the closing editor's-viewpoint pass."""
        return [prompt for prompt in self.runs(expect) if "加编者观点" not in prompt]


def pipeline(tmp_path, *, pi=None, model=None, review=True, units=None, progress=None):
    units = units or make_units()
    model, pi = model or Model(), pi or Pi()
    ledger = full.run_keypoints(tmp_path, units, model)
    plan, plan_problems = full.run_plan(tmp_path, ledger, pi, figures=False, input_json=INPUT)
    chapters = full.write_chapters(tmp_path, plan, ledger, units, pi, model, figures=False, review=review,
                                   progress=progress or (lambda *args: None), workers=1)
    coverage = full.finish(tmp_path, plan, plan_problems, ledger, chapters, INPUT)
    return ledger, plan, chapters, coverage, pi, model


def test_the_ledger_is_written_and_reused_when_the_transcript_is_the_same(tmp_path):
    model = Model()
    ledger = full.run_keypoints(tmp_path, make_units(), model)
    assert len(ledger["points"]) == 24 and ledger["points"][0]["id"] == "K001"
    assert (tmp_path / "keypoints.json").is_file() and (tmp_path / "keypoints.md").is_file()
    assert (tmp_path / "transcript" / "part-01.md").is_file()
    asked = len(model.prompts)
    assert full.run_keypoints(tmp_path, make_units(), model) == ledger
    assert len(model.prompts) == asked
    changed = make_units()
    changed[0]["canonical_text"] = "换了一句话讲咖啡豆的烘焙。"
    full.run_keypoints(tmp_path, changed, model)
    assert len(model.prompts) > asked


def test_the_plan_is_redone_once_with_its_problems(tmp_path):
    pi = Pi(plans=({**GOOD_PLAN, "lead": ""}, GOOD_PLAN))
    ledger = full.run_keypoints(tmp_path, make_units(), Model())
    plan, problems = full.run_plan(tmp_path, ledger, pi, figures=False, input_json=INPUT)
    runs = pi.runs("plan.json")
    assert len(runs) == 2 and "导语为空" in runs[1]
    assert plan["lead"] == "烘焙与萃取。" and problems == []
    assert json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))["lead"] == "烘焙与萃取。"


def test_a_plan_still_wrong_after_the_redo_is_kept_with_its_problems(tmp_path):
    lazy = {**GOOD_PLAN, "chapters": GOOD_PLAN["chapters"][:1]}  # 06:00–12:00 has no chapter
    pi = Pi(plans=(lazy, lazy))
    ledger = full.run_keypoints(tmp_path, make_units(), Model())
    _plan, problems = full.run_plan(tmp_path, ledger, pi, figures=False, input_json=INPUT)
    assert len(pi.runs("plan.json")) == 2 and any("没有归属章节" in problem for problem in problems)


class RefusedPlan(Pi):
    """The first planning run ends without writing plan.json (runanytime refused it, R7g)."""

    def __call__(self, workspace, prompt, expect):
        if expect == "plan.json" and not any(name == expect for name, _ in self.calls):
            self.calls.append((expect, prompt))
            raise PiRunError("Pi 结束了，但没有写出 plan.json")
        return super().__call__(workspace, prompt, expect)


def test_a_planning_run_that_left_nothing_is_run_once_more(tmp_path):
    """R7g (PLAN 15.4.14 G ②): one refusal at the first planning turn failed the whole report."""
    ledger = full.run_keypoints(tmp_path, make_units(), Model())
    pi = RefusedPlan()
    plan, problems = full.run_plan(tmp_path, ledger, pi, figures=False, input_json=INPUT)
    assert len(pi.runs("plan.json")) == 2 and plan["title"] == "手冲咖啡" and problems == []


def test_an_unreadable_plan_fails_the_report(tmp_path):
    pi = Pi(plans=("这不是 JSON", "还不是"))
    ledger = full.run_keypoints(tmp_path, make_units(), Model())
    with pytest.raises(PiRunError, match="规划"):
        full.run_plan(tmp_path, ledger, pi, figures=False, input_json=INPUT)


def test_every_chapter_is_its_own_run_and_the_report_is_assembled(tmp_path):
    _ledger, _plan, _chapters, coverage, pi, _model = pipeline(tmp_path)
    assert len(pi.runs("ch-01.html")) >= 1 and len(pi.runs("ch-02.html")) >= 1
    assert "K001" in pi.runs("ch-01.html")[0] and "K013" not in pi.runs("ch-01.html")[0]
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert html.index('<section id="s1">') < html.index('<section id="s2">')
    assert '<a href="#s2">萃取</a>' in html and html.count("{{VIDEO_DESCRIPTION}}") == 1
    assert coverage["points_total"] == 24 and coverage["written"] == 24 and coverage["uncovered"] == []
    saved = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    assert saved["written"] == 24 and len(saved["chapters"]) == 2
    assert saved["chapters"][0]["chars_per_minute"] > 0 and "copy_ratio" in saved["chapters"][0]


def test_a_chapter_that_misses_a_point_is_revised_at_most_twice_and_the_miss_is_recorded(tmp_path):
    pi = Pi(chapter=lambda prompt, attempt: section(prompt, leave_out=("K003",)))
    _ledger, _plan, chapters, coverage, pi, _model = pipeline(tmp_path, pi=pi, review=False)
    revisions = pi.writes("ch-01.html")[1:3]
    assert len(revisions) == 2 and all("K003" in prompt and "上一稿" in prompt for prompt in revisions)
    # still missing after two rounds: one targeted run with only the rules, the draft and K003's source
    [targeted] = pi.writes("ch-01.html")[3:]
    assert "只补" in targeted and "第2句原话" in targeted and "=== 附件：SKILL.md" not in targeted
    assert [point["id"] for point in coverage["uncovered"]] == ["K003"]
    assert coverage["uncovered"][0]["start_ms"] == 60_000 and coverage["uncovered"][0]["text"]
    assert chapters[0]["rounds"] == 2 and chapters[0]["targeted"] is True


def test_a_targeted_run_that_fixes_the_point_is_kept(tmp_path):
    pi = Pi(chapter=lambda prompt, attempt: section(prompt, leave_out=("K003",) if attempt < 4 else ()))
    _ledger, _plan, chapters, coverage, pi, _model = pipeline(tmp_path, pi=pi, review=False)
    assert len(pi.writes("ch-01.html")) == 4 and coverage["uncovered"] == [] and chapters[0]["targeted"] is True


def test_a_fixed_chapter_is_not_revised(tmp_path):
    pi = Pi(chapter=lambda prompt, attempt: section(prompt, leave_out=("K003",) if attempt == 1 else ()))
    _ledger, _plan, _chapters, coverage, pi, _model = pipeline(tmp_path, pi=pi, review=False)
    assert len(pi.writes("ch-01.html")) == 2 and coverage["uncovered"] == []


def test_the_review_sends_answers_found_in_the_source_back_once(tmp_path):
    _ledger, _plan, chapters, _coverage, pi, model = pipeline(tmp_path)
    runs = pi.writes("ch-01.html")
    assert len(runs) == 2 and "烘焙到什么程度" in runs[1] and "中深烘" in runs[1]
    # one question on a short chapter is below the bar: a second reader looked and found nothing new (R7g)
    assert chapters[0]["review"] == {"questions": 1, "answered": 1, "background": 0, "revised": True,
                                     "reverted": False, "second_reader": True, "unfinished": False}
    reader = next(prompt for prompt in model.prompts if "没看过视频" in prompt)
    assert "第0句原话" not in reader  # the reader never sees the transcript


def test_a_review_revision_that_loses_points_is_undone(tmp_path):
    pi = Pi(chapter=lambda prompt, attempt: section(prompt, leave_out=("K002",) if attempt == 2 else ()))
    _ledger, _plan, chapters, coverage, _pi, _model = pipeline(tmp_path, pi=pi)
    assert chapters[0]["review"]["reverted"] is True
    assert coverage["uncovered"] == []


def test_no_review_when_it_is_off_or_the_reader_has_no_questions(tmp_path):
    _ledger, _plan, _chapters, _coverage, pi, model = pipeline(tmp_path, review=False)
    assert not any("没看过视频" in prompt for prompt in model.prompts)
    assert len(pi.writes("ch-01.html")) == 1
    _l, _p, chapters, _c, pi, _m = pipeline(tmp_path / "again", model=Model(reader_questions=False))
    assert len(pi.writes("ch-01.html")) == 1 and chapters[0]["review"]["questions"] == 0


def test_progress_names_the_step_and_the_chapter(tmp_path):
    seen = []
    pipeline(tmp_path, progress=lambda step, number, total: seen.append((step, number, total)))
    assert ("写作", 1, 2) in seen and ("写作", 2, 2) in seen and ("审校", 2, 2) in seen


def test_finished_chapters_are_reused_when_the_run_is_retried(tmp_path):
    pipeline(tmp_path)
    again = Pi()
    ledger = full.run_keypoints(tmp_path, make_units(), Model())
    plan, _problems = full.run_plan(tmp_path, ledger, again, figures=False, input_json=INPUT)
    chapters = full.write_chapters(tmp_path, plan, ledger, make_units(), again, Model(), figures=False,
                                   review=True, progress=lambda *args: None, workers=1)
    assert again.calls == [] and len(chapters) == 2


def test_skipped_points_are_listed_with_their_reason_and_not_counted_as_missing(tmp_path):
    plan = {**GOOD_PLAN, "skips": [{"point": "K024", "reason": "寒暄与课堂管理"}]}
    _ledger, _plan, _chapters, coverage, _pi, _model = pipeline(tmp_path, pi=Pi(plans=(plan,)))
    assert coverage["skipped"] == [{"id": "K024", "reason": "寒暄与课堂管理", "text": "咖啡豆的烘焙和萃取之23",
                                    "start_ms": 690_000, "end_ms": 720_000}]
    assert coverage["written"] == 23 and coverage["uncovered"] == []


def test_with_figures_a_chapter_gets_only_the_frames_in_its_time(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    listed = [{"file": "f_000030.jpg", "t": 30.0, "label": "00:30"}, {"file": "f_000400.jpg", "t": 400.0, "label": "06:40"}]
    (frames / "frames.json").write_text(json.dumps(listed), encoding="utf-8")
    for frame in listed:
        (frames / frame["file"]).write_bytes(b"jpg")
    units, pi = make_units(), Pi()
    ledger = full.run_keypoints(tmp_path, units, Model())
    plan, _problems = full.run_plan(tmp_path, ledger, pi, figures=True, input_json=INPUT)
    full.write_chapters(tmp_path, plan, ledger, units, pi, Model(), figures=True, review=False,
                        progress=lambda *args: None, workers=1)
    first = tmp_path / "chapters" / "ch-01" / "frames"
    assert sorted(path.name for path in first.iterdir()) == ["f_000030.jpg", "frames.json"]
    assert [frame["file"] for frame in json.loads((first / "frames.json").read_text(encoding="utf-8"))] == ["f_000030.jpg"]
    assert "figures.md" in pi.runs("ch-01.html")[0] and "配图规则" in pi.runs("ch-01.html")[0]


class Look:
    """look(prompt, files): the frame ledger's one look per chapter; every frame is a slide."""

    def __init__(self):
        self.calls = []

    def __call__(self, prompt, files):
        self.calls.append([path.name for path in files])
        return json.dumps({"frames": {path.name: {"kind": "幻灯片", "what": f"讲义第{path.name[2:8]}秒那页"}
                                      for path in files}}, ensure_ascii=False)


def test_the_frame_ledger_is_offered_to_the_writer_and_an_unused_slide_is_sent_back_once_looked_at(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    listed = [{"file": "f_000030.jpg", "t": 30.0, "label": "00:30"}, {"file": "f_000400.jpg", "t": 400.0, "label": "06:40"}]
    (frames / "frames.json").write_text(json.dumps(listed), encoding="utf-8")
    for frame in listed:
        (frames / frame["file"]).write_bytes(b"jpg")
    units, pi, look = make_units(), Pi(), Look()
    ledger = full.run_keypoints(tmp_path, units, Model())
    plan, _problems = full.run_plan(tmp_path, ledger, pi, figures=True, input_json=INPUT)
    chapters = full.write_chapters(tmp_path, plan, ledger, units, pi, Model(), figures=True, review=False,
                                   progress=lambda *args: None, workers=1, look=look)
    assert look.calls == [["f_000030.jpg"], ["f_000400.jpg"]]
    first = pi.writes("ch-01.html")
    assert "f_000030.jpg" in first[0] and "讲义第000030秒那页" in first[0]
    assert len(first) == 3 and "f_000030.jpg" in first[1]  # never used, never declined: two revisions
    assert chapters[0]["check"]["unused_frames"] == ["f_000030.jpg"]
    again = Look()
    full.write_chapters(tmp_path, plan, ledger, units, Pi(), Model(), figures=True, review=False,
                        progress=lambda *args: None, workers=1, look=again)
    assert again.calls == []  # the ledger and the chapters are kept


def test_a_chapter_without_frames_is_not_told_about_frames(tmp_path):
    """One wasted turn per run otherwise: the writer went looking in an empty frames folder."""
    frames = tmp_path / "frames"
    frames.mkdir()
    listed = [{"file": "f_000030.jpg", "t": 30.0, "label": "00:30"}]
    (frames / "frames.json").write_text(json.dumps(listed), encoding="utf-8")
    (frames / "f_000030.jpg").write_bytes(b"jpg")
    units, pi = make_units(), Pi()
    ledger = full.run_keypoints(tmp_path, units, Model())
    plan, _problems = full.run_plan(tmp_path, ledger, pi, figures=True, input_json=INPUT)
    full.write_chapters(tmp_path, plan, ledger, units, pi, Model(), figures=True, review=False,
                        progress=lambda *args: None, workers=1, look=Look())
    assert "frames/ 里是本章" in pi.runs("ch-01.html")[0]
    assert "frames/ 里是本章" not in pi.runs("ch-02.html")[0]


def test_the_assembled_report_goes_through_finalize_with_its_frames_inlined(tmp_path):
    """E14 ①「拼装……通过 finalize 的检查」: placeholders filled, frames inlined, nothing external."""
    from prometheus.report.finalize import finalize_report

    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "f_000030.jpg").write_bytes(b"\xff\xd8jpg")
    (tmp_path / "source.info.json").write_text(json.dumps({"description": "视频简介原文"}, ensure_ascii=False),
                                               encoding="utf-8")
    figure = '<figure class="report-figure" data-frame-t="30"><img src="frames/f_000030.jpg" alt="颜色"><figcaption>颜色</figcaption></figure>'
    pi = Pi(chapter=lambda prompt, attempt: section(prompt).replace("</section>", figure + "</section>"))
    pipeline(tmp_path, pi=pi, review=False)
    final = tmp_path / "out" / "精读.html"
    title = finalize_report(tmp_path / "report.html", final, tmp_path)
    html = final.read_text(encoding="utf-8")
    assert title == "手冲咖啡"
    assert "{{" not in html and "视频简介原文" in html
    assert 'src="frames/' not in html and "data:image/jpeg;base64," in html


def test_the_review_keeps_what_was_asked_and_how_it_was_judged(tmp_path):
    """Without this nobody can tell why a chapter's ten questions led to nothing (English run, 2026-09-28)."""
    _ledger, _plan, chapters, _coverage, _pi, _model = pipeline(tmp_path)
    details = chapters[0]["review_details"]
    assert details["questions"] == [{"quote": "咖啡豆的烘焙和萃取之0", "question": "烘焙到什么程度？",
                                     "verdict": {"kind": "原文有答案", "answer": "中深烘"}}]
    assert details["pictures"] == [] and "judge_reply" in details


def test_the_editors_links_are_verified_and_counted_in_the_coverage(tmp_path):
    """PLAN 15.4.11a-4: a dead link in the editor's view is dropped before assembly."""
    box = ('<aside class="viewpoint"><p class="viewpoint-label">编者观点（非视频内容）</p><ul>'
           '<li>编者的判断。<span class="confidence">置信度：中</span>依据：'
           '<a href="https://en.wikipedia.org/wiki/Coffee_roasting">Coffee roasting (Wikipedia)</a>、'
           '<a href="https://example.org/gone">Gone</a></li></ul></aside>')
    pi = Pi(chapter=lambda prompt, attempt: section(prompt).replace("</section>", box + "</section>"))
    units, model = make_units(), Model()
    ledger = full.run_keypoints(tmp_path, units, model)
    plan, problems = full.run_plan(tmp_path, ledger, pi, figures=False, input_json=INPUT)

    def open_page(url):
        if "gone" in url:
            raise OSError("404")
        return "Coffee roasting - Wikipedia"

    chapters = full.write_chapters(tmp_path, plan, ledger, units, pi, model, figures=False, review=False,
                                   progress=lambda *args: None, workers=1, verify_links=open_page)
    coverage = full.finish(tmp_path, plan, problems, ledger, chapters, INPUT)
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "example.org/gone" not in html and "Coffee_roasting" in html
    assert coverage["viewpoints"] == {"points": 2, "links": 4, "kept": 2, "dropped": 2, "unsourced": 0,
                                      "unreachable": 2, "unrelated": 0}


def test_every_chapter_ends_with_an_editors_viewpoint_pass(tmp_path):
    """One-go runs wrote 0–5 viewpoint boxes where a pass of their own wrote 12–34 (R7e patch,
    R7f Russell): every chapter now gets that pass, after the review (user 2026-09-30)."""
    _ledger, plan, _chapters, _coverage, pi, _model = pipeline(tmp_path)
    for number in range(1, len(plan["chapters"]) + 1):
        runs = pi.runs(f"ch-{number:02d}.html")
        assert "加编者观点" in runs[-1] and not any("加编者观点" in prompt for prompt in runs[:-1])


class Readers(Model):
    """The first reader asks `first` questions; a second reader, when there is one, one new question."""

    def __init__(self, first=1):
        super().__init__()
        self.first = first

    def __call__(self, prompt: str) -> str:
        if "没看过视频" not in prompt:
            return super().__call__(prompt)
        self.prompts.append(prompt)
        quote = re.search(r"咖啡豆的烘焙和萃取之\d+", prompt).group(0)
        if "已经问过" in prompt:
            return json.dumps({"questions": [{"quote": quote, "question": "萃取是什么意思？"}]}, ensure_ascii=False)
        return json.dumps({"questions": [{"quote": quote, "question": f"烘焙到什么程度{i}？"} for i in range(self.first)]},
                          ensure_ascii=False)


def test_a_second_reader_looks_for_what_the_first_missed(tmp_path):
    """R7g (PLAN 15.4.14 A): a second reader looks for what the first one missed, and the two lists are
    judged together."""
    _l, _p, chapters, _c, _pi, model = pipeline(tmp_path, model=Readers(first=1))
    second = [prompt for prompt in model.prompts if "已经问过" in prompt]
    assert len(second) == 2 and "烘焙到什么程度0？" in second[0]
    judge = next(prompt for prompt in model.prompts if "逐条判断" in prompt)
    assert "烘焙到什么程度0？" in judge and "萃取是什么意思？" in judge
    assert chapters[0]["review"]["second_reader"] is True and chapters[0]["review"]["questions"] == 2


def test_every_chapter_gets_a_second_reader_however_many_the_first_asked(tmp_path):
    """The sonnet baseline: short chapters kept a per-thousand-characters bar from ever calling one
    (user 2026-09-30: every chapter)."""
    _l, _p, chapters, _c, _pi, model = pipeline(tmp_path, model=Readers(first=30))
    assert len([prompt for prompt in model.prompts if "已经问过" in prompt]) == 2
    assert all(chapter["review"]["second_reader"] is True for chapter in chapters)


class Background(Model):
    """The judge calls the reader's question background: the revision should add a supplement."""

    def __call__(self, prompt: str) -> str:
        if "逐条判断" in prompt:
            self.prompts.append(prompt)
            return json.dumps({"verdicts": {"1": {"kind": "术语或背景"}}}, ensure_ascii=False)
        return super().__call__(prompt)


def test_a_background_question_left_without_a_supplement_goes_back_once(tmp_path):
    """R7g (15.4.14 F): the revision was asked for a supplement and wrote none."""
    _l, _p, chapters, _c, pi, _m = pipeline(tmp_path, model=Background())
    runs = pi.runs("ch-01.html")
    assert "还没有补充说明" in runs[-1] and sum("还没有补充说明" in prompt for prompt in runs) == 1
    assert any("还没有补充说明" in problem for problem in chapters[0]["closing"])


class LeakyPi(Pi):
    """The viewpoint pass writes the writing materials in; `stubborn`: the closing fix does too."""

    def __init__(self, *, stubborn=False):
        super().__init__()
        self.stubborn = stubborn

    def __call__(self, workspace, prompt, expect):
        path = super().__call__(workspace, prompt, expect)
        if "加编者观点" in prompt or (self.stubborn and "处理过程" in prompt):
            leaked = path.read_text(encoding="utf-8").replace("</section>", "<p>候选帧已逐张查看，没有选用。</p></section>")
            path.write_text(leaked, encoding="utf-8")
        return path


def test_what_the_closing_check_finds_goes_back_once(tmp_path):
    """R7g (15.4.14 B–E): the review's revision and the viewpoint pass come after the chapter checks, so a
    last look catches the writing materials, thin supplements, pictures not drawn and crowded limits."""
    _l, _p, chapters, _c, pi, _m = pipeline(tmp_path, pi=LeakyPi(), review=False)
    runs = pi.runs("ch-01.html")
    assert "加编者观点" in runs[-2] and "处理过程" in runs[-1]
    assert sum("处理过程" in prompt for prompt in runs) == 1
    assert "候选帧" not in chapters[0]["fragment"] and chapters[0]["closing"]


def test_the_closing_check_goes_back_only_once_even_if_the_fix_misses(tmp_path):
    _l, _p, _chapters, _c, pi, _m = pipeline(tmp_path, pi=LeakyPi(stubborn=True), review=False)
    assert sum("处理过程" in prompt for prompt in pi.runs("ch-01.html")) == 1


def test_the_closing_problems_name_what_to_fix_and_never_a_threshold():
    supplement = ('<aside class="supplement"><p class="supplement-label">补充说明（非视频内容）</p>'
                  "<p>萃取率是溶出的比例。</p></aside>")
    fragment = (f"<section><h2>一</h2><p>浅烘豆要用高一点的水温。</p>{supplement}"
                "<p>" + "这件事不能据此断定。" * 5 + "</p><p>候选帧已逐张查看。</p></section>")
    problems = full.closing_problems(fragment, [{"quote": "浅烘豆要用高一点的水温", "want": "温度对照图"}],
                                     [{"quote": "这件事不能据此断定", "question": "为什么不能断定？"}])
    joined = "".join(problems)
    assert len(problems) == 5 and "温度对照图" in joined and "溶出的比例" in joined and "候选帧" in joined
    assert "不能据此断定" in joined and "为什么要紧" in joined and "为什么不能断定？" in joined
    for threshold in (review.SUPPLEMENT_MIN, chapter_checks.HEDGE_MAX):
        assert str(threshold) not in joined


REFUSAL = "Sorry, I wasn't able to respond to that. Is there something else I can help with?"


class Refusing(Model):
    """Readers and the judge refuse the first `times` times (a relay's content filter, R7g)."""

    def __init__(self, times=1):
        super().__init__()
        self.left = {"reader": times, "judge": times}

    def __call__(self, prompt: str) -> str:
        kind = "reader" if "没看过视频" in prompt else "judge" if "逐条判断" in prompt else None
        if kind and self.left[kind] > 0:
            self.left[kind] -= 1
            self.prompts.append(prompt)
            return REFUSAL
        return super().__call__(prompt)


def test_a_refused_reader_or_judge_is_asked_again(tmp_path):
    """R7g (PLAN 15.4.14 G ①): a refusal was read as 「no questions」 and two chapters got no supplements."""
    _l, _p, chapters, _c, _pi, model = pipeline(tmp_path, model=Refusing(times=1))
    first_readers = [p for p in model.prompts if "没看过视频" in p and "已经问过" not in p]
    assert len(first_readers) == 3  # chapter 1 asked twice, chapter 2 once
    assert chapters[0]["review"]["questions"] == 1 and chapters[0]["review"]["answered"] == 1
    assert chapters[0]["review"]["unfinished"] is False


def test_a_review_that_stays_refused_is_marked_unfinished(tmp_path):
    _l, _p, chapters, coverage, _pi, _m = pipeline(tmp_path, model=Refusing(times=99))
    assert chapters[0]["review"]["unfinished"] is True and chapters[0]["review"]["questions"] == 0
    assert coverage["chapters"][0]["review"]["unfinished"] is True


class Silent(Pi):
    """Chapter 1's first write, then its viewpoint pass, end without touching the file (a refusal)."""

    def __init__(self, *, stubborn=False):
        super().__init__()
        self.stubborn, self.skipped = stubborn, []

    def __call__(self, workspace, prompt, expect):
        target = workspace / expect
        first_write = expect == "ch-01.html" and not any(name == expect for name, _ in self.calls)
        viewpoint = expect == "ch-01.html" and "加编者观点" in prompt
        seen = sum(1 for kind in self.skipped if kind == ("write" if first_write else "viewpoint"))
        if (first_write and not self.skipped) or (viewpoint and (self.stubborn or not seen)):
            self.calls.append((expect, prompt))
            self.skipped.append("write" if first_write else "viewpoint")
            if not target.is_file():
                raise PiRunError(f"Pi 结束了，但没有写出 {expect}")
            return target
        return super().__call__(workspace, prompt, expect)


def test_a_writing_run_that_left_nothing_is_run_once_more(tmp_path):
    """R7g (15.4.14 G ②): chapter 1's first write was refused and the whole report failed."""
    _l, _p, _chapters, coverage, pi, _m = pipeline(tmp_path, pi=Silent(), review=False)
    runs = pi.runs("ch-01.html")
    assert sum("加编者观点" in prompt for prompt in runs) == 2 and coverage["uncovered"] == []
    assert pi.skipped == ["write", "viewpoint"]


def test_a_run_that_changes_nothing_twice_is_left_as_it_is(tmp_path):
    _l, _p, _chapters, _c, pi, _m = pipeline(tmp_path, pi=Silent(stubborn=True), review=False)
    assert sum("加编者观点" in prompt for prompt in pi.runs("ch-01.html")) == 2


def test_a_viewpoint_pass_that_loses_a_point_is_undone(tmp_path):
    pi = Pi(chapter=lambda prompt, attempt: section(prompt, leave_out=("K001",) if "加编者观点" in prompt else ()))
    _ledger, _plan, _chapters, coverage, pi, _model = pipeline(tmp_path, pi=pi, review=False)
    assert any("加编者观点" in prompt for prompt in pi.runs("ch-01.html")) and coverage["uncovered"] == []
