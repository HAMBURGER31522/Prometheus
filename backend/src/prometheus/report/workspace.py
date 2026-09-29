"""Report workspace assembly and PiRunner wiring (PLAN 8.6), and the stages of 完整精读 (15.4.11)."""

import asyncio
import json
import logging
import os
import shutil
import time
from pathlib import Path

from prometheus import paths
from prometheus.agents import contain, runs
from prometheus.llm import one_shot
from prometheus.report import full, patch, pi_run, viewpoints
from prometheus.report.chunks import load_units
from prometheus.report.full import FIGURES_MD
from prometheus.report.timing import pi_timeout_seconds
from prometheus.tasks import errors
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
    if runs.agent_of(settings["llm"])["id"] != "pi":
        return _standard_on_agent(work, settings, kwargs, node_exe, pi_cli)
    # run contained: writable only in the item's work folder and Pi's own folder (PLAN 15.4.13)
    kwargs["command_prefix"] = [*contain.prefix([work, kwargs["agent_dir"]], temp=kwargs["agent_dir"] / "tmp"),
                                *kwargs["command_prefix"]]
    runner = PiRunner(**kwargs)
    return asyncio.run(runner.run(work))


# VRA's PiRunner request for the standard report (vendor/video-report-agent pi.py), for the Agents it
# cannot start; the staged skill and the checks afterwards are the same (PLAN 15.4.13).
STANDARD_TEMPLATE = "report-template.html"
STANDARD_PROMPT = (
    "读取 transcript.md 和 input.json，按照 video-report skill 生成完整报告，写入 report.html。"
    f"读取 assets/{STANDARD_TEMPLATE} 作为本次唯一模板，"
    "原样保留其中的 {{VIDEO_DESCRIPTION}} 占位符一次，"
    "放在题头之后、正文之前；不要读取、改写或自行生成视频简介，运行时会按原始元数据填充。"
    "本任务 report_mode=standard，是任务自身保存的不可变输入；不根据当前配置或视频内容重新选择模式。"
    "本次只读取 modes/standard.md 这一份模式文件，不读取另一模式。"
    "Profile 只指导内容关系表达，不覆盖所选模式的展开程度。"
    "只使用当前模式的模板、样式与组件，不读取或混入另一模式的视觉资源。"
)


def _standard_on_agent(work: Path, settings: dict, kwargs: dict, node_exe: str, pi_cli: str) -> Path:
    """The 「标准」 report through Codex CLI or Claude Code: VRA's workspace, request and checks."""
    from video_report_agent.report_content import fill_video_description

    pi_run.stage_skill(work)
    (work / "assets").mkdir(exist_ok=True)
    for extra in kwargs.get("extra_files") or []:
        shutil.copy2(extra, work / Path(extra).name)
    report = pi_run.run_task(work, STANDARD_PROMPT + (kwargs.get("extra_prompt") or ""), expect="report.html",
                             llm=_llm(settings), prefix=[node_exe, pi_cli], agent_dir=kwargs["agent_dir"],
                             timeout=kwargs["timeout"])
    fill_video_description(report, work)
    html = report.read_text(encoding="utf-8").lower()
    if "<html" not in html or "</html>" not in html or "<body" not in html:
        raise runs.AgentRunError("report.html is not a complete HTML document")
    return report


# ---- 完整精读 (PLAN 15.4.11): 提取要点, 规划, then the report chapter by chapter ----

def full_depth(settings: dict) -> bool:
    return (settings.get("report") or {}).get("depth", "full") == "full"


def review_on(settings: dict) -> bool:
    return (settings.get("report") or {}).get("review", True) is not False


# The relay can break for minutes (timeouts, 429, connection errors, streams cut); Pi's own retries
# wait 2, 4 and 8 seconds. A call it broke is run again up to ten times, waiting 10 s and doubling up
# to 2 minutes (user 2026-09-29), never past the stage's time (English runs, D-44).
RELAY_RETRIES = 10
RELAY_FIRST_WAIT_S = 10
RELAY_LONGEST_WAIT_S = 120
_RELAY_FAILURES = ("MODEL_TIMEOUT", "MODEL_RATE_LIMITED", "MODEL_BUSY")


def _patient(call, deadline=None):
    for attempt in range(RELAY_RETRIES + 1):
        try:
            return call()
        except (pi_run.PiRunError, one_shot.OneShotError, runs.AgentRunError) as exc:
            if attempt == RELAY_RETRIES or errors.classify("report", str(exc)) not in _RELAY_FAILURES:
                raise
            wait = min(RELAY_FIRST_WAIT_S * 2 ** attempt, RELAY_LONGEST_WAIT_S)
            if deadline is not None and deadline - time.monotonic() < wait + 60:  # room for the retry itself
                raise
            logging.getLogger(__name__).warning("relay broke the call (%s); retry %d/%d in %ds",
                                                str(exc)[-120:], attempt + 1, RELAY_RETRIES, wait)
            time.sleep(wait)


def _llm(settings: dict) -> dict:
    llm = settings["llm"]
    return {"provider": llm["provider"], "model": llm["model"], "thinking": llm.get("thinking") or "medium",
            "api_key": llm.get("api_key") or "", **_agent(settings)}


