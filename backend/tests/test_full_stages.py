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
