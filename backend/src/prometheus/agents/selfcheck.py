"""The self-check a new copy of an Agent must pass before it replaces the old one (PLAN 15.4.13).

It runs the copy against the local fake model API (agents/fake_api.py), never online: a one-shot call
that must answer, and a workspace task that must write its file, both contained as real runs are.
For Pi also VRA's own run, its PiRunner, which is written for a fixed Pi event format (user
2026-09-29: Pi may move ahead of VRA only if this passes).
"""

import asyncio
import json
from pathlib import Path

from prometheus.agents import contain, fake_api, runs
from prometheus.agents.versions import UpdateError
from prometheus.llm import one_shot
from prometheus.report import pi_run

KEY = "sk-prometheus-selfcheck"
MODEL = "selfcheck-model"
NAMES = {"pi": "Pi", "codex": "Codex CLI", "claude": "Claude Code"}
PI_CLI = Path("pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js")


def run(tools_root, agent_id: str, *, node_exe, scratch) -> None:
    """Raise UpdateError when the copy under `tools_root` cannot do what the app asks of it."""
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        with fake_api.FakeModelApi() as api:
            if agent_id == "pi":
                _pi(Path(tools_root) / PI_CLI, Path(node_exe), api, scratch)
            else:
                _agent(Path(tools_root), agent_id, api, scratch)
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError(f"{NAMES[agent_id]} 自检没通过，保留原来的版本：{exc}") from exc


def _expect_answer(answer: str, what: str) -> None:
    if answer.strip() != fake_api.ANSWER:
        raise UpdateError(f"自检：{what}没有得到回答（{answer[:80]!r}）")


def _workspace(scratch: Path, name: str) -> Path:
    folder = scratch / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _agent(tools_root: Path, agent_id: str, api, scratch: Path) -> None:
    agent = {"id": agent_id, "access": "key", "base_url": api.url if agent_id == "claude" else f"{api.url}/v1"}
    config = scratch / "config"
    answer = runs.one_shot(agent, prompt="回复两个字：可用", model=MODEL, api_key=KEY, thinking="medium",
                           work_dir=_workspace(scratch, "one-shot"), config_root=config, tools_root=tools_root)
    _expect_answer(answer, "一次性调用")
    workspace = _workspace(scratch, "task")
    runs.task(agent, workspace, f"WRITE:{workspace / 'ch-01.html'}", expect="ch-01.html", model=MODEL, api_key=KEY,
              thinking="medium", config_root=config, tools_root=tools_root, timeout=300)


def _pi(pi_cli: Path, node_exe: Path, api, scratch: Path) -> None:
    from video_report_agent.pi import PiRunner

    agent_dir = scratch / "config" / "pi"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "models.json").write_text(json.dumps({"providers": {"custom": {
        "baseUrl": api.url, "api": "anthropic-messages", "apiKey": KEY,
        "models": [{"id": MODEL, "name": MODEL, "reasoning": False, "input": ["text"], "contextWindow": 200000,
                    "maxTokens": 8192}]}}}), encoding="utf-8")
    answer = one_shot.run_one_shot(_workspace(scratch, "one-shot"), prompt="回复两个字：可用", provider="custom",
                                   model=MODEL, api_key=KEY, thinking="low", node_exe=str(node_exe),
                                   pi_cli=str(pi_cli), agent_dir=agent_dir)
    _expect_answer(answer, "一次性调用")
    workspace = _workspace(scratch, "task")
    pi_run.run_task(workspace, f"WRITE:{workspace / 'ch-01.html'}", expect="ch-01.html",
                    llm={"provider": "custom", "model": MODEL, "api_key": KEY}, prefix=[str(node_exe), str(pi_cli)],
                    agent_dir=agent_dir, timeout=300)
    report = _workspace(scratch, "standard")  # VRA's run, as the 「标准」 report calls it (report/workspace.py)
    (report / "transcript.md").write_text("# 自检\n\n[00:00] 自检。\n", encoding="utf-8")
    (report / "input.json").write_text(json.dumps({"title": "自检"}, ensure_ascii=False), encoding="utf-8")
    runner = PiRunner(provider="custom", model=MODEL, api_key=KEY, thinking="low", timeout=300,
                      tools="read,write,edit,powershell", extra_prompt=f"\nHTML:{report / 'report.html'}",
                      command_prefix=[*contain.prefix([report, agent_dir], temp=agent_dir / "tmp"), str(node_exe),
                                      str(pi_cli)], agent_dir=agent_dir)
    asyncio.run(runner.run(report))
