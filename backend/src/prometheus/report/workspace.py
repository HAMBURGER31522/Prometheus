"""Report workspace assembly and PiRunner wiring (PLAN 8.6)."""

import asyncio
import json
import os
from pathlib import Path

from video_report_agent.pi import PiRunner

from prometheus import paths
from prometheus.report.timing import pi_timeout_seconds

PLATFORM_LABELS = {"bilibili": "Bilibili", "youtube": "YouTube"}
FIGURES_MD = Path(__file__).parent / "overlays" / "figures.md"

WINDOWS_PROMPT = (
    "本机为 Windows，命令工具是 PowerShell；运行 Python 用"
    " `& $env:VIDEO_REPORT_PYTHON script.py`；脚本和中间文件只写在当前工作区。"
    "报告一律用简体中文撰写，专有名词和术语可以保留原文。"
)
FIGURES_PROMPT = "另读 figures.md，按其中规则使用 frames/ 里的候选帧。"


def build_input_json(row: dict) -> dict:
    label = PLATFORM_LABELS[row["platform"]]
    title = row.get("source_title") or row["video_id"]
    uploader = row.get("uploader") or ""
    return {
        "url": row["source_url"],
        "video_id": row["video_id"].split("?")[0],
        "report_mode": "standard",
        "transcript_mode": "asr-only",
        "ocr_mode": "off",
        "ocr_roi": None,
        "subtitle_file": None,
        "platform": label,
        "title": title,
        "uploader": uploader,
        "attribution": f"{label}；{uploader}；《{title}》；{row['source_url']}",
    }


def build_runner_kwargs(row: dict, settings: dict, node_exe: str, pi_cli: str, *,
                        figures: bool, model_supports_images: bool) -> dict:
    llm = settings["llm"]
    figures_on = figures and model_supports_images
    return {
        "provider": llm["provider"],
        "model": llm["model"],
        "api_key": llm.get("api_key") or None,
        "thinking": llm.get("thinking") or "low",
        "timeout": pi_timeout_seconds(row.get("duration_s") or 0.0),
        "tools": "read,write,edit,powershell",
        "extra_prompt": WINDOWS_PROMPT + (FIGURES_PROMPT if figures_on else ""),
        "extra_files": [FIGURES_MD] if figures_on else None,
        "command_prefix": [node_exe, pi_cli],
    }


def run_report_stage(data_dir, item_id: str, row: dict, settings: dict, *,
                     node_exe: str, pi_cli: str, figures: bool = False,
                     model_supports_images: bool = False) -> Path:
    work = paths.work_dir(data_dir, item_id)
    work.mkdir(parents=True, exist_ok=True)
    (work / "input.json").write_text(
        json.dumps(build_input_json(row), ensure_ascii=False, indent=2), encoding="utf-8",
    )
    os.environ.setdefault("PYTHONUTF8", "1")
    kwargs = build_runner_kwargs(
        row, settings, node_exe, pi_cli,
        figures=figures, model_supports_images=model_supports_images,
    )
    kwargs["agent_dir"] = paths.pi_config_dir(data_dir)
    runner = PiRunner(**kwargs)
    return asyncio.run(runner.run(work))
