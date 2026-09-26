"""ffmpeg wav conversion for ASR (PLAN 8.3 transcribe stage)."""

from pathlib import Path


def build_wav_cmd(audio_path: Path, wav_path: Path) -> list:
    raise NotImplementedError
