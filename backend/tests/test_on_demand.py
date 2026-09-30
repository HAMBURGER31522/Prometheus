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


# ---------------- without a report (E17 ①) ----------------

def _segments(data_dir, item_id, texts):
    import json

    from prometheus import paths

    target = paths.segments_file(data_dir, item_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"start": index * 12.0, "end": index * 12.0 + 12, "text": text} for index, text in enumerate(texts)]
    target.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def test_without_a_report_the_video_is_filed_by_its_title_and_how_the_transcript_opens(data_dir, monkeypatch):
    from conftest import DUMMY_RUNTIME
    from prometheus.library import categories as categories_store
    from prometheus.tasks import stages as stages_mod
    from prometheus.tasks.runner import StageContext

    item_id = _item(data_dir, outputs=SUBTITLES)
    items_store.update_item(data_dir, item_id, source_title="手冲咖啡入门：从磨豆开始")
    _segments(data_dir, item_id, ["今天我们来讲手冲咖啡。", "先说磨豆的粗细。"])
    prompts = []

    def one_shot(work, *, prompt, **kwargs):
        prompts.append(prompt)
        return '{"category": "咖啡", "tags": ["手冲", "磨豆"], "description": "讲怎么在家做手冲咖啡。"}'

    monkeypatch.setattr(stages_mod.one_shot_mod, "run_one_shot", one_shot)
    try:
        stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["classify"](StageContext(data_dir, item_id))
    except FileNotFoundError as missing:
        pytest.fail(f"classify still needs a report: {missing}")
    assert "手冲咖啡入门：从磨豆开始" in prompts[0] and "今天我们来讲手冲咖啡。" in prompts[0]
    assert "报告标题" not in prompts[0]
    row = items_store.get_item(data_dir, item_id)
    names = {c["id"]: c["name"] for c in categories_store.list_categories(data_dir)}
    assert names[row["category_id"]] == "咖啡"
    assert row["description"] == "讲怎么在家做手冲咖啡。"


def test_without_a_report_the_library_folder_and_the_index_hold_only_what_was_made(client):
    import json

    from conftest import wait_for_status
    from prometheus.library import layout

    item_id = _submit(client, outputs=SUBTITLES, depth="standard").json()["id"]
    row = wait_for_status(client, item_id, "done")
    data_dir = client.app.state.data_dir
    folder = data_dir / row["library_path"]
    assert sorted(path.name for path in folder.iterdir()) == ["字幕.srt", "字幕.txt", "来源.url"]
    assert folder.name.endswith(layout.safe_name(row["source_title"]))
    entries = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))["items"]
    entry = next(entry for entry in entries if entry["id"] == item_id)
    assert set(entry["paths"]) == {"srt", "txt", "url"}
    listing = (folder.parent / "_index.md").read_text(encoding="utf-8")
    assert f"({folder.name}/字幕.txt)" in listing
    assert "精读.md" not in listing


def test_without_a_report_the_subtitles_are_corrected_without_reference(data_dir):
    """PLAN 15.4.15-4 (R6b was accepted this way); with a report its text is the reference."""
    from prometheus import paths
    from prometheus.subtitle import fix

    alone = _item(data_dir, "BV1alone0000", outputs=SUBTITLES)
    with_report = _item(data_dir, "BV1report000")
    for item_id in (alone, with_report):
        _segments(data_dir, item_id, ["今天我们来讲手冲咖啡。"])
    paths.report_file(data_dir, with_report).parent.mkdir(parents=True, exist_ok=True)
    paths.report_file(data_dir, with_report).write_text(
        "<html><body><h1>手冲咖啡</h1><p>磨豆要均匀。</p></body></html>", encoding="utf-8")
    prompts = {}
    for item_id in (alone, with_report):
        fix.fix_for_item(data_dir, item_id, items_store.get_item(data_dir, item_id), {}, node_exe="", pi_cli="",
                         ask=lambda prompt, item_id=item_id: prompts.setdefault(item_id, prompt) and "{}")
    # The rules name 「参考材料」 either way, as when R6b was accepted; the report itself is what is left out.
    assert "今天我们来讲手冲咖啡。" in prompts[alone] and "参考材料（报告）：" not in prompts[alone]
    assert "参考材料（报告）：" in prompts[with_report] and "磨豆要均匀。" in prompts[with_report]


# ---------------- 「现在生成」 (E17 ①: only the missing steps) ----------------

