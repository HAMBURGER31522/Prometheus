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
import sys
from pathlib import Path

from prometheus.agents import commands, contain
from prometheus.report import pi_run

NAMES = {"claude": "Claude Code", "codex": "Codex CLI"}
SKILL_ATTACHED = "=== 附件：SKILL.md"
# The rules and the skill speak of Pi's read / write / edit / powershell tools; this says which of each
# Agent's tools those are, and keeps text files in UTF-8 (Windows PowerShell 5.1 reads them as GBK).
UTF8 = ("读写文本文件一律用 UTF-8：读用 Get-Content -Raw -Encoding UTF8，写用 "
        "[IO.File]::WriteAllText(路径, 文本, [Text.UTF8Encoding]::new($false))；不要用 Set-Content 或 Out-File。")
TOOL_NOTES = {
    "claude": ("工具对照：文中说的 read 工具就是 Read，也用它看图片（例如 frames/ 里的候选帧）；write、edit 工具就是 Edit，"
               "新建文件时 old_string 留空，整篇写回时先 Read 再用 Edit 替换全文；powershell 工具就是 PowerShell。" + UTF8),
    "codex": ("工具对照：文中说的 read 工具，读文本用 shell，看图片（例如 frames/ 里的候选帧）用 view_image；write、edit 工具"
              "用 apply_patch（有的话），没有就在 shell 里写；powershell 工具就是你的 shell。" + UTF8),
}
PI_CLI = Path("pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js")
_STATUS = re.compile(r"\bstatus (\d{3})\b|API Error: (\d{3})\b")


class AgentRunError(RuntimeError):
    code = "EXTERNAL_MODEL_FAILURE"


def agent_of(llm: dict) -> dict:
    """The Agent part of the settings' ``llm`` view: which one, how it connects, where to."""
    return {"id": llm.get("agent") or "pi", "access": llm.get("access") or "key",
            "base_url": llm.get("base_url") or (llm.get("custom") or {}).get("base_url", ""),
            "context_window": llm.get("context_window"), "max_tokens": llm.get("max_tokens"),
            "protocol": llm.get("protocol") or (llm.get("custom") or {}).get("protocol", "")}


def _limits(agent: dict, model: str, config_root, tools_root) -> tuple:
    """(context window, maximum output): the profile's own, else what the model catalogue says — the
    same lookup that fills Pi's models.json (llm/pi_models.model_fields)."""
    context, most = agent.get("context_window"), agent.get("max_tokens")
    if context and most:
        return context, most
    from prometheus.llm import pi_models

    protocol = agent.get("protocol") or ("anthropic" if agent["id"] == "claude" else "openai")
    profile = {"kind": "custom", "model": model.removesuffix("[1m]"), "protocol": protocol,
               "base_url": agent.get("base_url", "")}
    try:
        _source, fields = pi_models.model_fields(Path(config_root).parent.parent, profile,
                                                 pi_cli=Path(tools_root) / PI_CLI)
    except (OSError, ValueError, KeyError):
        fields = {}
    return context or fields.get("contextWindow"), most or fields.get("maxTokens")


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
           tools, write: bool, files=(), timeout=None, system: str = "") -> subprocess.CompletedProcess:
    agent_id = agent["id"]
    exe = commands.executable(tools_root, agent_id)
    (Path(config_root) / agent_id).mkdir(parents=True, exist_ok=True)
    context, most = _limits(agent, model, config_root, tools_root)
    base_env = {**os.environ, "VIDEO_REPORT_PYTHON": sys.executable, "PYTHONUTF8": "1"} if write else os.environ
    if agent_id == "claude":
        command = commands.claude_command(exe, model=commands.claude_model(model, context), thinking=thinking,
                                          tools=tools, system=system)
        env = commands.claude_env(base_env, config_root=config_root, base_url=agent["base_url"], api_key=api_key,
                                  max_tokens=most, context_window=context)
    else:
        signed_in = agent.get("access") == "login"
        command = commands.codex_command(exe, model=model, thinking=thinking, workspace=cwd, write=write,
                                         base_url=None if signed_in else agent["base_url"], images=files,
                                         context_window=context, max_tokens=most, system=system)
        env = commands.codex_env(base_env, config_root=config_root, api_key=None if signed_in else api_key)
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
    attached = SKILL_ATTACHED in prompt  # the chapter prompts carry SKILL.md already (report/full.py)
    parts = ["" if attached or not skill.is_file() else skill.read_text(encoding="utf-8"), prompt]
    result = _start(agent, prompt="\n\n".join(part for part in parts if part), model=model, api_key=api_key,
                    thinking=thinking, cwd=workspace, config_root=config_root, tools_root=tools_root, tools=True,
                    write=True, timeout=timeout, system=f"{pi_run.SYSTEM}\n\n{TOOL_NOTES[agent['id']]}")
    with (workspace / "agent.events.jsonl").open("ab") as log:
        log.write(result.stdout or b"")
    with (workspace / "agent.stderr.log").open("ab") as log:
        log.write(result.stderr or b"")
    _answer(agent["id"], result)
    target = workspace / expect
    if not target.is_file():
        raise AgentRunError(f"{NAMES[agent['id']]} 结束了，但没有写出 {expect}")
    return target
