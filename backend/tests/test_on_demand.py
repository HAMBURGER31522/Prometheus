"""按需生成 (PLAN 15.4.15): what a video gets — the report (with its mind map), the subtitles — and how
detailed its report is, for this video only."""

import pytest
from conftest import BV_URL
from prometheus.library import items as items_store

ALL = {"report": True, "subtitles": True, "mindmap": True}
SUBTITLES = {"report": False, "subtitles": True, "mindmap": False}


def _submit(client, **body):
    return client.post("/api/items", json={"url": BV_URL, "figures": False, **body})


def _row(client, item_id):
    return client.get(f"/api/items/{item_id}").json()


# ---------------- the submit (E17 ①: saved and checked) ----------------

def test_a_submit_keeps_what_the_video_gets_and_how_detailed(client):
    outputs = {"report": True, "subtitles": False, "mindmap": False}
    item_id = _submit(client, figures=True, outputs=outputs, depth="standard").json()["id"]
    row = _row(client, item_id)
    assert row.get("outputs") == outputs
    assert row.get("depth") == "standard"
    assert row["figures"] == 1


def test_without_a_report_there_are_no_figures_to_draw(client):
    item_id = _submit(client, figures=True, outputs=SUBTITLES, depth="full").json()["id"]
    row = _row(client, item_id)
    assert row.get("outputs") == SUBTITLES
    assert row["figures"] == 0


def test_old_items_and_old_clients_get_all_three_at_the_settings_depth(client):
    """PLAN 15.4.15-6: items from before R7h have all three and follow the settings' depth."""
    item_id = _submit(client).json()["id"]
    row = _row(client, item_id)
    assert row.get("outputs") == ALL
    assert "depth" in row and row["depth"] is None
    old = items_store.create_item(client.app.state.data_dir, platform="bilibili", video_id="BV1old00000",
                                  source_url="https://www.bilibili.com/video/BV1old00000/", status="done")
    assert _row(client, old).get("outputs") == ALL
    listed = {row["id"]: row for row in client.get("/api/items").json()}
    assert listed[old].get("outputs") == ALL
    queued = {row["id"]: row for row in client.get("/api/queue").json()}
    assert queued[old].get("outputs") == ALL


@pytest.mark.parametrize(("body", "code"), [
    ({"outputs": {"report": False, "subtitles": False, "mindmap": False}}, "OUTPUTS_INVALID"),
    ({"outputs": {"report": False, "subtitles": True, "mindmap": True}}, "OUTPUTS_INVALID"),
    ({"outputs": {"report": False, "subtitles": False, "mindmap": True}}, "OUTPUTS_INVALID"),
    ({"outputs": {"report": True}}, "OUTPUTS_INVALID"),
    ({"outputs": {"report": "yes", "subtitles": True, "mindmap": False}}, "OUTPUTS_INVALID"),
    ({"outputs": ["report", "subtitles"]}, "OUTPUTS_INVALID"),
    ({"depth": "deep"}, "DEPTH_INVALID"),
    ({"depth": None, "outputs": SUBTITLES}, "DEPTH_INVALID"),
])
def test_nothing_to_make_a_map_without_its_report_or_an_unknown_depth_is_refused(client, body, code):
    response = _submit(client, **body)
    assert response.status_code == 422
    assert response.json() == {"code": code}
    assert client.get("/api/items").json() == []


# ---------------- which steps run (E17 ①) ----------------

REPORT_STEPS = {"frames", "keypoints", "plan", "report", "finalize"}
SUBTITLE_STEPS = ["resolve", "download", "transcribe", "transcript", "subtitle_fix", "classify", "publish"]


def _finished(client, item_id) -> list:
    import json

    from prometheus import paths

    trace = paths.work_dir(client.app.state.data_dir, item_id) / "run.trace.jsonl"
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    return [event["stage"] for event in events if event["event"] == "end"]


