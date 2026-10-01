"""Real pipeline stage runners (PLAN 8.3): resolve, download, wav."""

import json
from pathlib import Path
from typing import ClassVar

import pytest
from prometheus.ingest import download as download_mod
from prometheus.ingest import resolve as resolve_mod
from prometheus.transcribe.audio import build_wav_cmd
from yt_dlp.utils import DownloadError

ROW = {
    "id": "a" * 32, "platform": "bilibili", "video_id": "BV1xJYT6EEYc",
    "source_url": "https://www.bilibili.com/video/BV1xJYT6EEYc/",
}
SETTINGS = {"network": {"proxy": "", "youtube_cookies_file": ""}}
INFO = {"title": "财政再平衡", "uploader": "示例UP主", "duration": 61.5}


class FakeYDL:
    last_opts: ClassVar[dict | None] = None
    calls: ClassVar[list] = []
    prepared: ClassVar[str | None] = None

    def __init__(self, opts):
        FakeYDL.last_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        FakeYDL.calls.append((url, download))
        return dict(INFO)

    def prepare_filename(self, info):
        return FakeYDL.prepared


def test_resolve_stage_writes_source_info_and_returns_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(resolve_mod, "YoutubeDL", FakeYDL)
    work = tmp_path / "work"
    work.mkdir()
    updates = resolve_mod.resolve_stage(work, ROW, SETTINGS, "node.exe")
    source_info = json.loads((work / "source.info.json").read_text(encoding="utf-8"))
    assert source_info["title"] == "财政再平衡"
    assert updates["source_title"] == "财政再平衡"
    assert updates["uploader"] == "示例UP主"
    assert updates["duration_s"] == 61.5
    assert FakeYDL.last_opts["writeinfojson"] is True
    assert FakeYDL.calls[-1] == (ROW["source_url"], False)


def test_download_stage_returns_media_path(tmp_path, monkeypatch):
    monkeypatch.setattr(download_mod, "YoutubeDL", FakeYDL)
    work = tmp_path / "work"
    work.mkdir()
    FakeYDL.prepared = str(work / "media.m4a")
    (work / "media.m4a").write_bytes(b"RIFF")
    path = download_mod.download_stage(work, ROW, SETTINGS, "node.exe", media="audio")
    assert path == Path(work / "media.m4a")
    assert "media.%(ext)s" in FakeYDL.last_opts["outtmpl"]
    assert FakeYDL.last_opts["format"] == "bestaudio"
    assert FakeYDL.calls[-1][1] is True


def test_download_error_maps_to_cookies_required(tmp_path, monkeypatch):
    class FailYDL(FakeYDL):
        def extract_info(self, url, download=False):
            raise DownloadError("ERROR: Sign in to confirm you're not a bot")

    monkeypatch.setattr(download_mod, "YoutubeDL", FailYDL)
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(download_mod.IngestError) as error:
        download_mod.download_stage(work, ROW, SETTINGS, "node.exe", media="audio")
    assert error.value.code == "YOUTUBE_COOKIES_REQUIRED"


def test_wav_command_matches_plan():
    command = build_wav_cmd(Path("media.m4a"), Path("audio.wav"))
    assert command[:2] == ["ffmpeg", "-y"]
    assert str(Path("media.m4a")) in command
    assert "-vn" in command and "-ac" in command and "1" in command
    assert "-ar" in command and "16000" in command
    assert "pcm_s16le" in command
    assert str(Path("audio.wav")) in command
