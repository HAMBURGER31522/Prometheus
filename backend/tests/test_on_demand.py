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