def _agent(settings: dict) -> dict:
    """The profile's Agent for pi_run.run_task (PLAN 15.4.13); Pi when the settings predate them."""
    agent = runs.agent_of(settings["llm"])
    return {"agent": agent["id"], "access": agent["access"], "base_url": agent["base_url"]}


def model_ask(data_dir, work, settings: dict, node_exe: str, pi_cli: str):
    """ask(prompt) -> reply: one-shot calls (key points, the review) with the configured model."""
    llm = _llm(settings)

    def ask(prompt: str) -> str:
        return _patient(lambda: one_shot.run_one_shot(
            work, prompt=prompt, provider=llm["provider"], model=llm["model"], api_key=llm["api_key"],
            thinking=llm["thinking"], node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir),
            agent=runs.agent_of(llm),
        ))

    return ask


def model_look(data_dir, work, settings: dict, node_exe: str, pi_cli: str):
    """look(prompt, files) -> reply: a one-shot call with images attached (the frame ledger)."""
    llm = _llm(settings)

    def look(prompt: str, files: list) -> str:
        return _patient(lambda: one_shot.run_one_shot(
            work, prompt=prompt, provider=llm["provider"], model=llm["model"], api_key=llm["api_key"],
            thinking=llm["thinking"], node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir),
            files=files, agent=runs.agent_of(llm),
        ))

    return look


def pi_runner(data_dir, settings: dict, node_exe: str, pi_cli: str, *, deadline: float):
    """run_pi(workspace, prompt, expect) for report/full.py: each run gets what is left of its stage's time."""
    llm = _llm(settings)

    def once(workspace, prompt: str, expect: str):
        left = deadline - time.monotonic()
        if left <= 0:
            raise pi_run.PiRunError("Pi generation timed out: the stage's time is used up")
        return pi_run.run_task(workspace, prompt, expect=expect, llm=llm, prefix=[node_exe, pi_cli],
                               agent_dir=paths.pi_config_dir(data_dir), timeout=left)

    def run(workspace, prompt: str, expect: str):
        return _patient(lambda: once(workspace, prompt, expect), deadline)

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


# The writing stage's time is the 2.1 formula times this, by thinking level (PLAN 15.4.11, user
# 2026-09-29: at xhigh Kabbalah ran out of 3x at its sixth chapter); planning gets a third of it.
TIME_TIMES = {"high": 4, "xhigh": 6, "max": 8}


def _times(settings: dict) -> float:
    return TIME_TIMES.get(_llm(settings)["thinking"], 3)


def run_plan_stage(data_dir, item_id: str, row: dict, settings: dict, *, node_exe: str, pi_cli: str,
                   figures: bool) -> None:
    _planned(data_dir, paths.work_dir(data_dir, item_id), row, settings, node_exe, pi_cli, figures=figures,
             seconds=max(1.0, _times(settings) / 3) * pi_timeout_seconds(row.get("duration_s") or 0.0))


def run_full_report_stage(data_dir, item_id: str, row: dict, settings: dict, *, node_exe: str, pi_cli: str,
                          figures: bool, progress):
    """Chapters, checks, review, assembly: work/report.html for finalize (15.4.11)."""
    work = paths.work_dir(data_dir, item_id)
    units, ledger, plan, problems, ask, run_pi = _planned(
        data_dir, work, row, settings, node_exe, pi_cli, figures=figures,
        seconds=_times(settings) * pi_timeout_seconds(row.get("duration_s") or 0.0))
    proxy = settings["network"].get("proxy", "")
    chapters = full.write_chapters(work, plan, ledger, units, run_pi, ask, figures=figures,
                                   review=review_on(settings), progress=progress,
                                   look=model_look(data_dir, work, settings, node_exe, pi_cli),
                                   verify_links=lambda url: viewpoints.open_page(url, proxy=proxy))
    full.finish(work, plan, problems, ledger, chapters, build_input_json(row))
    return work / "report.html"


def run_patch_stage(data_dir, item_id: str, row: dict, settings: dict, *, node_exe: str, pi_cli: str, progress):
    """A finished 完整 report patched by the newer rules (PLAN 15.4.11a-5): the published 精读, the
    kept ledger and the old skips; nothing is extracted or planned again."""
    work = paths.work_dir(data_dir, item_id)
    ledger = json.loads((work / "keypoints.json").read_text(encoding="utf-8"))
    units = load_units(work / "canonical-transcript.jsonl")
    published = paths.library_folder(data_dir, row["library_path"]) / paths.LIBRARY_FILES["html"]
    coverage = work / "coverage.json"
    skipped = (json.loads(coverage.read_text(encoding="utf-8")).get("skipped") or []) if coverage.is_file() else []
    proxy = settings["network"].get("proxy", "")
    run_pi = pi_runner(data_dir, settings, node_exe, pi_cli,
                       deadline=time.monotonic() + _times(settings) * pi_timeout_seconds(row.get("duration_s") or 0.0))
    patch.patch_report(work, published.read_text(encoding="utf-8"), ledger, units, run_pi, skipped=skipped,
                       verify_links=lambda url: viewpoints.open_page(url, proxy=proxy), progress=progress)