@pytest.mark.parametrize(("outputs", "skipped"), [
    (ALL, set()),
    ({"report": True, "subtitles": True, "mindmap": False}, {"mindmap"}),
    ({"report": True, "subtitles": False, "mindmap": True}, {"subtitle_fix"}),
    ({"report": True, "subtitles": False, "mindmap": False}, {"subtitle_fix", "mindmap"}),
    (SUBTITLES, REPORT_STEPS | {"mindmap"}),
])
def test_each_choice_runs_only_its_steps(client, outputs, skipped):
    from conftest import wait_for_status
    from prometheus.tasks import runner

    item_id = _submit(client, outputs=outputs, depth="standard").json()["id"]
    wait_for_status(client, item_id, "done")
    assert _finished(client, item_id) == [stage for stage in runner.STAGES if stage not in skipped]


def test_the_console_counts_only_the_steps_this_video_runs(client):
    item_id = _submit(client, outputs=SUBTITLES, depth="standard").json()["id"]
    assert _row(client, item_id).get("stages") == SUBTITLE_STEPS
    queued = {row["id"]: row for row in client.get("/api/queue").json()}
    assert queued[item_id].get("stages") == SUBTITLE_STEPS
    from prometheus.tasks import runner

    old = items_store.create_item(client.app.state.data_dir, platform="bilibili", video_id="BV1old00000",
                                  source_url="https://www.bilibili.com/video/BV1old00000/", status="done")
    assert _row(client, old).get("stages") == runner.STAGES


@pytest.fixture
def data_dir(tmp_path):
    from prometheus import paths
    from prometheus.library import db

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    return data_dir


def _item(data_dir, video_id="BV1xJYT6EEYc", **fields):
    return items_store.create_item(data_dir, platform="bilibili", video_id=video_id,
                                   source_url=f"https://www.bilibili.com/video/{video_id}/", **fields)


@pytest.mark.parametrize(("settings_depth", "item_depth", "written"), [
    ("full", "standard", "standard"),
    ("standard", "full", "full"),
    ("standard", None, "standard"),
    ("full", None, "full"),
])
def test_the_report_is_written_at_the_videos_own_depth(data_dir, monkeypatch, settings_depth, item_depth, written):
    """PLAN 15.4.15-2: the switch beside the link box is for this one video; items from before follow the settings."""
    from conftest import DUMMY_RUNTIME
    from prometheus.settings import store
    from prometheus.tasks import stages as stages_mod
    from prometheus.tasks.runner import StageContext

    settings = store.load(data_dir)
    settings["report"] = {"depth": settings_depth, "review": True}
    store.save(data_dir, settings)
    ctx = StageContext(data_dir, _item(data_dir, depth=item_depth))
    called = []
    for name, label in (("run_keypoints_stage", "keypoints"), ("run_plan_stage", "plan"),
                        ("run_full_report_stage", "full"), ("run_report_stage", "standard")):
        monkeypatch.setattr(stages_mod.workspace_mod, name, lambda *a, label=label, **k: called.append(label))
    impls = stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)
    for stage in ("keypoints", "plan", "report"):
        impls[stage](ctx)
    assert called == (["keypoints", "plan", "full"] if written == "full" else ["standard"])


def test_a_restart_does_not_call_a_map_nobody_asked_for_failed(data_dir):
    """A mind map rerun cut short by quitting is marked failed; a video without a map has none to fail."""
    from prometheus.library import db

    rerun = _item(data_dir, "BV1rerun0000", status="done")  # from before R7h: all three
    no_map = _item(data_dir, "BV1nomap0000", status="done", outputs={"report": True, "subtitles": True, "mindmap": False})
    subtitles = _item(data_dir, "BV1subs00000", status="done", outputs=SUBTITLES)
    db.mark_running_as_interrupted(data_dir)
    assert items_store.get_item(data_dir, rerun)["mindmap_status"] == "failed"
    assert items_store.get_item(data_dir, no_map)["mindmap_status"] is None
    assert items_store.get_item(data_dir, subtitles)["mindmap_status"] is None
