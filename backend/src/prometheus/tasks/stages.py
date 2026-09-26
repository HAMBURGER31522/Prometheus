"""Real stage implementations wired into the queue (PLAN 8.3)."""

import json
from pathlib import Path

from prometheus import paths
from prometheus import runtime as runtime_mod
from prometheus.figures import frames as frames_mod
from prometheus.ingest import download as download_mod
from prometheus.ingest import resolve as resolve_mod
from prometheus.library import categories as categories_store
from prometheus.library import items as items_store
from prometheus.llm import capability
from prometheus.llm import one_shot as one_shot_mod
from prometheus.mindmap import generate as mindmap_generate
from prometheus.report import workspace as workspace_mod
from prometheus.report.classify import classify_report
from prometheus.report.finalize import finalize_report
from prometheus.report.outline import extract_outline
from prometheus.settings import store
from prometheus.subtitle import convert as subtitle_convert
from prometheus.subtitle import format as subtitle_format
from prometheus.transcribe import cloud as cloud_mod
from prometheus.transcribe import local as local_mod
from prometheus.transcribe.audio import to_wav
from prometheus.transcribe.transcript import build_transcript_md


def _row(data_dir, ctx):
    row = items_store.get_item(data_dir, ctx.item_id)
    if row is None:
        raise RuntimeError(f"item disappeared: {ctx.item_id}")
    return row


def _work(data_dir, ctx):
    work = paths.work_dir(data_dir, ctx.item_id)
    work.mkdir(parents=True, exist_ok=True)
    return work


def _asr_to_segments(asr_payload: dict) -> list:
    return [
        {
            "start": segment["start_ms"] / 1000,
            "end": segment["end_ms"] / 1000,
            "text": segment["text"],
        }
        for segment in asr_payload.get("segments", [])
    ]


def _write_subtitle_files(data_dir, ctx, asr_path) -> None:
    payload = json.loads(Path(asr_path).read_text(encoding="utf-8"))
    segments = subtitle_convert.maybe_simplify(_asr_to_segments(payload), payload.get("language"))
    segments_file = paths.segments_file(data_dir, ctx.item_id)
    segments_file.write_text(
        json.dumps(segments, ensure_ascii=False), encoding="utf-8",
    )
    paths.srt_file(data_dir, ctx.item_id).write_text(
        subtitle_format.to_srt(segments), encoding="utf-8",
    )


def build_real_impls(data_dir, runtime=None) -> dict:
    """``runtime``: a resolved Runtime, or a zero-argument callable returning one."""

    def _rt():
        found = runtime() if callable(runtime) else runtime
        return found if found is not None else runtime_mod.resolve(None)

    def _node_exe() -> str:
        return str(_rt().node)

    def _pi_cli() -> str:
        return str(_rt().pi_cli)

    def resolve(ctx):
        row = _row(data_dir, ctx)
        updates = resolve_mod.resolve_stage(
            _work(data_dir, ctx), row, store.load(data_dir), _node_exe(),
        )
        items_store.update_item(data_dir, ctx.item_id, **updates)

    def download(ctx):
        row = _row(data_dir, ctx)
        settings = store.load(data_dir)
        work = _work(data_dir, ctx)
        media = ["audio"] + (["video"] if row["figures"] else [])
        for kind in media:
            download_mod.download_stage(work, row, settings, _node_exe(), media=kind)

    def transcribe(ctx):
        work = _work(data_dir, ctx)
        audio = download_mod.downloaded_file(work, "media")
        if audio is None:
            raise FileNotFoundError("work/media.* is missing after download")
        wav = to_wav(audio, work / "audio.wav")
        backend = store.load(data_dir)["asr"]["backend"]
        if backend == "cloud":
            asr_path = cloud_mod.transcribe_cloud(data_dir, ctx.item_id, wav)
        else:
            asr_path = local_mod.transcribe_local(data_dir, ctx.item_id, wav)
        _write_subtitle_files(data_dir, ctx, asr_path)

    def transcript(ctx):
        row = _row(data_dir, ctx)
        work = _work(data_dir, ctx)
        metadata = {
            "title": row["report_title"] or row["source_title"] or row["video_id"],
            "uploader": row["uploader"] or "",
            "attribution": (
                f"{row['uploader'] or '未知UP主'} · {row['source_title'] or row['video_id']}"
            ),
            "url": row["source_url"],
            "video_id": row["video_id"].split("?")[0],
            "platform": row["platform"],
            "duration_s": row["duration_s"] or 0.0,
        }
        build_transcript_md(work, work / "asr.json", metadata)

    def frames(ctx):
        row = _row(data_dir, ctx)
        work = _work(data_dir, ctx)
        if not row["figures"]:
            return
        video = download_mod.downloaded_file(work, "video")
        if video is None:
            return
        frames_mod.extract_frames(video, work)

    def report(ctx):
        row = _row(data_dir, ctx)
        settings = store.load(data_dir)
        work = _work(data_dir, ctx)
        figures = bool(row["figures"]) and (work / "frames" / "frames.json").is_file()
        # Ask Pi (built-in and custom providers alike) only when frames exist.
        supports_images = figures and capability.query_supports_images(
            _node_exe(), _pi_cli(), data_dir, settings["llm"],
        )
        workspace_mod.run_report_stage(
            data_dir, ctx.item_id, row, settings,
            node_exe=_node_exe(), pi_cli=_pi_cli(),
            figures=figures, model_supports_images=supports_images,
        )

    def finalize(ctx):
        work = _work(data_dir, ctx)
        title = finalize_report(
            work / "report.html", paths.report_file(data_dir, ctx.item_id), work,
        )
        items_store.update_item(data_dir, ctx.item_id, report_title=title)

    def classify(ctx):
        settings = store.load(data_dir)
        work = _work(data_dir, ctx)
        html = paths.report_file(data_dir, ctx.item_id).read_text(encoding="utf-8")
        outline = extract_outline(html)
        h2_titles = [section["title"] for section in outline["sections"]]
        existing = [c["name"] for c in categories_store.list_categories(data_dir)]
        llm = settings["llm"]
        name = classify_report(
            work, outline["title"], outline["intro"][:500], h2_titles, existing,
            one_shot=one_shot_mod.run_one_shot,
            provider=llm["provider"], model=llm["model"],
            api_key=llm.get("api_key") or "", thinking=llm.get("thinking") or "low",
            node_exe=_node_exe(), pi_cli=_pi_cli(),
            agent_dir=paths.pi_config_dir(data_dir),
        )
        category_id = categories_store.ensure_category(data_dir, name)
        items_store.update_item(data_dir, ctx.item_id, category_id=category_id)

    def mindmap(ctx):
        mindmap_generate.generate_for_item(
            data_dir, ctx.item_id, _row(data_dir, ctx), store.load(data_dir)["llm"],
            node_exe=_node_exe(), pi_cli=_pi_cli(),
        )

    return {
        "resolve": resolve,
        "download": download,
        "transcribe": transcribe,
        "transcript": transcript,
        "frames": frames,
        "report": report,
        "finalize": finalize,
        "classify": classify,
        "mindmap": mindmap,
    }
