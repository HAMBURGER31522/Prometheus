"""Real pipeline stage runners (PLAN 8.3): resolve, download, wav, cloud ASR."""

import json
from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError

from prometheus.ingest import download as download_mod
from prometheus.ingest import resolve as resolve_mod
from prometheus.transcribe import cloud as cloud_mod
from prometheus.transcribe.audio import build_wav_cmd

ROW = {
    "id": "a" * 32, "platform": "bilibili", "video_id": "BV1xJYT6EEYc",
    "source_url": "https://www.bilibili.com/video/BV1xJYT6EEYc/",
}
SETTINGS = {"network": {"proxy": "", "youtube_cookies_file": ""}}
INFO = {"title": "财政再平衡", "uploader": "示例UP主", "duration": 61.5}


class FakeYDL:
    last_opts = None
    calls = []
    prepared = None

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


def test_cloud_transcribe_uses_paraformer(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setattr(
        cloud_mod, "store",
        type("S", (), {
            "load": staticmethod(lambda data_dir: {
                "asr": {"dashscope_api_key": "sk-dash", "cloud_model": "paraformer-v2"},
            }),
        }),
    )
    config = {
        "asr_backend": "paraformer", "asr_model": "paraformer-v2",
        "asr_language": "zh", "asr_base_url": "https://dashscope.aliyuncs.com/api/v1",
        "asr_parameters": {"channel_id": [0]},
    }
    seen = {}

    def fake_config(**kwargs):
        seen["config_kwargs"] = kwargs
        return config

    class FakeRun:
        def to_dict(self):
            return {"backend": "paraformer", "segments": [
                {"ordinal": 0, "start_ms": 0, "end_ms": 1500, "text": "你好"},
            ]}

    def fake_transcribe(audio_path, **kwargs):
        seen["transcribe_kwargs"] = kwargs
        return FakeRun()

    monkeypatch.setattr(cloud_mod, "resolve_media_config", fake_config)
    monkeypatch.setattr(cloud_mod, "vendor_transcribe_audio", fake_transcribe)

    work = tmp_path / "work"
    work.mkdir()
    out = cloud_mod.transcribe_cloud(tmp_path, "a" * 32, work / "audio.wav")

    assert seen["config_kwargs"]["asr_backend"] == "paraformer"
    kwargs = seen["transcribe_kwargs"]
    assert kwargs["backend"] == "paraformer"
    assert kwargs["model"] == "paraformer-v2"
    assert kwargs["language"] == "zh"
    assert kwargs["base_url"] == config["asr_base_url"]
    assert kwargs["parameters"] == config["asr_parameters"]
    import os

    assert os.environ["DASHSCOPE_API_KEY"] == "sk-dash"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["segments"][0]["text"] == "你好"


def test_cloud_requires_dashscope_key(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cloud_mod, "store",
        type("S", (), {
            "load": staticmethod(lambda data_dir: {
                "asr": {"dashscope_api_key": "", "cloud_model": "paraformer-v2"},
            }),
        }),
    )
    with pytest.raises(cloud_mod.CloudAsrError) as error:
        cloud_mod.transcribe_cloud(tmp_path, "a" * 32, tmp_path / "audio.wav")
    assert error.value.code == "EXTERNAL_API_FAILURE"
