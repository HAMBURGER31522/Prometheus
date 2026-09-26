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
