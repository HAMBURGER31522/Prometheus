"""Real stage runners driven through the pipeline context (PLAN 8.3).

Every stage receives a StageContext; these tests call the stages exactly the way
the queue does, which the module-level stage tests never exercised.
"""

import pytest
from prometheus import paths
from prometheus.library import db
from prometheus.library import items as items_store
from prometheus.tasks import stages as stages_mod
from prometheus.tasks.runner import StageContext


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
    return StageContext(data_dir, item_id)


class _Stop(Exception):
    """Raised by doubles once they have captured their input."""


def test_transcribe_converts_the_audio_not_the_info_json_sidecar(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    work = paths.work_dir(data_dir, ctx.item_id)
    (work / "media.info.json").write_text("{}", encoding="utf-8")
    (work / "media.m4a").write_bytes(b"audio")
    seen = {}

    def fake_to_wav(source, target):
        seen["source"] = source
        raise _Stop

    monkeypatch.setattr(stages_mod, "to_wav", fake_to_wav)
    with pytest.raises(_Stop):
        stages_mod.build_real_impls(data_dir)["transcribe"](ctx)
    assert seen["source"].name == "media.m4a"


def test_frames_extracts_from_the_video_not_the_info_json_sidecar(data_dir, monkeypatch):
    ctx = _ctx(data_dir, figures=1)
    work = paths.work_dir(data_dir, ctx.item_id)
    (work / "video.info.json").write_text("{}", encoding="utf-8")
    (work / "video.mp4").write_bytes(b"video")
    seen = {}

    def fake_extract(video, work_dir):
        seen["video"] = video

    monkeypatch.setattr(stages_mod.frames_mod, "extract_frames", fake_extract)
    stages_mod.build_real_impls(data_dir)["frames"](ctx)
    assert seen["video"].name == "video.mp4"


def test_report_stage_receives_the_item_row(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    seen = {}

    def fake_run(data_dir_arg, item_id, row, settings, **kwargs):
        seen["item_id"] = item_id
        seen["row_id"] = row["id"]

    monkeypatch.setattr(stages_mod.workspace_mod, "run_report_stage", fake_run)
    stages_mod.build_real_impls(data_dir)["report"](ctx)
    assert seen == {"item_id": ctx.item_id, "row_id": ctx.item_id}


def test_finalize_stage_records_the_report_title(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    monkeypatch.setattr(stages_mod, "finalize_report", lambda source, target, work: "报告标题")
    stages_mod.build_real_impls(data_dir)["finalize"](ctx)
    assert items_store.get_item(data_dir, ctx.item_id)["report_title"] == "报告标题"


def _write_report(data_dir, item_id):
    target = paths.report_file(data_dir, item_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '<html><body><h1>报告标题</h1><p class="lede">导语。</p>'
        '<h2>第一章<span class="section-time">00:00–01:00</span></h2><p>正文。</p>'
        "</body></html>",
        encoding="utf-8",
    )


def test_classify_stage_assigns_a_category(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    _write_report(data_dir, ctx.item_id)
    monkeypatch.setattr(stages_mod, "classify_report", lambda *args, **kwargs: "测试分类")
    stages_mod.build_real_impls(data_dir)["classify"](ctx)
    assert items_store.get_item(data_dir, ctx.item_id)["category_id"] is not None


def test_mindmap_stage_marks_failure_when_output_never_validates(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    _write_report(data_dir, ctx.item_id)
    monkeypatch.setattr(stages_mod.one_shot_mod, "run_one_shot", lambda *args, **kwargs: "")
    stages_mod.build_real_impls(data_dir)["mindmap"](ctx)
    assert items_store.get_item(data_dir, ctx.item_id)["mindmap_status"] == "failed"
