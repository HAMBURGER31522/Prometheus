"""Live tests (PLAN 12/M3): real videos through the real stage runners.

Credentials come from the environment; missing values skip with explicit reasons:
- PROMETHEUS_TEST_BV: public bilibili video, 5-10 minutes (recorded in docs/acceptance.md)
- PROMETHEUS_TEST_YT_COOKIES: YouTube cookies.txt path
- PROMETHEUS_TEST_PROXY: optional proxy URL, e.g. http://127.0.0.1:7897
"""

import hashlib
import json
import os
from pathlib import Path

import pytest
from prometheus import paths
from prometheus.ingest import download as download_mod
from prometheus.ingest import resolve as resolve_mod
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
requires_cookies = pytest.mark.skipif(
    not YT_COOKIES, reason="PROMETHEUS_TEST_YT_COOKIES 未设置",
)


def _pipeline(source: str, platform: str, video_id: str):
    data_dir = paths.init_data_dir(DATA_DIR)
    # One item folder per video (production semantics): yt-dlp skips existing
    # media, so sharing an id across videos would transcribe stale audio.
    item_id = hashlib.sha1(f"{platform}:{video_id}".encode()).hexdigest()[:32]
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
def test_bilibili_bcut_transcribe_to_transcript():
    """必剪 needs no key (PLAN 15.4.4): a real upload to Bilibili's free ASR."""
    from prometheus.tasks.stages import _transcribe_bcut

    _data_dir, _item_id, work, row, wav = _pipeline(
        f"https://www.bilibili.com/video/{BV}/", "bilibili", BV,
    )
    asr_path = _transcribe_bcut(work, wav)
    assert json.loads(asr_path.read_text(encoding="utf-8"))["engine"] == "bcut"
    _transcript_assertions(work, asr_path, row)


@requires_bv
def test_bilibili_local_transcribe_to_transcript():
    data_dir, item_id, work, row, wav = _pipeline(
        f"https://www.bilibili.com/video/{BV}/", "bilibili", BV,
    )
    components.install_components(data_dir, proxy=PROXY)
    asr_path = local_mod.transcribe_local(data_dir, item_id, wav)
    # Mandarin goes to FunASR on the CPU (D-35, D-39).
    assert json.loads(asr_path.read_text(encoding="utf-8"))["engine"] == "funasr-onnx"
    _transcript_assertions(work, asr_path, row)


@requires_cookies
def test_youtube_cookies_chain_local_transcribe():
    """Cookie gate and the English path: anything but Mandarin stays on whisper (D-35)."""
    data_dir, item_id, work, row, wav = _pipeline(YT_URL, "youtube", "jNQXAC9IVRw")
    assert row["platform"] == "youtube"
    components.install_components(data_dir, proxy=PROXY)
    asr_path = local_mod.transcribe_local(data_dir, item_id, wav)
    assert json.loads(asr_path.read_text(encoding="utf-8"))["engine"] == "faster-whisper"
    _transcript_assertions(work, asr_path, row)
