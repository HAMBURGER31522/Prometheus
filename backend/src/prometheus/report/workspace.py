"""Report workspace assembly and PiRunner wiring (PLAN 8.6), and the stages of 完整精读 (15.4.11)."""

import asyncio
import json
import os
import time
from pathlib import Path

from prometheus import paths
from prometheus.llm import one_shot
from prometheus.report import full, pi_run
from prometheus.report.chunks import load_units
from prometheus.report.full import FIGURES_MD
from prometheus.report.timing import pi_timeout_seconds
from video_report_agent.pi import PiRunner

PLATFORM_LABELS = {"bilibili": "Bilibili", "youtube": "YouTube"}

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
    # 「标准」精读: the VRA run as it was. 「完整」 goes chapter by chapter instead (run_full_report_stage).
    extra_files = [FIGURES_MD] if figures_on else []
    return {
        "provider": llm["provider"],
        "model": llm["model"],
        "api_key": llm.get("api_key") or None,
        "thinking": llm.get("thinking") or "low",
        "timeout": pi_timeout_seconds(row.get("duration_s") or 0.0),
        "tools": "read,write,edit,powershell",
        "extra_prompt": WINDOWS_PROMPT + (FIGURES_PROMPT if figures_on else ""),
        "extra_files": extra_files or None,
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


# ---- 完整精读 (PLAN 15.4.11): 提取要点, 规划, then the report chapter by chapter ----

def full_depth(settings: dict) -> bool:
    return (settings.get("report") or {}).get("depth", "full") == "full"


def review_on(settings: dict) -> bool:
    return (settings.get("report") or {}).get("review", True) is not False


def _llm(settings: dict) -> dict:
    llm = settings["llm"]
    return {"provider": llm["provider"], "model": llm["model"], "thinking": llm.get("thinking") or "medium",
            "api_key": llm.get("api_key") or ""}


def model_ask(data_dir, work, settings: dict, node_exe: str, pi_cli: str):
    """ask(prompt) -> reply: one-shot calls (key points, the review) with the configured model."""
    llm = _llm(settings)

    def ask(prompt: str) -> str:
        return one_shot.run_one_shot(
            work, prompt=prompt, provider=llm["provider"], model=llm["model"], api_key=llm["api_key"],
            thinking=llm["thinking"], node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir),
        )

    return ask


def model_look(data_dir, work, settings: dict, node_exe: str, pi_cli: str):
    """look(prompt, files) -> reply: a one-shot call with images attached (the frame ledger)."""
    llm = _llm(settings)

    def look(prompt: str, files: list) -> str:
        return one_shot.run_one_shot(
            work, prompt=prompt, provider=llm["provider"], model=llm["model"], api_key=llm["api_key"],
            thinking=llm["thinking"], node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir),
            files=files,
        )

    return look


def pi_runner(data_dir, settings: dict, node_exe: str, pi_cli: str, *, deadline: float):
    """run_pi(workspace, prompt, expect) for report/full.py: each run gets what is left of its stage's time."""
    llm = _llm(settings)

    def run(workspace, prompt: str, expect: str):
        left = deadline - time.monotonic()
        if left <= 0:
            raise pi_run.PiRunError("Pi generation timed out: the stage's time is used up")
        return pi_run.run_task(workspace, prompt, expect=expect, llm=llm, prefix=[node_exe, pi_cli],
                               agent_dir=paths.pi_config_dir(data_dir), timeout=left)

    return run


def run_keypoints_stage(data_dir, item_id: str, settings: dict, *, node_exe: str, pi_cli: str) -> None:
    work = paths.work_dir(data_dir, item_id)
    units = load_units(work / "canonical-transcript.jsonl")
    full.run_keypoints(work, units, model_ask(data_dir, work, settings, node_exe, pi_cli))


def _planned(data_dir, work, row: dict, settings: dict, node_exe: str, pi_cli: str, *, figures: bool, seconds: float):
    """The ledger and the plan, both kept from their own stages unless their inputs changed."""
    ask = model_ask(data_dir, work, settings, node_exe, pi_cli)
    units = load_units(work / "canonical-transcript.jsonl")
    ledger = full.run_keypoints(work, units, ask)
    run_pi = pi_runner(data_dir, settings, node_exe, pi_cli, deadline=time.monotonic() + seconds)
    plan, problems = full.run_plan(work, ledger, run_pi, figures=figures, input_json=build_input_json(row))
    return units, ledger, plan, problems, ask, run_pi


def run_plan_stage(data_dir, item_id: str, row: dict, settings: dict, *, node_exe: str, pi_cli: str,
                   figures: bool) -> None:
    _planned(data_dir, paths.work_dir(data_dir, item_id), row, settings, node_exe, pi_cli, figures=figures,
             seconds=pi_timeout_seconds(row.get("duration_s") or 0.0))


def run_full_report_stage(data_dir, item_id: str, row: dict, settings: dict, *, node_exe: str, pi_cli: str,
                          figures: bool, progress):
    """Chapters, checks, review, assembly: work/report.html for finalize. 3x the time (15.4.11)."""
    work = paths.work_dir(data_dir, item_id)
    units, ledger, plan, problems, ask, run_pi = _planned(
        data_dir, work, row, settings, node_exe, pi_cli, figures=figures,
        seconds=3 * pi_timeout_seconds(row.get("duration_s") or 0.0))
    chapters = full.write_chapters(work, plan, ledger, units, run_pi, ask, figures=figures,
                                   review=review_on(settings), progress=progress,
                                   look=model_look(data_dir, work, settings, node_exe, pi_cli))
    full.finish(work, plan, problems, ledger, chapters, build_input_json(row))
    return work / "report.html"
