"""Real stage runners driven through the pipeline context (PLAN 8.3).

Every stage receives a StageContext; these tests call the stages exactly the way
the queue does, which the module-level stage tests never exercised.
"""

import pytest
from conftest import DUMMY_RUNTIME
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
        stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["transcribe"](ctx)
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
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["frames"](ctx)
    assert seen["video"].name == "video.mp4"


def test_report_stage_receives_the_item_row(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    seen = {}

    def fake_run(data_dir_arg, item_id, row, settings, **kwargs):
        seen["item_id"] = item_id
        seen["row_id"] = row["id"]

    monkeypatch.setattr(stages_mod.workspace_mod, "run_report_stage", fake_run)
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["report"](ctx)
    assert seen == {"item_id": ctx.item_id, "row_id": ctx.item_id}


def test_finalize_stage_records_the_report_title(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    monkeypatch.setattr(stages_mod, "finalize_report", lambda source, target, work: "报告标题")
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["finalize"](ctx)
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
    monkeypatch.setattr(stages_mod, "classify_item", lambda *args, **kwargs: {
        "category": "测试分类", "tags": ["标签"], "description": "一句话。"})
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["classify"](ctx)
    assert items_store.get_item(data_dir, ctx.item_id)["category_id"] is not None


def test_mindmap_stage_marks_failure_when_output_never_validates(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    _write_report(data_dir, ctx.item_id)
    monkeypatch.setattr(stages_mod.one_shot_mod, "run_one_shot", lambda *args, **kwargs: "")
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["mindmap"](ctx)
    assert items_store.get_item(data_dir, ctx.item_id)["mindmap_status"] == "failed"


def test_report_stage_asks_pi_whether_a_builtin_model_sees_images(data_dir, monkeypatch):
    ctx = _ctx(data_dir, figures=1)
    work = paths.work_dir(data_dir, ctx.item_id)
    (work / "frames").mkdir(parents=True)
    (work / "frames" / "frames.json").write_text("[]", encoding="utf-8")
    seen = {}

    def fake_run(data_dir_arg, item_id, row, settings, **kwargs):
        seen.update(kwargs)

    from prometheus.llm import capability

    # Default settings use the built-in deepseek provider (no custom checkbox involved).
    monkeypatch.setattr(capability, "query_supports_images", lambda *a, **k: True, raising=False)
    monkeypatch.setattr(stages_mod.workspace_mod, "run_report_stage", fake_run)
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["report"](ctx)
    assert seen["model_supports_images"] is True


def _audio_ready(data_dir, ctx, monkeypatch, backend):
    import json

    from prometheus.settings import store

    settings = store.load(data_dir)
    settings["asr"] = {"backend": backend}
    store.save(data_dir, settings)
    work = paths.work_dir(data_dir, ctx.item_id)
    (work / "media.m4a").write_bytes(b"audio")
    monkeypatch.setattr(stages_mod, "to_wav", lambda source, target: target)
    monkeypatch.setattr(stages_mod, "to_mp3", lambda source, target: target)

    def local_run(engine):
        def transcribe_local(data_dir_, item_id, wav):
            out = paths.work_dir(data_dir_, item_id) / "asr.json"
            out.write_text(json.dumps({"engine": engine, "language": "zh", "segments": [
                {"ordinal": 0, "start_ms": 0, "end_ms": 1500, "text": "你好"}]}), encoding="utf-8")
            return out
        return transcribe_local
    return local_run


def test_cloud_transcription_goes_to_bcut(data_dir, monkeypatch):
    import json

    from prometheus.transcribe import bcut

    ctx = _ctx(data_dir)
    _audio_ready(data_dir, ctx, monkeypatch, "cloud")
    monkeypatch.setattr(bcut, "transcribe", lambda mp3, **kw: [{"start": 0.0, "end": 1.5, "text": "你好"}])

    def no_local(*args):
        raise AssertionError("local transcription ran although 必剪 worked")

    monkeypatch.setattr(stages_mod.local_mod, "transcribe_local", no_local)
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["transcribe"](ctx)
    asr = json.loads((paths.work_dir(data_dir, ctx.item_id) / "asr.json").read_text(encoding="utf-8"))
    assert asr["engine"] == "bcut"
    assert paths.segments_file(data_dir, ctx.item_id).is_file()
    row = items_store.get_item(data_dir, ctx.item_id)
    assert row.get("transcript_source") == "bcut"
    assert row.get("notice") is None


def test_bcut_unavailable_falls_back_to_local_with_a_notice(data_dir, monkeypatch):
    # PLAN 15.4.4: 412 / 429 / timeouts / failed tasks -> local, and the item says so.
    from prometheus.transcribe import bcut

    ctx = _ctx(data_dir)
    local_run = _audio_ready(data_dir, ctx, monkeypatch, "cloud")

    def unavailable(mp3, **kw):
        raise bcut.BcutUnavailable("必剪返回 HTTP 412")

    monkeypatch.setattr(bcut, "transcribe", unavailable)
    monkeypatch.setattr(stages_mod.local_mod, "transcribe_local", local_run("funasr-onnx"))
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["transcribe"](ctx)
    row = items_store.get_item(data_dir, ctx.item_id)
    assert row.get("notice") == "必剪不可用，已改用本地转写"
    assert row.get("transcript_source") == "funasr-onnx"


def test_local_transcription_records_the_engine_it_used(data_dir, monkeypatch):
    ctx = _ctx(data_dir)
    local_run = _audio_ready(data_dir, ctx, monkeypatch, "local")
    monkeypatch.setattr(stages_mod.local_mod, "transcribe_local", local_run("faster-whisper"))
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["transcribe"](ctx)
    assert items_store.get_item(data_dir, ctx.item_id).get("transcript_source") == "faster-whisper"


def _youtube_ctx(data_dir, *, language, subtitles, figures=0):
    import json

    item_id = items_store.create_item(
        data_dir, platform="youtube", video_id="BHY0FxzoKZE",
        source_url="https://www.youtube.com/watch?v=BHY0FxzoKZE", figures=figures,
    )
    work = paths.work_dir(data_dir, item_id)
    work.mkdir(parents=True, exist_ok=True)
    (work / "source.info.json").write_text(json.dumps({
        "language": language, "subtitles": {key: [{"ext": "vtt"}] for key in subtitles},
    }), encoding="utf-8")
    return StageContext(data_dir, item_id)


def test_a_manual_subtitle_is_downloaded_instead_of_the_audio(data_dir, monkeypatch):
    from prometheus.ingest import platform_subtitles

    ctx = _youtube_ctx(data_dir, language="en", subtitles=["en", "de"], figures=1)
    fetched = []
    monkeypatch.setattr(stages_mod.download_mod, "download_stage",
                        lambda work, row, settings, node, *, media: fetched.append(media))
    monkeypatch.setattr(platform_subtitles, "download_subtitle",
                        lambda work, row, settings, node, language: fetched.append(("subtitle", language)))
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["download"](ctx)
    assert fetched == [("subtitle", "en"), "video"]


def test_a_downloaded_subtitle_replaces_transcription(data_dir, monkeypatch):
    import json

    ctx = _youtube_ctx(data_dir, language="zh", subtitles=["zh-TW"])
    work = paths.work_dir(data_dir, ctx.item_id)
    (work / "subtitle.zh-TW.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.500\n這是字幕\n", encoding="utf-8")

    def no_audio(*args):
        raise AssertionError("audio was converted although a manual subtitle exists")

    monkeypatch.setattr(stages_mod, "to_wav", no_audio)
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["transcribe"](ctx)
    asr = json.loads((work / "asr.json").read_text(encoding="utf-8"))
    assert asr["engine"] == "youtube-subtitles" and asr["language"] == "zh"
    segments = json.loads(paths.segments_file(data_dir, ctx.item_id).read_text(encoding="utf-8"))
    assert segments == [{"start": 1.0, "end": 2.5, "text": "这是字幕"}]
    assert items_store.get_item(data_dir, ctx.item_id).get("transcript_source") == "youtube-subtitles"
