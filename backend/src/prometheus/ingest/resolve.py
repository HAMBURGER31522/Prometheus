"""yt-dlp metadata resolution (PLAN 8.3 resolve stage)."""

import json
from pathlib import Path

from yt_dlp import YoutubeDL

from prometheus.ingest.download import build_ytdlp_opts


def resolve_stage(work_dir: Path, row: dict, settings: dict, node_exe: str) -> dict:
    raise NotImplementedError
