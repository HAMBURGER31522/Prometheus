"""yt-dlp metadata resolution (PLAN 8.3 resolve stage)."""

import json
from pathlib import Path

from prometheus.ingest.download import build_ytdlp_opts
from yt_dlp import YoutubeDL


def resolve_stage(work_dir: Path, row: dict, settings: dict, node_exe: str) -> dict:
    opts = build_ytdlp_opts(row["platform"], settings, node_exe=node_exe)
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(row["source_url"], download=False)
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "source.info.json").write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8",
    )
    return {
        "source_title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "duration_s": info.get("duration"),
    }
