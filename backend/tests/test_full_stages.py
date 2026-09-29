"""完整精读 in the queue (PLAN 15.4.11): the 提取要点 and 规划 stages, the chapter report, the
console's 「写作（第 3/10 章）」, and the model settings reaching every call."""

import json
import time

import pytest
from conftest import DUMMY_RUNTIME
from prometheus import paths
from prometheus.library import db
from prometheus.library import items as items_store
from prometheus.report import workspace as workspace_mod
from prometheus.report.pi_run import PiRunError
from prometheus.settings import store
from prometheus.tasks import runner
from prometheus.tasks import stages as stages_mod
from prometheus.tasks.runner import StageContext

UNITS = [{"unit_id": f"unit-{i:06d}", "start_ms": i * 1000, "end_ms": (i + 1) * 1000, "canonical_text": f"第{i}句"}
         for i in range(3)]
EMPTY_LEDGER = {"points": [], "skips": [], "problems": [], "uncovered": []}


@pytest.fixture
def data_dir(tmp_path):
    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    return data_dir


def _ctx(data_dir, *, figures=0):
    item_id = items_store.create_item(
        data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
        source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/", figures=figures,
    )
    work = paths.work_dir(data_dir, item_id)
    work.mkdir(parents=True, exist_ok=True)
    (work / "canonical-transcript.jsonl").write_text(
        "\n".join(json.dumps(unit, ensure_ascii=False) for unit in UNITS), encoding="utf-8")
    return StageContext(data_dir, item_id)


def _depth(data_dir, depth, *, review=True):
    settings = store.load(data_dir)
    settings["report"] = {"depth": depth, "review": review}
    store.save(data_dir, settings)


def test_key_points_and_the_plan_come_right_before_the_report():
    at = runner.STAGES.index("report")
    assert runner.STAGES[at - 2:at] == ["keypoints", "plan"]


def test_standard_depth_skips_the_key_points_and_the_plan(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    _depth(data_dir, "standard")
    called = []
    monkeypatch.setattr(stages_mod.workspace_mod, "run_keypoints_stage", lambda *a, **k: called.append("keypoints"))
    monkeypatch.setattr(stages_mod.workspace_mod, "run_plan_stage", lambda *a, **k: called.append("plan"))
    impls = stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)
    impls["keypoints"](ctx)
    impls["plan"](ctx)
    assert called == []


def test_full_depth_runs_key_points_the_plan_and_the_chapters_and_the_console_shows_the_chapter(data_dir, monkeypatch):
    ctx = _ctx(data_dir)  # 「完整」 is the default
    seen = {}

    def fake_full(data_dir_arg, item_id, row, settings, **kwargs):
        kwargs["progress"]("写作", 3, 10)
        seen["detail"] = items_store.get_item(data_dir_arg, item_id)["stage_detail"]

    monkeypatch.setattr(stages_mod.workspace_mod, "run_keypoints_stage",
                        lambda data_dir_arg, item_id, settings, **kwargs: seen.setdefault("keypoints", item_id))
    monkeypatch.setattr(stages_mod.workspace_mod, "run_plan_stage",
                        lambda data_dir_arg, item_id, row, settings, **kwargs: seen.setdefault("plan", kwargs["figures"]))
    monkeypatch.setattr(stages_mod.workspace_mod, "run_full_report_stage", fake_full)
    monkeypatch.setattr(stages_mod.workspace_mod, "run_report_stage", lambda *a, **k: seen.setdefault("vra", True))
    impls = stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)
    for stage in ("keypoints", "plan", "report"):
        impls[stage](ctx)
    assert seen == {"keypoints": ctx.item_id, "plan": False, "detail": "写作（第 3/10 章）"}


def test_the_chapter_shown_goes_when_the_next_stage_starts(data_dir):
    ctx = _ctx(data_dir)
    seen = []
    impls = {"report": lambda c: items_store.update_item(data_dir, c.item_id, stage_detail="写作（第 1/2 章）"),
             "finalize": lambda c: seen.append(items_store.get_item(data_dir, c.item_id)["stage_detail"])}
    runner.run_item(ctx, impls, stages=["report", "finalize"])
    assert seen == [None]


def test_the_coverage_survives_the_cleanup():
    from prometheus.tasks.cleanup import KEEP

    assert "coverage.json" in KEEP
    assert "keypoints.json" in KEEP  # E14's time coverage is measured against the ledger afterwards