FILLED_REPORT = ["keypoints", "plan", "report", "finalize", "mindmap", "publish"]


def _done(client, outputs):
    from conftest import wait_for_status

    item_id = _submit(client, outputs=outputs, depth="standard").json()["id"]
    wait_for_status(client, item_id, "done")
    return item_id


def _runs(client, item_id) -> list:
    """The finished steps of each run, oldest first."""
    import json

    from prometheus import paths

    trace = paths.work_dir(client.app.state.data_dir, item_id) / "run.trace.jsonl"
    runs: dict = {}
    for event in map(json.loads, trace.read_text(encoding="utf-8").splitlines()):
        if event["event"] == "end":
            runs.setdefault(event["run"], []).append(event["stage"])
    return list(runs.values())


def _settled(client, item_id, until, timeout=15.0):
    """The row once the fill-in is over and `until(row)` holds."""
    import time

    deadline = time.time() + timeout
    row = None
    while time.time() < deadline:
        row = _row(client, item_id)
        if row["stage"] is None and until(row):
            return row
        time.sleep(0.05)
    raise AssertionError(f"never settled: {row!r}")


def _fill(client, item_id, **body):
    return client.post(f"/api/items/{item_id}/regenerate", json=body)


def test_filling_in_the_report_with_figures_downloads_only_the_picture_and_cleans_it_after(client, monkeypatch):
    from prometheus import paths
    from prometheus.library import layout

    item_id = _done(client, SUBTITLES)
    work = paths.work_dir(client.app.state.data_dir, item_id)

    def video(ctx):
        (work / "video.mp4").write_bytes(b"picture")

    def frames(ctx):
        (work / "frames").mkdir(exist_ok=True)
        (work / "frames" / "f_0001.jpg").write_bytes(b"jpg")

    monkeypatch.setitem(client.app.state.queue.impls, "video", video)
    monkeypatch.setitem(client.app.state.queue.impls, "frames", frames)
    response = _fill(client, item_id, only="report", depth="full", figures=True)
    assert response.status_code == 200
    row = _settled(client, item_id, lambda row: row["outputs"]["report"])
    assert row["outputs"] == {"report": True, "subtitles": False, "mindmap": True}
    assert (row["status"], row["depth"], row["figures"]) == ("done", "full", 1)
    assert _runs(client, item_id)[-1] == ["video", "frames", *FILLED_REPORT]
    folder = client.app.state.data_dir / row["library_path"]
    assert {"精读.html", "精读.md", "思维导图.md", "字幕.txt"} <= {path.name for path in folder.iterdir()}
    assert folder.name.endswith(layout.safe_name(row["report_title"]))  # the report's title names the folder
    assert not (work / "video.mp4").exists() and not (work / "frames").exists()  # user 2026-09-30


def test_filling_in_the_report_without_figures_downloads_nothing(client):
    item_id = _done(client, SUBTITLES)
    assert _fill(client, item_id, only="report", depth="standard", figures=False).status_code == 200
    row = _settled(client, item_id, lambda row: row["outputs"]["report"])
    assert (row["depth"], row["figures"]) == ("standard", 0)
    assert _runs(client, item_id)[-1] == FILLED_REPORT


def test_filling_in_the_subtitles_only_corrects_them(client):
    item_id = _done(client, {"report": True, "subtitles": False, "mindmap": True})
    assert _fill(client, item_id, only="subtitles").status_code == 200
    row = _settled(client, item_id, lambda row: row["outputs"]["subtitles"])
    assert row["outputs"] == ALL and row["subtitle_status"] == "ok"
    assert _runs(client, item_id)[-1] == ["subtitle_fix", "publish"]


def test_filling_in_the_map_needs_its_report(client):
    item_id = _done(client, {"report": True, "subtitles": True, "mindmap": False})
    assert _fill(client, item_id, only="mindmap").status_code == 200
    row = _settled(client, item_id, lambda row: row["mindmap_status"] == "ok")
    assert row["outputs"] == ALL
    assert _runs(client, item_id)[-1] == ["mindmap", "publish"]
    no_report = _done(client, SUBTITLES)
    response = _fill(client, no_report, only="mindmap")
    assert (response.status_code, response.json()) == (409, {"code": "NO_REPORT"})


