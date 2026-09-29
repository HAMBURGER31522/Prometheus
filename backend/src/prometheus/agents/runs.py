"""Running a model call through Codex CLI or Claude Code (PLAN 15.4.13): a one-shot text call, or a
task in a workspace that must leave a named file behind. Pi keeps its own paths (llm/one_shot.py,
report/pi_run.py); they hand over here when the profile names another Agent.

A task gets what a Pi run gets, as text in its prompt: the same workspace-only system prompt and the
skill's SKILL.md (Pi loads it with --skill; the other Agents' own skill loading stays off). Answers come
from the event streams (Claude Code's ``result`` event, Codex's last ``agent_message``); a failure
puts the endpoint's HTTP status right after 「：」 so tasks/errors.py names the reason.
"""

import json
import os
import re
import subprocess
from pathlib import Path

from prometheus.agents import commands, contain
from prometheus.report import pi_run

NAMES = {"claude": "Claude Code", "codex": "Codex CLI"}
_STATUS = re.compile(r"\bstatus (\d{3})\b|API Error: (\d{3})\b")


class AgentRunError(RuntimeError):
    code = "EXTERNAL_MODEL_FAILURE"


def agent_of(llm: dict) -> dict:
    """The Agent part of the settings' ``llm`` view: which one, how it connects, where to."""
    return {"id": llm.get("agent") or "pi", "access": llm.get("access") or "key",
            "base_url": llm.get("base_url") or (llm.get("custom") or {}).get("base_url", "")}


def _events(stdout: bytes) -> list:
    events = []
    for line in (stdout or b"").decode("utf-8", "replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _failure(agent_id: str, message: str, status=None) -> AgentRunError:
    if status is None and (found := _STATUS.search(message or "")):
        status = next(group for group in found.groups() if group)
    return AgentRunError(f"{NAMES[agent_id]} 调用失败：{f'{status} ' if status else ''}{message}")


def _answer(agent_id: str, result: subprocess.CompletedProcess) -> str:
    events = _events(result.stdout)
    stderr = (result.stderr or b"").decode("utf-8", "replace").strip()
    if agent_id == "claude":
        final = next((event for event in reversed(events) if event.get("type") == "result"), None)
        if final and not final.get("is_error") and result.returncode == 0:
            return (final.get("result") or "").strip()
        status = (final or {}).get("api_error_status")
        raise _failure(agent_id, (final or {}).get("result") or stderr or "没有输出", str(status) if status else None)
    failed = next((event for event in reversed(events) if event.get("type") == "turn.failed"), None)
    if failed or result.returncode != 0:
        errors = [event.get("message", "") for event in events if event.get("type") == "error"]
        message = ((failed or {}).get("error") or {}).get("message") or (errors[-1] if errors else "") or stderr
        raise _failure(agent_id, message or "没有输出")
    texts = [event["item"].get("text", "") for event in events
             if event.get("type") == "item.completed" and (event.get("item") or {}).get("type") == "agent_message"]
    return texts[-1].strip() if texts else ""


def _start(agent: dict, *, prompt: str, model: str, api_key: str, thinking: str, cwd: Path, config_root, tools_root,
           tools, write: bool, files=(), timeout=None) -> subprocess.CompletedProcess:
    agent_id = agent["id"]
    exe = commands.executable(tools_root, agent_id)
    (Path(config_root) / agent_id).mkdir(parents=True, exist_ok=True)
    if agent_id == "claude":
        command = commands.claude_command(exe, model=model, thinking=thinking, tools=tools)
        env = commands.claude_env(os.environ, config_root=config_root, base_url=agent["base_url"], api_key=api_key)
    else:
        signed_in = agent.get("access") == "login"
        command = commands.codex_command(exe, model=model, thinking=thinking, workspace=cwd, write=write,
                                         base_url=None if signed_in else agent["base_url"], images=files)
        env = commands.codex_env(os.environ, config_root=config_root, api_key=None if signed_in else api_key)
    own = Path(config_root) / agent_id
    writable = [cwd, own] if write else [own]  # everything else stays out of reach (contain.py)
    command = [*contain.prefix(writable, temp=own / "tmp"), *command]
    try:
        return subprocess.run(command, input=prompt.encode("utf-8"), capture_output=True, cwd=str(cwd), env=env,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AgentRunError(f"{NAMES[agent_id]} generation timed out: the stage's time is used up") from exc
    except OSError as exc:
        raise AgentRunError(f"启动 {NAMES[agent_id]} 失败（在「设置 · 检查更新」里安装）：{exc}") from exc


def one_shot(agent: dict, *, prompt: str, model: str, api_key: str, thinking: str, work_dir, config_root, tools_root,
             files=()) -> str:
    """A text answer; `files` are images to look at (Codex attaches them, Claude Code reads them)."""
    if files and agent["id"] == "claude":
        prompt += "\n\n先用 Read 工具逐张查看这些图片，再回答：\n" + "\n".join(str(path) for path in files)
    result = _start(agent, prompt=prompt, model=model, api_key=api_key, thinking=thinking, cwd=Path(work_dir),
                    config_root=config_root, tools_root=tools_root, tools="Read" if files else False, write=False,
                    files=files if agent["id"] == "codex" else ())
    return _answer(agent["id"], result)


def task(agent: dict, workspace, prompt: str, *, expect: str, model: str, api_key: str, thinking: str, config_root,
         tools_root, timeout: float) -> Path:
    """Run once in `workspace`; the file `expect` must be there afterwards (as pi_run.run_task)."""
    workspace = Path(workspace)
    skill = workspace / "SKILL.md"
    parts = [pi_run.SYSTEM, skill.read_text(encoding="utf-8") if skill.is_file() else "", prompt]
    result = _start(agent, prompt="\n\n".join(part for part in parts if part), model=model, api_key=api_key,
                    thinking=thinking, cwd=workspace, config_root=config_root, tools_root=tools_root, tools=True,
                    write=True, timeout=timeout)
    with (workspace / "agent.events.jsonl").open("ab") as log:
        log.write(result.stdout or b"")
    with (workspace / "agent.stderr.log").open("ab") as log:
        log.write(result.stderr or b"")
    _answer(agent["id"], result)
    target = workspace / expect
    if not target.is_file():
        raise AgentRunError(f"{NAMES[agent['id']]} 结束了，但没有写出 {expect}")
    return target
