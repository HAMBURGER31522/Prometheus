"""Real stage implementations wired into the queue (PLAN 8.3)."""

import json
import os
import shutil
from pathlib import Path

from prometheus import paths
from prometheus.ingest import download as download_mod
from prometheus.ingest import resolve as resolve_mod
from prometheus.library import items as items_store
from prometheus.settings import store
from prometheus.subtitle import convert as subtitle_convert
from prometheus.subtitle import format as subtitle_format
from prometheus.transcribe import cloud as cloud_mod
from prometheus.transcribe import local as local_mod
from prometheus.transcribe.audio import to_wav
from prometheus.transcribe.transcript import build_transcript_md


def _node_exe() -> str:
    return os.getenv("PROMETHEUS_NODE") or shutil.which("node") or "node"


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


def build_real_impls(data_dir) -> dict:
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
        audio_files = list(work.glob("media.*"))
        if not audio_files:
            raise FileNotFoundError("work/media.* is missing after download")
        wav = to_wav(audio_files[0], work / "audio.wav")
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

    return {
        "resolve": resolve,
        "download": download,
        "transcribe": transcribe,
        "transcript": transcript,
    }
