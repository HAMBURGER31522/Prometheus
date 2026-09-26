"""Data directory layout - the only place that composes these paths (PLAN 7)."""

from pathlib import Path


def init_data_dir(data_dir: Path) -> Path:
    return data_dir


def db_path(data_dir: Path) -> Path:
    return data_dir / "prometheus.db"


def settings_file(data_dir: Path) -> Path:
    return data_dir / "config" / "settings.json"


def pi_config_dir(data_dir: Path) -> Path:
    return data_dir / "config" / "pi"


def models_json(data_dir: Path) -> Path:
    return pi_config_dir(data_dir) / "models.json"


def cuda_dir(data_dir: Path) -> Path:
    return data_dir / "runtime" / "cuda"


def models_dir(data_dir: Path) -> Path:
    return data_dir / "models"


def logs_dir(data_dir: Path) -> Path:
    return data_dir / "logs"


def backend_port_file(data_dir: Path) -> Path:
    return logs_dir(data_dir) / "backend.port"


def items_root(data_dir: Path) -> Path:
    return data_dir / "items"


def item_dir(data_dir: Path, item_id: str) -> Path:
    return items_root(data_dir) / item_id


def report_file(data_dir: Path, item_id: str) -> Path:
    return item_dir(data_dir, item_id) / "report" / "report.html"


def mindmap_file(data_dir: Path, item_id: str) -> Path:
    return item_dir(data_dir, item_id) / "mindmap" / "mindmap.md"


def segments_file(data_dir: Path, item_id: str) -> Path:
    return item_dir(data_dir, item_id) / "subtitle" / "segments.json"


def srt_file(data_dir: Path, item_id: str) -> Path:
    return item_dir(data_dir, item_id) / "subtitle" / "subtitle.srt"


def work_dir(data_dir: Path, item_id: str) -> Path:
    return item_dir(data_dir, item_id) / "work"


def new_item_id() -> str:
    return "0" * 32