def test_the_key_point_stage_reads_the_units_and_asks_the_configured_model(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    seen = {}

    def fake_keypoints(work, units, ask):
        seen.update(work=work, units=units, reply=ask("问题"))

    def fake_one_shot(work_dir, **kwargs):
        seen["call"] = kwargs
        return "回答"

    monkeypatch.setattr(workspace_mod.full, "run_keypoints", fake_keypoints)
    monkeypatch.setattr(workspace_mod.one_shot, "run_one_shot", fake_one_shot)
    settings = store.load(data_dir)
    workspace_mod.run_keypoints_stage(data_dir, ctx.item_id, settings, node_exe="node.exe", pi_cli="cli.js")
    assert seen["work"] == paths.work_dir(data_dir, ctx.item_id) and seen["units"] == UNITS
    assert seen["reply"] == "回答"
    assert seen["call"]["model"] == settings["llm"]["model"] and seen["call"]["provider"] == settings["llm"]["provider"]
    assert seen["call"]["thinking"] == (settings["llm"].get("thinking") or "medium")
    assert (seen["call"]["node_exe"], seen["call"]["pi_cli"]) == ("node.exe", "cli.js")
    assert seen["call"]["agent_dir"] == paths.pi_config_dir(data_dir)


def test_the_plan_stage_hands_the_item_and_one_stage_of_time_to_the_planner(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    seen = {}
    monkeypatch.setattr(workspace_mod.full, "run_keypoints", lambda work, units, ask: EMPTY_LEDGER)
    monkeypatch.setattr(workspace_mod, "pi_runner",
                        lambda *args, deadline: seen.setdefault("left", deadline - time.monotonic()) and "runner")

    def fake_plan(work, ledger, run_pi, **kwargs):
        seen.update(kwargs, run_pi=run_pi)
        return {"chapters": []}, []

    monkeypatch.setattr(workspace_mod.full, "run_plan", fake_plan)
    row = items_store.get_item(data_dir, ctx.item_id)
    workspace_mod.run_plan_stage(data_dir, ctx.item_id, row, store.load(data_dir),
                                 node_exe="node.exe", pi_cli="cli.js", figures=False)
    assert seen["figures"] is False and seen["input_json"]["platform"] == "Bilibili" and seen["run_pi"] == "runner"
    assert 1790 < seen["left"] <= 1800  # pi_timeout_seconds for an unknown duration


def test_the_chapter_report_gets_the_review_setting_figures_progress_and_three_times_the_time(data_dir, monkeypatch):
    ctx = _ctx(data_dir, figures=1)
    _depth(data_dir, "full", review=False)
    seen = {}
    monkeypatch.setattr(workspace_mod.full, "run_keypoints", lambda work, units, ask: EMPTY_LEDGER)
    monkeypatch.setattr(workspace_mod.full, "run_plan", lambda work, ledger, run_pi, **kwargs: ({"chapters": []}, []))
    monkeypatch.setattr(workspace_mod, "pi_runner",
                        lambda *args, deadline: seen.setdefault("left", deadline - time.monotonic()) and "runner")

    def fake_write(work, plan, ledger, units, run_pi, ask, **kwargs):
        seen.update(kwargs, units=units)
        return []

    def fake_finish(work, plan, problems, ledger, chapters, input_json):
        seen["input_json"] = input_json
        (work / "report.html").write_text("<html></html>", encoding="utf-8")
        return {}

    monkeypatch.setattr(workspace_mod.full, "write_chapters", fake_write)
    monkeypatch.setattr(workspace_mod.full, "finish", fake_finish)

    def progress(step, number, total):
        return None

    row = items_store.get_item(data_dir, ctx.item_id)
    report = workspace_mod.run_full_report_stage(data_dir, ctx.item_id, row, store.load(data_dir),
                                                 node_exe="node.exe", pi_cli="cli.js", figures=True, progress=progress)
    assert report == paths.work_dir(data_dir, ctx.item_id) / "report.html"
    assert seen["review"] is False and seen["figures"] is True and seen["progress"] is progress
    assert seen["units"] == UNITS and seen["input_json"]["platform"] == "Bilibili"
    assert 3 * 1800 - 10 < seen["left"] <= 3 * 1800


def test_every_pi_run_gets_what_is_left_of_the_stage_time(data_dir, monkeypatch, tmp_path):
    seen = {}

    def fake_task(workspace, prompt, *, expect, llm, prefix, agent_dir, timeout):
        seen.update(llm=llm, prefix=prefix, agent_dir=agent_dir, timeout=timeout)
        return workspace / expect

    monkeypatch.setattr(workspace_mod.pi_run, "run_task", fake_task)
    settings = store.load(data_dir)
    run = workspace_mod.pi_runner(data_dir, settings, "node.exe", "cli.js", deadline=time.monotonic() + 100)
    assert run(tmp_path, "任务", "plan.json") == tmp_path / "plan.json"
    assert 90 < seen["timeout"] <= 100 and seen["prefix"] == ["node.exe", "cli.js"]
    assert (seen["llm"]["provider"], seen["llm"]["model"]) == (settings["llm"]["provider"], settings["llm"]["model"])
    assert seen["agent_dir"] == paths.pi_config_dir(data_dir)
    seen.clear()
    late = workspace_mod.pi_runner(data_dir, settings, "node.exe", "cli.js", deadline=time.monotonic() - 1)
    with pytest.raises(PiRunError, match="timed out"):
        late(tmp_path, "任务", "plan.json")
    assert seen == {}


def test_the_frame_ledger_looks_through_the_configured_model_with_the_frames_attached(data_dir, monkeypatch, tmp_path):
    ctx = _ctx(data_dir, figures=1)
    seen = {}
    monkeypatch.setattr(workspace_mod.full, "run_keypoints", lambda work, units, ask: EMPTY_LEDGER)
    monkeypatch.setattr(workspace_mod.full, "run_plan", lambda work, ledger, run_pi, **kwargs: ({"chapters": []}, []))
    monkeypatch.setattr(workspace_mod.full, "write_chapters", lambda *args, **kwargs: seen.update(look=kwargs["look"]) or [])
    monkeypatch.setattr(workspace_mod.full, "finish", lambda *args: {})

    def fake_one_shot(work_dir, **kwargs):
        seen["call"] = kwargs
        return "{}"

    monkeypatch.setattr(workspace_mod.one_shot, "run_one_shot", fake_one_shot)
    row = items_store.get_item(data_dir, ctx.item_id)
    workspace_mod.run_full_report_stage(data_dir, ctx.item_id, row, store.load(data_dir), node_exe="node.exe",
                                        pi_cli="cli.js", figures=True, progress=lambda *args: None)
    frame = tmp_path / "f_000030.jpg"
    assert seen["look"]("看图", [frame]) == "{}"
    assert seen["call"]["files"] == [frame] and seen["call"]["prompt"] == "看图"


def _relay(fails: list, *, error):
    """A call that fails with the given errors first, then answers."""
    calls = []

    def call(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) <= len(fails):
            raise error(fails[len(calls) - 1])
        return "ok"

    return call, calls


def test_a_run_the_relay_broke_is_tried_again_after_a_wait(data_dir, monkeypatch, tmp_path):
    """English run 2026-09-28: timeouts, 429 and connection errors for minutes; Pi's own retries
    (2, 4, 8 s) were not enough and a whole chapter failed."""
    waits = []
    monkeypatch.setattr(workspace_mod.time, "sleep", waits.append)
    task, calls = _relay(["Request timed out.", '429 {"error":{"message":"rate limited"}}'], error=PiRunError)
    monkeypatch.setattr(workspace_mod.pi_run, "run_task", lambda workspace, prompt, **kwargs: task(**kwargs))
    run = workspace_mod.pi_runner(data_dir, store.load(data_dir), "n", "c", deadline=time.monotonic() + 3600)
    assert run(tmp_path, "任务", "ch-07.html") == "ok"
    assert len(calls) == 3 and waits == [10, 20]


def test_ten_tries_with_waits_doubling_from_ten_seconds_up_to_two_minutes(data_dir, monkeypatch, tmp_path):
    """User 2026-09-29: ten chances, from 10 s and growing, like the official clients' backoff."""
    waits = []
    monkeypatch.setattr(workspace_mod.time, "sleep", waits.append)
    task, calls = _relay(["unexpected EOF"] * 10, error=PiRunError)
    monkeypatch.setattr(workspace_mod.pi_run, "run_task", lambda workspace, prompt, **kwargs: task(**kwargs))
    run = workspace_mod.pi_runner(data_dir, store.load(data_dir), "n", "c", deadline=time.monotonic() + 36000)
    assert run(tmp_path, "任务", "ch-07.html") == "ok"
    assert len(calls) == 11 and waits == [10, 20, 40, 80, 120, 120, 120, 120, 120, 120]


def test_other_failures_and_an_eleventh_relay_failure_are_not_hidden(data_dir, monkeypatch, tmp_path):
    monkeypatch.setattr(workspace_mod.time, "sleep", lambda seconds: None)
    task, calls = _relay(["Pi 结束了，但没有写出 ch-07.html"], error=PiRunError)
    monkeypatch.setattr(workspace_mod.pi_run, "run_task", lambda workspace, prompt, **kwargs: task(**kwargs))
    run = workspace_mod.pi_runner(data_dir, store.load(data_dir), "n", "c", deadline=time.monotonic() + 3600)
    with pytest.raises(PiRunError, match="没有写出"):
        run(tmp_path, "任务", "ch-07.html")
    assert len(calls) == 1
    task, calls = _relay(["Connection error."] * 11, error=PiRunError)
    monkeypatch.setattr(workspace_mod.pi_run, "run_task", lambda workspace, prompt, **kwargs: task(**kwargs))
    with pytest.raises(PiRunError, match="Connection error"):
        run(tmp_path, "任务", "ch-07.html")
    assert len(calls) == 11


def test_no_wait_past_the_stages_time(data_dir, monkeypatch, tmp_path):
    monkeypatch.setattr(workspace_mod.time, "sleep", lambda seconds: None)
    task, calls = _relay(["Request timed out."], error=PiRunError)
    monkeypatch.setattr(workspace_mod.pi_run, "run_task", lambda workspace, prompt, **kwargs: task(**kwargs))
    run = workspace_mod.pi_runner(data_dir, store.load(data_dir), "n", "c", deadline=time.monotonic() + 30)
    with pytest.raises(PiRunError, match="timed out"):
        run(tmp_path, "任务", "ch-07.html")
    assert len(calls) == 1


def test_one_shot_calls_the_relay_broke_are_tried_again_too(data_dir, monkeypatch, tmp_path):
    from prometheus.llm.one_shot import OneShotError

    waits = []
    monkeypatch.setattr(workspace_mod.time, "sleep", waits.append)
    shot, calls = _relay(["一次性文本调用失败（exit 1）：503 status code (no body)"], error=OneShotError)
    monkeypatch.setattr(workspace_mod.one_shot, "run_one_shot", lambda work_dir, **kwargs: shot(**kwargs))
    settings = store.load(data_dir)
    assert workspace_mod.model_ask(data_dir, tmp_path, settings, "n", "c")("问题") == "ok"
    assert workspace_mod.model_look(data_dir, tmp_path, settings, "n", "c")("看图", []) == "ok"
    assert len(calls) == 3 and waits == [10]


@pytest.mark.parametrize(("thinking", "times"), [("medium", 3), ("high", 4), ("xhigh", 6), ("max", 8)])
def test_the_time_limit_grows_with_the_thinking_level(data_dir, monkeypatch, thinking, times):
    """User 2026-09-29: at xhigh Kabbalah ran out of the 3x at its sixth chapter of eleven."""
    ctx = _ctx(data_dir)
    settings = store.load(data_dir)
    settings["llm_profiles"]["items"][0]["thinking"] = thinking
    store.save(data_dir, settings)
    seen = []
    monkeypatch.setattr(workspace_mod.full, "run_keypoints", lambda work, units, ask: EMPTY_LEDGER)
    monkeypatch.setattr(workspace_mod.full, "run_plan", lambda work, ledger, run_pi, **kwargs: ({"chapters": []}, []))
    monkeypatch.setattr(workspace_mod.full, "write_chapters", lambda *args, **kwargs: [])
    monkeypatch.setattr(workspace_mod.full, "finish", lambda *args: {})
    monkeypatch.setattr(workspace_mod, "pi_runner",
                        lambda *args, deadline: seen.append(deadline - time.monotonic()) or "runner")
    row = items_store.get_item(data_dir, ctx.item_id)
    workspace_mod.run_full_report_stage(data_dir, ctx.item_id, row, store.load(data_dir), node_exe="n", pi_cli="c",
                                        figures=False, progress=lambda *args: None)
    workspace_mod.run_plan_stage(data_dir, ctx.item_id, row, store.load(data_dir), node_exe="n", pi_cli="c",
                                 figures=False)
    report, plan = seen
    assert times * 1800 - 10 < report <= times * 1800
    assert max(1, times / 3) * 1800 - 10 < plan <= max(1, times / 3) * 1800


def test_the_chapter_report_opens_the_editors_links_through_the_proxy(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    settings = store.load(data_dir)
    settings["network"]["proxy"] = "http://127.0.0.1:7890"
    store.save(data_dir, settings)
    seen = {}
    monkeypatch.setattr(workspace_mod.full, "run_keypoints", lambda work, units, ask: EMPTY_LEDGER)
    monkeypatch.setattr(workspace_mod.full, "run_plan", lambda work, ledger, run_pi, **kwargs: ({"chapters": []}, []))
    monkeypatch.setattr(workspace_mod.full, "write_chapters", lambda *args, **kwargs: seen.update(kwargs) or [])
    monkeypatch.setattr(workspace_mod.full, "finish", lambda *args: {})
    monkeypatch.setattr(workspace_mod.viewpoints, "open_page", lambda url, *, proxy="": seen.setdefault("opened", (url, proxy)) and "页面")
    row = items_store.get_item(data_dir, ctx.item_id)
    workspace_mod.run_full_report_stage(data_dir, ctx.item_id, row, store.load(data_dir), node_exe="n", pi_cli="c",
                                        figures=False, progress=lambda *args: None)
    assert seen["verify_links"]("https://en.wikipedia.org/wiki/X") == "页面"
    assert seen["opened"] == ("https://en.wikipedia.org/wiki/X", "http://127.0.0.1:7890")