def test_filling_in_what_is_there_an_unknown_depth_or_an_unfinished_item_is_refused(client):
    full = _done(client, ALL)
    response = _fill(client, full, only="report", depth="standard", figures=False)
    assert (response.status_code, response.json()) == (409, {"code": "ALREADY_MADE"})
    response = _fill(client, full, only="subtitles")
    assert (response.status_code, response.json()) == (409, {"code": "ALREADY_MADE"})
    subtitles = _done(client, SUBTITLES)
    response = _fill(client, subtitles, only="report", depth="deep", figures=False)
    assert (response.status_code, response.json()) == (422, {"code": "DEPTH_INVALID"})
    items_store.update_item(client.app.state.data_dir, subtitles, status="failed")
    response = _fill(client, subtitles, only="report", depth="standard", figures=False)
    assert (response.status_code, response.json()) == (409, {"code": "NOT_DONE"})


def test_a_failed_fill_in_leaves_the_item_done_says_why_and_can_be_tried_again(client, monkeypatch):
    from video_report_agent.pi import PiError

    item_id = _done(client, SUBTITLES)

    def report_times_out(ctx):
        raise PiError("EXTERNAL_MODEL_FAILURE", "Request timed out.")

    monkeypatch.setitem(client.app.state.queue.impls, "report", report_times_out)
    assert _fill(client, item_id, only="report", depth="standard", figures=False).status_code == 200
    row = _settled(client, item_id, lambda row: row["error_code"] is not None)
    assert row["status"] == "done" and row["outputs"] == SUBTITLES
    assert row["error_reason"]
    monkeypatch.undo()
    assert _fill(client, item_id, only="report", depth="standard", figures=False).status_code == 200
    row = _settled(client, item_id, lambda row: row["outputs"]["report"])
    assert row["error_code"] is None and row["error_message"] is None


def test_one_fill_in_at_a_time(client, monkeypatch):
    import threading

    item_id = _done(client, SUBTITLES)
    release = threading.Event()
    started = threading.Event()

    def slow_plan(ctx):
        started.set()
        release.wait(timeout=10)

    monkeypatch.setitem(client.app.state.queue.impls, "plan", slow_plan)
    try:
        assert _fill(client, item_id, only="report", depth="standard", figures=False).status_code == 200
        assert started.wait(timeout=10)
        assert _row(client, item_id)["stage"] == "plan"
        response = _fill(client, item_id, only="report", depth="standard", figures=False)
        assert (response.status_code, response.json()) == (409, {"code": "BUSY"})
    finally:
        release.set()
    _settled(client, item_id, lambda row: row["outputs"]["report"])


def test_a_waiting_fill_in_shows_as_waiting(client, monkeypatch):
    """Queued behind another video: the row already has a step, and says it has not started."""
    import threading
    import time

    first = _done(client, SUBTITLES)
    release = threading.Event()
    monkeypatch.setitem(client.app.state.queue.impls, "resolve", lambda ctx: release.wait(timeout=10))
    other = client.post("/api/items", json={"url": "https://www.bilibili.com/video/BV1bZhQ6VEQK/", "figures": False})
    try:
        deadline = time.time() + 10
        while _row(client, other.json()["id"])["status"] != "running" and time.time() < deadline:
            time.sleep(0.05)
        assert _fill(client, first, only="subtitles").status_code == 200
        row = _row(client, first)
        assert (row["stage"], row["stage_detail"]) == ("subtitle_fix", "排队中")
    finally:
        release.set()
    _settled(client, first, lambda row: row["outputs"]["subtitles"])


def test_a_restart_ends_a_fill_in_cut_short(data_dir):
    from prometheus.library import db

    cut = _item(data_dir, status="done", outputs=SUBTITLES)
    items_store.update_item(data_dir, cut, stage="report", stage_detail="写作（第 2/5 章）")
    db.mark_running_as_interrupted(data_dir)
    row = items_store.get_item(data_dir, cut)
    assert (row["status"], row["stage"], row["stage_detail"]) == ("done", None, None)


def test_the_picture_step_downloads_only_the_video(data_dir, monkeypatch):
    from conftest import DUMMY_RUNTIME
    from prometheus.tasks import stages as stages_mod
    from prometheus.tasks.runner import StageContext

    item_id = _item(data_dir, status="done", outputs=SUBTITLES, figures=1)
    downloaded = []
    monkeypatch.setattr(stages_mod.download_mod, "download_stage", lambda *a, media: downloaded.append(media))
    impls = stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)
    assert "video" in impls, "no step downloads the picture alone"
    impls["video"](StageContext(data_dir, item_id))
    assert downloaded == ["video"]
