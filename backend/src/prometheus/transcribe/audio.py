"""ffmpeg wav conversion for ASR (PLAN 8.3 transcribe stage)."""

import subprocess
from pathlib import Path


class AudioError(RuntimeError):
    code = "ENVIRONMENT_FAILURE"


def build_wav_cmd(audio_path: Path, wav_path: Path) -> list:
    return [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(wav_path),
    ]


def to_wav(audio_path: Path, wav_path: Path) -> Path:
    result = subprocess.run(build_wav_cmd(audio_path, wav_path), capture_output=True, check=False)
    if result.returncode != 0:
        raise AudioError(
            "ffmpeg 转 16kHz 单声道 wav 失败，请确认已安装 FFmpeg。"
        )
    return wav_path


def build_mp3_cmd(audio_path: Path, mp3_path: Path) -> list:
    """必剪's input (PLAN 15.4.4): 16kHz mono 48kbps mp3, a fraction of the wav's size to upload."""
    return [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
        str(mp3_path),
    ]


def to_mp3(audio_path: Path, mp3_path: Path) -> Path:
    result = subprocess.run(build_mp3_cmd(audio_path, mp3_path), capture_output=True, check=False)
    if result.returncode != 0:
        raise AudioError("ffmpeg 转 mp3 失败，请确认已安装 FFmpeg。")
    return mp3_path
