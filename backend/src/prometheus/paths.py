"""Data directory layout - the only place that composes these paths (PLAN 15.4.1).

The data directory *is* the readable library: category folders with one folder
per video. Everything the program needs internally lives in a hidden
``.prometheus`` folder next to them.
"""

import secrets
import sys
from pathlib import Path

INTERNAL = ".prometheus"

# Files of a published item, keyed by role (PLAN 15.4.1).
LIBRARY_FILES = {
    "html": "精读.html", "md": "精读.md", "mindmap": "思维导图.md",
    "srt": "字幕.srt", "txt": "字幕.txt", "url": "来源.url",
}


def _hide(path: Path) -> None:
    if sys.platform == "win32":
        import ctypes

        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attributes != -1:
            ctypes.windll.kernel32.SetFileAttributesW(str(path), attributes | 0x2)


def internal_dir(data_dir: Path) -> Path:
    return Path(data_dir) / INTERNAL


def init_data_dir(data_dir: Path) -> Path:
    data_dir = Path(data_dir)
    internal = internal_dir(data_dir)
    for relative in ("config/pi", "runtime/cuda", "models", "logs", "cache"):
        (internal / relative).mkdir(parents=True, exist_ok=True)
    _hide(internal)
    return data_dir


def db_path(data_dir: Path) -> Path:
    return internal_dir(data_dir) / "prometheus.db"


def settings_file(data_dir: Path) -> Path:
    return internal_dir(data_dir) / "config" / "settings.json"


def pi_config_dir(data_dir: Path) -> Path:
    return internal_dir(data_dir) / "config" / "pi"


def models_json(data_dir: Path) -> Path:
    return pi_config_dir(data_dir) / "models.json"


def cuda_dir(data_dir: Path) -> Path:
    return internal_dir(data_dir) / "runtime" / "cuda"


def models_dir(data_dir: Path) -> Path:
    return internal_dir(data_dir) / "models"


def funasr_dir(data_dir: Path) -> Path:
    """FunASR ONNX models, one folder per ModelScope repo (PLAN 15.4.4)."""
    return models_dir(data_dir) / "funasr"


def logs_dir(data_dir: Path) -> Path:
    return internal_dir(data_dir) / "logs"


def backend_port_file(data_dir: Path) -> Path:
    return logs_dir(data_dir) / "backend.port"


def cache_dir(data_dir: Path, item_id: str) -> Path:
    """Per-item working and regeneration files (asr.json, transcript.md, ...)."""
    return internal_dir(data_dir) / "cache" / item_id


def work_dir(data_dir: Path, item_id: str) -> Path:
    return cache_dir(data_dir, item_id)


def segments_file(data_dir: Path, item_id: str) -> Path:
    return cache_dir(data_dir, item_id) / "segments.json"


def raw_segments_file(data_dir: Path, item_id: str) -> Path:
    """The transcript before subtitle correction (PLAN 15.4.6); kept for 「原始识别」."""
    return cache_dir(data_dir, item_id) / "segments.raw.json"


def fine_segments_file(data_dir: Path, item_id: str) -> Path:
    """The transcription's own fragments, before they became paragraphs (PLAN 15.4.10)."""
    return cache_dir(data_dir, item_id) / "segments.fine.json"


def out_dir(data_dir: Path, item_id: str) -> Path:
    """Finished artifacts waiting to be published into the library."""
    return cache_dir(data_dir, item_id) / "out"


def report_file(data_dir: Path, item_id: str) -> Path:
    return out_dir(data_dir, item_id) / "report.html"


def mindmap_json(data_dir: Path, item_id: str) -> Path:
    """The knowledge tree the app renders (kept in the cache for regeneration)."""
    return cache_dir(data_dir, item_id) / "mindmap.json"


def mindmap_file(data_dir: Path, item_id: str) -> Path:
    return out_dir(data_dir, item_id) / "mindmap.md"


def srt_file(data_dir: Path, item_id: str) -> Path:
    return out_dir(data_dir, item_id) / "subtitle.srt"


def library_folder(data_dir: Path, library_path: str) -> Path:
    return Path(data_dir) / library_path


def new_item_id() -> str:
    return secrets.token_hex(16)
