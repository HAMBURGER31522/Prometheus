"""Live tests (PLAN 12/M3): real videos through the real stage runners.

Credentials come from the environment; missing values skip with explicit reasons:
- PROMETHEUS_TEST_BV: public bilibili video, 5-10 minutes (recorded in docs/acceptance.md)
- DASHSCOPE_API_KEY: cloud transcription (paraformer)
- PROMETHEUS_TEST_YT_COOKIES: YouTube cookies.txt path
- PROMETHEUS_TEST_PROXY: optional proxy URL, e.g. http://127.0.0.1:7897
"""

import json
import os
from pathlib import Path

import pytest
from prometheus import paths
from prometheus.ingest import download as download_mod
from prometheus.ingest import resolve as resolve_mod
from prometheus.transcribe import cloud as cloud_mod
from prometheus.transcribe import components
from prometheus.transcribe import local as local_mod
from prometheus.transcribe.audio import to_wav
from prometheus.transcribe.transcript import build_transcript_md

pytestmark = pytest.mark.live

BV = os.getenv("PROMETHEUS_TEST_BV", "")
PROXY = os.getenv("PROMETHEUS_TEST_PROXY", "")
YT_COOKIES = os.getenv("PROMETHEUS_TEST_YT_COOKIES", "")
YT_URL = os.getenv("PROMETHEUS_TEST_YT_URL", "https://www.youtube.com/watch?v=jNQXAC9IVRw")
NODE = os.getenv("PROMETHEUS_NODE") or "node"
# Stable data dir (gitignored): model and CUDA components survive across runs.
DATA_DIR = Path(
    os.getenv("PROMETHEUS_TEST_DATA_DIR", "acceptance-output/live-data")
).resolve()

requires_bv = pytest.mark.skipif(not BV, reason="PROMETHEUS_TEST_BV 未设置")
requires_dashscope = pytest.mark.skipif(
    not os.getenv("DASHSCOPE_API_KEY"), reason="DASHSCOPE_API_KEY 未设置",
)
requires_cookies = pytest.mark.skipif(
    not YT_COOKIES, reason="PROMETHEUS_TEST_YT_COOKIES 未设置",
)


def _pipeline(source: str, platform: str, video_id: str):
    data_dir = paths.init_data_dir(DATA_DIR)
    item_id = "b" * 32
    work = paths.work_dir(data_dir, item_id)
    work.mkdir(parents=True, exist_ok=True)
    row = {
        "id": item_id, "platform": platform, "video_id": video_id, "source_url": source,
        "figures": 0,
    }
    settings = {"network": {"proxy": PROXY, "youtube_cookies_file": YT_COOKIES}}
    row.update(resolve_mod.resolve_stage(work, row, settings, NODE))
    audio = download_mod.download_stage(work, row, settings, NODE, media="audio")
    wav = to_wav(audio, work / "audio.wav")
    return data_dir, item_id, work, row, wav


def _transcript_assertions(work: Path, asr_path: Path, row: dict) -> None:
    payload = json.loads(asr_path.read_text(encoding="utf-8"))
    assert payload["segments"], "asr.json has no segments"
    metadata = {
        "title": row["source_title"],
        "uploader": row["uploader"] or "",
        "attribution": f"{row['uploader'] or ''} · {row['source_title']}".strip(" ·"),
        "url": row["source_url"],
        "video_id": row["video_id"],
        "platform": row["platform"],
        "duration_s": row["duration_s"] or 0.0,
    }
    transcript = build_transcript_md(work, asr_path, metadata)
    text = transcript.read_text(encoding="utf-8")
    assert text.startswith(f"# {row['source_title']}")
    assert "[unit-" in text


@requires_bv
@requires_dashscope
def test_bilibili_cloud_transcribe_to_transcript():
    data_dir, item_id, work, row, wav = _pipeline(
        f"https://www.bilibili.com/video/{BV}/", "bilibili", BV,
    )
    asr_path = cloud_mod.transcribe_cloud(data_dir, item_id, wav)
    _transcript_assertions(work, asr_path, row)


@requires_bv
def test_bilibili_local_transcribe_to_transcript():
    data_dir, item_id, work, row, wav = _pipeline(
        f"https://www.bilibili.com/video/{BV}/", "bilibili", BV,
    )
    components.install_components(data_dir, proxy=PROXY)
    asr_path = local_mod.transcribe_local(data_dir, item_id, wav)
    _transcript_assertions(work, asr_path, row)


@requires_cookies
@requires_dashscope
def test_youtube_full_chain_with_cookies():
    data_dir, item_id, work, row, wav = _pipeline(YT_URL, "youtube", "jNQXAC9IVRw")
    assert row["platform"] == "youtube"
    asr_path = cloud_mod.transcribe_cloud(data_dir, item_id, wav)
    _transcript_assertions(work, asr_path, row)
